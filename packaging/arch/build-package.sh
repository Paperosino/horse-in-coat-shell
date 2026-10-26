#!/usr/bin/env bash
# Build/install from one dependency manifest; never run makepkg as root.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
root=$(cd -- "$here/../.." && pwd -P)
if ((EUID == 0)); then
    printf 'Run this script as your regular user, without sudo.\n' >&2
    exit 1
fi
command -v pacman >/dev/null || { printf 'This installer requires Arch Linux and pacman.\n' >&2; exit 1; }
install_requested=0
dry_run=0
args=()
for arg in "$@"; do
    case "$arg" in
        --dry-run) dry_run=1 ;;
        --install|-i) install_requested=1 ;;
        -si|-is) install_requested=1; args+=(-s) ;;
        --help|-h)
            printf 'Usage: %s [--install] [--dry-run] [makepkg options]\n' "$0"
            exit 0 ;;
        *) args+=("$arg") ;;
    esac
done
# Runtime libraries are also required to link the source build. Pacman resolves
# virtual providers/version constraints; PKGBUILD is the only dependency list.
mapfile -t dependencies < <(bash -c 'source "$1"; printf "%s\n" "${depends[@]}" "${makedepends[@]}"' _ "$here/PKGBUILD")
missing=()
if output=$(pacman -T "${dependencies[@]}"); then
    :
else
    status=$?
    if ((status != 127)); then
        printf 'pacman could not check dependencies (status %s).\n' "$status" >&2
        exit "$status"
    fi
    mapfile -t missing <<< "$output"
fi
if ((dry_run)); then
    printf 'Missing runtime/build dependencies: %s\n' "${missing[*]:-(none)}"
    printf 'Plan: install missing dependencies with pacman; validate Hyprland ABI; build as user; copy package to %s\n' "$root"
    if ((install_requested)); then printf 'Then install the package with pacman -U; package hooks enable hics services.\n'; fi
    exit 0
fi
if ((${#missing[@]})); then
    printf 'Installing missing runtime/build dependencies: %s\n' "${missing[*]}"
    # Prompt normally. Do not silently downgrade --install to build-only.
    sudo -- pacman -S --needed -- "${missing[@]}"
fi
command -v rsync >/dev/null || { printf 'rsync is required for source staging.\n' >&2; exit 1; }
# Check before an expensive bundled-runtime build. Never upgrade/downgrade a
# running compositor or run pacman -Sy as an implicit recovery step.
abi=$(python3 -c 'import json,subprocess; v=json.loads(subprocess.check_output(["Hyprland","--version-json"])); assert v.get("version")=="0.56.2" and v.get("abiHash"), "Hyprland 0.56.2 is required"; print(v["abiHash"])')
python3 "$root/distribution/check_headers.py" "$abi"
stage=$(mktemp -d "${TMPDIR:-/tmp}/hics-package.XXXXXXXX")
cleanup() {
    if [[ ${KEEP_STAGING:-0} == 1 ]]; then printf 'Staging directory kept: %s\n' "$stage";
    else rm -rf -- "$stage"; fi
}
trap cleanup EXIT
stage=$(cd -- "$stage" && pwd -P)
case "$stage/" in "$root/"*) printf 'TMPDIR must be outside the source repository.\n' >&2; exit 1 ;; esac
mkdir -p "$stage/src/hics"
rsync -a --exclude='/.git' --exclude='/build' --exclude='/pkg' --exclude='/src' --exclude='/*.pkg.tar.*' \
    "$root/" "$stage/src/hics/"
cp "$here/PKGBUILD" "$stage/PKGBUILD"
cp "$here/hic-shell.install" "$stage/hic-shell.install"
# Keep paths predictable even when the user's makepkg.conf defines PKGDEST or
# BUILDDIR. --packagelist is authoritative; never glob detached signatures.
cd "$stage"
export PKGDEST="$stage" BUILDDIR="$stage/build"
makepkg --cleanbuild "${args[@]}" "PKGDEST=$stage" "BUILDDIR=$stage/build"
mapfile -t packages < <(makepkg --packagelist "${args[@]}" "PKGDEST=$stage" "BUILDDIR=$stage/build")
artifacts=()
for pkg in "${packages[@]}"; do
    [[ -f $pkg && $pkg != *.sig ]] || { printf 'Missing built package: %s\n' "$pkg" >&2; exit 1; }
    dest="$root/$(basename -- "$pkg")"
    cp -f -- "$pkg" "$dest"
    if [[ -f $pkg.sig ]]; then cp -f -- "$pkg.sig" "$dest.sig"; fi
    artifacts+=("$dest")
done
((${#artifacts[@]})) || { printf 'makepkg produced no packages.\n' >&2; exit 1; }
printf 'Built package: %s\n' "${artifacts[@]}"
if ((install_requested)); then
    sudo -- pacman -U -- "${artifacts[@]}"
    printf 'Package installed. hics services are enabled by its installation hook.\n'
fi
