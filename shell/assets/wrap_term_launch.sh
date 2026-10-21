#!/usr/bin/env sh

cat ~/.local/state/hics/sequences.txt 2>/dev/null

exec "$@"
