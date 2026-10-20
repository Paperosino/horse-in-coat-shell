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

# Shared glibc/toolchain libraries are always taken from the system.
toolchain_re='^(ld-linux|libc\.so|libm\.so|libpthread|librt|libdl|libresolv|libstdc\+\+\.so|libgcc_s\.so|libatomic\.so)'

is_excluded() {
    [[ $1 =~ $toolchain_re ]]
}

have_lib() {
    [[ -e $lib_dir/$1 ]]
}

copy_lib() {
    local needed=$1 resolved=$2 real base
    real=$(readlink -f "$resolved")
    base=$(basename "$real")
    if [[ ! -e $lib_dir/$base ]]; then
        cp -a "$real" "$lib_dir/$base"
        printf 'bundled lib: %s\n' "$base"
    fi
    if [[ $needed != "$base" && ! -e $lib_dir/$needed ]]; then
        ln -sf "$base" "$lib_dir/$needed"
    fi
}

# Copy the closure of one ELF object (binary or library). Returns 0 when at
# least one new library was copied, 1 otherwise.
scan_deps() {
    local target=$1 copied=0 line needed resolved
    while IFS= read -r line; do
        if [[ $line =~ ^[[:space:]]*([^[:space:]]+)[[:space:]]+\=\>[[:space:]]+(/[^[:space:]]+) ]]; then
            needed=${BASH_REMATCH[1]}
            resolved=${BASH_REMATCH[2]}
        elif [[ $line =~ ^[[:space:]]*(/[^[:space:]]+\.so[^[:space:]]*)[[:space:]]+\(0x ]]; then
            resolved=${BASH_REMATCH[1]}
            needed=$resolved
        else
            continue
        fi
        # NEEDED may itself be a path (e.g. /lib64/ld-linux-x86-64.so.2 on
        # glibc 2.44 ldd output); only the plain soname is ever bundled.
        needed=${needed##*/}
        [[ -e $resolved ]] || continue
        is_excluded "$needed" && continue
        have_lib "$needed" && continue
        copy_lib "$needed" "$resolved"
        copied=1
    done < <(ldd "$target" 2>/dev/null || true)
    return "$copied"
}

# One pass over every library already in the bundle plus the qs binary.
closure_pass() {
    local copied=0 obj
    scan_deps "$qs_bin" || copied=1
    while IFS= read -r -d '' obj; do
        scan_deps "$obj" || copied=1
    done < <(find "$lib_dir" -xtype f \( -name '*.so' -o -name '*.so.*' \) -print0)
    return "$copied"
}

fixpoint() {
    local pass=0
    while closure_pass; do
        pass=$((pass + 1))
        if ((pass > 100)); then
            printf 'error: library closure did not converge\n' >&2
            return 1
        fi
    done
}

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
    sqldrivers tls multimedia; do
    src=$qt_plugins/$dir
    if [[ ! -d $src ]]; then
        printf 'warn: Qt plugin directory missing: %s\n' "$src" >&2
        continue
    fi
    mkdir -p "$plugins_dest/$dir"
    find "$src" -maxdepth 1 \( -type f -o -type l \) \( -name '*.so' -o -name '*.so.*' \) \
        -exec cp -a -t "$plugins_dest/$dir" {} +
done

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

# 6. Use a Hyprstack-specific binary name (qt.conf lookup is app-dir based).
if [[ -e $root/bin/quickshell || -L $root/bin/quickshell ]]; then
    mv -f "$root/bin/quickshell" "$root/bin/hyprstack-qs"
fi
rm -f "$root/bin/qs"

printf 'bundle complete: %s\n' "$root"
