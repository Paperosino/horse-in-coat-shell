#!/usr/bin/env bash
# Arch installation: one command for dependencies, package and hics units.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if ((EUID == 0)); then
    printf 'Run ./install.sh as your regular user; it invokes sudo when needed.\n' >&2
    exit 1
fi
case "${1:-}" in
    --help|-h)
        printf 'Usage:\n  ./install.sh [--dry-run] [makepkg options]\n  ./install.sh --package FILE [--dry-run]\n\nSource installation builds a package and installs all required runtime/build dependencies.\nA prebuilt package needs runtime dependencies only, resolved by pacman.\n'
        exit 0 ;;
    --package)
        [[ $# == 2 || ( $# == 3 && $3 == --dry-run ) ]] || { printf 'Usage: ./install.sh --package FILE [--dry-run]\n' >&2; exit 2; }
        command -v pacman >/dev/null || { printf 'This installer requires Arch Linux and pacman.\n' >&2; exit 1; }
        [[ -f $2 ]] || { printf 'Package not found: %s\n' "$2" >&2; exit 1; }
        package=$(cd -- "$(dirname -- "$2")" && pwd -P)/$(basename -- "$2")
        name=$(pacman -Qqp -- "$package")
        [[ $name == hic-shell ]] || { printf 'Expected hic-shell package, got %s\n' "$name" >&2; exit 1; }
        if [[ ${3:-} == --dry-run ]]; then
            printf 'Plan: sudo pacman -U -- %q\nRuntime dependencies and hics service hooks are handled by pacman.\n' "$package"
            exit 0
        fi
        sudo -- pacman -U -- "$package"
        printf 'hic-shell installed; its package hook enables the hics services.\n'
        ;;
    *) exec "$root/packaging/arch/build-package.sh" --install "$@" ;;
esac
