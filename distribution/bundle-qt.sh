#!/usr/bin/env bash
# Assemble a self-contained quickshell + Qt runtime inside an installed tree.
# Usage: bundle-qt.sh <qs binary> <bundle root> <qt plugins> <qt qml> <qt libs> <qs source dir>
# Idempotent: safe to re-run over an existing bundle.
set -euo pipefail

qs_bin=$1
root=$2
qt_plugins=$3
qt_qml=$4
qt_libs=$5
qs_source=$6
qt_overlay=${7:-}

lib_dir=$root/lib

if [[ ! -f $qs_bin ]]; then
    printf 'error: quickshell binary not found: %s\n' "$qs_bin" >&2
    exit 1
fi
chmod 755 "$qs_bin"
if [[ ! -d $qt_qml || ! -d $qt_plugins || ! -d $qt_libs ]]; then
    printf 'error: invalid Qt directories (qml/plugins/libs): %s %s %s\n' "$qt_qml" "$qt_plugins" "$qt_libs" >&2
    exit 1
fi

mkdir -p "$lib_dir" "$root/bin" "$root/licenses"

source "$(dirname -- "${BASH_SOURCE[0]}")/runtime-dependencies.sh"

# Native desktop workers use modules which quickshell itself may not link.
# Keep their Qt ABI in the same private runtime as Core/DBus.
for module in Concurrent Sql; do
    name="libQt6${module}.so.6"
    if [[ ! -e $qt_libs/$name ]]; then
        printf 'error: required Qt worker library missing: %s\n' "$qt_libs/$name" >&2
        exit 1
    fi
    copy_lib "$name" "$qt_libs/$name"
done

# Discard unsupported optional SQL server drivers from an older cached bundle
# before its first closure check. The workers only instantiate QSQLITE.
if [[ -d $lib_dir/qt6/plugins/sqldrivers ]]; then
    find "$lib_dir/qt6/plugins/sqldrivers" -maxdepth 1 \( -type f -o -type l \) \
        -name '*.so*' ! -name libqsqlite.so -delete
fi

# 1. Closure of the quickshell binary itself (Qt, wayland, icu, ...).
fixpoint

# 2. Qt QML modules and plugins used by the shell.
qml_dest=$lib_dir/qt6/qml
mkdir -p "$qml_dest"
for dir in Qt QtQml QtQuick QtMultimedia; do
    if [[ -d $qt_qml/$dir ]]; then
        cp -a "$qt_qml/$dir" "$qml_dest/"
    else
        printf 'warn: Qt QML directory missing: %s\n' "$qt_qml/$dir" >&2
    fi
done

plugins_dest=$lib_dir/qt6/plugins
for dir in platforms wayland-shell-integration wayland-decoration-client \
    wayland-graphics-integration-client imageformats iconengines \
    tls multimedia; do
    src=$qt_plugins/$dir
    if [[ ! -d $src ]]; then
        printf 'warn: Qt plugin directory missing: %s\n' "$src" >&2
        continue
    fi
    mkdir -p "$plugins_dest/$dir"
    find "$src" -maxdepth 1 \( -type f -o -type l \) \( -name '*.so' -o -name '*.so.*' \) \
        -exec cp -a -t "$plugins_dest/$dir" {} +
done

# Both private HICS databases use QSQLITE. Optional SQL server drivers may be
# installed with Qt without their external client libraries (e.g. Firebird).
# They have no caller in this runtime; external applications use their own Qt.
sqlite_plugin=$qt_plugins/sqldrivers/libqsqlite.so
if [[ ! -f $sqlite_plugin ]]; then
    printf 'error: the private HICS databases require %s\n' "$sqlite_plugin" >&2
    exit 1
fi
mkdir -p "$plugins_dest/sqldrivers"
cp -a "$sqlite_plugin" "$plugins_dest/sqldrivers/"

# Apply source-built Qt fixes before the final dependency closure. Keep QML,
# graphics integrations and other unmodified plugins from the original bundle.
if [[ -n $qt_overlay ]]; then
    python3 "$(dirname "$0")/apply_qt_runtime_patches.py" --overlay "$qt_overlay" --root "$root"
fi

# 3. Second closure over everything now under lib/ (catches plugin-only
#    dependencies such as QtSvg, QuickControls2, QuickShapes, QuickEffects).
fixpoint

# 4. qt.conf next to the binary keeps the bundle relocatable.
cat > "$root/bin/qt.conf" <<'EOF'
[Paths]
Prefix=..
Libraries=lib
Plugins=lib/qt6/plugins
QmlImports=lib/qt6/qml
EOF

# 5. Licenses for the bundled Qt libraries and quickshell.
qt_licenses=$root/licenses/qt
mkdir -p "$qt_licenses"
for pkg in qt6-base qt6-declarative qt6-svg qt6-imageformats qt6-shadertools qt6-wayland qt6-multimedia ffmpeg; do
    src=/usr/share/licenses/$pkg
    if [[ -d $src ]]; then
        cp -a "$src"/. "$qt_licenses/"
    else
        printf 'warn: Qt license directory missing: %s\n' "$src" >&2
    fi
done
if [[ -f $qs_source/LICENSE ]]; then
    cp "$qs_source/LICENSE" "$root/licenses/quickshell-LGPL-3.0"
else
    printf 'warn: quickshell LICENSE not found in %s\n' "$qs_source" >&2
fi
if [[ -e $lib_dir/libjemalloc.so.2 ]]; then
    jemalloc_license=${HICS_JEMALLOC_LICENSE_FILE:-/usr/share/licenses/jemalloc/COPYING}
    if [[ ! -f $jemalloc_license ]]; then
        printf 'error: bundled jemalloc requires its license: %s\n' "$jemalloc_license" >&2
        exit 1
    fi
    cp "$jemalloc_license" "$root/licenses/jemalloc-BSD-2-Clause"
fi

# 6. Use the HICS runtime binary name (qt.conf lookup is app-dir based).
if [[ -e $root/bin/quickshell || -L $root/bin/quickshell ]]; then
    mv -f "$root/bin/quickshell" "$root/bin/hics-qs"
fi
rm -f "$root/bin/qs"

# Refuse an old cached QS binary/source stage without the audited source fixes.
python3 "$(dirname "$0")/apply_quickshell_patches.py" stamp --source "$qs_source" --root "$root"

printf 'bundle complete: %s\n' "$root"
