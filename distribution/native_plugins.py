#!/usr/bin/env python3
"""Validate the complete native plugin payload before deployment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PLUGINS = {
    "hics-capture.so": Path("hics-capture.so"),
    "hics-bars.so": Path("hics-bars.so"),
    "libspatialoverview.so": Path("third_party/phantomat/libspatialoverview.so"),
}


def validate(directory: Path, build: Path, abi: str | None = None):
    metadata = json.loads((directory / "native-version.json").read_text())
    built_metadata = json.loads((build / "native-version.json").read_text())
    expected = abi or built_metadata.get("abiHash")
    if not expected or metadata.get("abiHash") != expected or built_metadata.get("abiHash") != expected:
        raise ValueError("Native plugin ABI does not match the compositor/build")
    result = {}
    for name, relative in PLUGINS.items():
        installed = (directory / name).read_bytes()
        compiled = (build / relative).read_bytes()
        if not installed.startswith(b"\x7fELF") or len(installed) < 64:
            raise ValueError("Invalid native library: " + name)
        if installed != compiled:
            raise ValueError("Staged native library differs from the current build: " + name)
        result[name] = hashlib.sha256(installed).hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("build", type=Path)
    arguments = parser.parse_args()
    try:
        print(json.dumps(validate(arguments.directory, arguments.build), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Native plugin validation failed: {error}\n")
