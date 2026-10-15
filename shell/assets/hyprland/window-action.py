#!/usr/bin/env python3
"""Dispatch a titlebar action to the owning window, including address-reuse protection."""
import json
import os
import re
import subprocess
import sys


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"minimize", "maximize", "maximize-set", "maximize-unset", "close"}:
        return 2
    address = os.environ.get("HYPRSTACK_WINDOW_ADDRESS", "")
    stable_id = os.environ.get("HYPRSTACK_WINDOW_ID", "")
    if not re.fullmatch(r"0x[0-9a-fA-F]+", address) or not re.fullmatch(r"[0-9a-fA-F]+", stable_id):
        return 2
    arguments = ",".join(json.dumps(value) for value in (sys.argv[1], address, stable_id))
    return subprocess.run(["hyprctl", "eval", f"hyprstack_layouts.action({arguments})"]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
