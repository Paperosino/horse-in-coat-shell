#!/usr/bin/env python3
"""Reject development headers which cannot build a compatible native plugin."""
from pathlib import Path
import re
import shlex
import subprocess
import sys


def headers_abi():
    flags = subprocess.check_output(["pkg-config", "--cflags-only-I", "hyprland"], text=True)
    roots = [Path(flag[2:]) for flag in shlex.split(flags) if flag.startswith("-I") and len(flag) > 2]
    includedir = subprocess.check_output(["pkg-config", "--variable=includedir", "hyprland"], text=True).strip()
    if includedir:
        roots.append(Path(includedir))
    roots.append(Path("/usr/include"))
    header = next((root / "hyprland/src/version.h" for root in roots
                   if (root / "hyprland/src/version.h").is_file()), None)
    if header is None:
        raise ValueError("Hyprland development headers are missing version.h")
    defines = dict(re.findall(r'^#define\s+(\w+)\s+"([^"\n]*)"', header.read_text(), re.M))
    try:
        result = defines["GIT_COMMIT_HASH"]
        for suffix, name in (("aq", "AQUAMARINE"), ("hu", "HYPRUTILS"), ("hg", "HYPRGRAPHICS"),
                             ("hc", "HYPRCURSOR"), ("hlg", "HYPRLANG")):
            value = defines[name + "_VERSION"]
            result += "_" + suffix + "_" + (value.rsplit(".", 1)[0] if "." in value else value)
        return result
    except KeyError as error:
        raise ValueError("Incomplete Hyprland ABI metadata in development headers") from error


if __name__ == "__main__":
    try:
        actual = headers_abi()
        if len(sys.argv) != 2 or actual != sys.argv[1]:
            raise ValueError("Hyprland headers do not match the installed compositor ABI; install matching development files")
        print("Hyprland development headers match the compositor ABI")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
