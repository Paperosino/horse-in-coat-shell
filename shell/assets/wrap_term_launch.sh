#!/usr/bin/env sh

cat ~/.local/state/hyprstack/sequences.txt 2>/dev/null

exec "$@"
