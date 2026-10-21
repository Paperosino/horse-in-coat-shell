#!/usr/bin/env bash
# Build the hics-shell Arch package from the repository tree.
# Usage: packaging/arch/build-package.sh [makepkg options, e.g. --install]
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)
root=$(cd -- "$here/../.." && pwd -P)

stage=$(mktemp -d "${TMPDIR:-/tmp}/hics-package.XXXXXXXX")
cleanup() {
    if [[ ${KEEP_STAGING:-0} == 1 ]]; then
        printf 'Staging directory kept: %s\n' "$stage"
    else
        rm -rf "$stage"
    fi
}
trap cleanup EXIT

printf 'Staging source tree in %s\n' "$stage"
mkdir -p "$stage/src/hics"
rsync -a --exclude='/.git' --exclude='/build' --exclude='/pkg' --exclude='/src' \
    "$root"/ "$stage/src/hics/"
cp "$here/PKGBUILD" "$stage/PKGBUILD"
cp "$here/hic-shell.install" "$stage/hic-shell.install"

# Report and install missing build dependencies non-interactively.
mapfile -t makedepends < <(bash -c 'source "$1" >/dev/null 2>&1; printf "%s\n" "${makedepends[@]}"' _ "$stage/PKGBUILD")
missing=()
for dep in "${makedepends[@]}"; do
    pacman -T "$dep" >/dev/null 2>&1 && continue
    if pacman -Sg "$dep" >/dev/null 2>&1; then
        group_ok=1
        while read -r _ member; do
            if ! pacman -Q "$member" >/dev/null 2>&1; then
                group_ok=0
                break
            fi
        done < <(pacman -Sg "$dep")
        ((group_ok)) && continue
    fi
    missing+=("$dep")
done
if ((${#missing[@]})); then
    printf 'Missing build dependencies: %s\n' "${missing[*]}"
    if sudo -n pacman -S --needed --noconfirm "${missing[@]}"; then
        printf 'Build dependencies installed.\n'
    else
        printf 'Install the build dependencies manually:\n  sudo pacman -S --needed %s\n' "${missing[*]}" >&2
        exit 1
    fi
fi

install_requested=0
for arg in "$@"; do
    case $arg in
        -i|--install|-si|-is) install_requested=1 ;;
    esac
done

args=("$@")
deferred_install=0
if ((install_requested)) && ! sudo -n true 2>/dev/null; then
    printf 'sudo requires a password; building without installing.\n'
    args=()
    for arg in "$@"; do
        case $arg in
            -i|--install|-si|-is) ;;
            *) args+=("$arg") ;;
        esac
    done
    deferred_install=1
fi

mkdir -p "$stage/build"
cd "$stage"
if ! BUILDDIR="$stage/build" makepkg --cleanbuild "${args[@]}"; then
    printf 'makepkg failed.\n' >&2
    exit 1
fi

shopt -s nullglob
packages=("$stage"/hic-shell-*.pkg.tar.*)
if ((${#packages[@]} == 0)); then
    printf 'makepkg finished without producing a package.\n' >&2
    exit 1
fi
pkg=${packages[0]}

dest=$root/$(basename "$pkg")
cp -f "$pkg" "$dest"
pkg=$dest

if ((deferred_install)); then
    printf 'Package built (not installed; sudo needs a password):\n  sudo pacman -U --noconfirm %s\n' "$pkg"
    exit 0
fi
printf 'Built package: %s\n' "$pkg"
