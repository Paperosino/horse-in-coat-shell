#!/usr/bin/env python3
"""Reject a cached release executable without the audited startup policy.

This supplements the executable/library checksums in the QS manifest. It does
not execute the frontend or change the caller's allocator environment.
"""
import argparse
from pathlib import Path
import re
import subprocess

CONFIGURATION = b'dirty_decay_ms:1000,muzzy_decay_ms:0\0'


def verify(binary):
    if binary.is_symlink() or not binary.is_file():
        raise ValueError('A regular QS executable is required')
    symbols = subprocess.check_output(['readelf', '--dyn-syms', '--wide', str(binary)],
                                      text=True, timeout=10)
    if not re.search(r'\bOBJECT\s+GLOBAL\s+DEFAULT\s+\d+\s+malloc_conf\s*$', symbols, re.MULTILINE):
        raise ValueError('QS startup allocator policy symbol is missing')
    # The actual initialized value is tested with mallctl in the native fixture;
    # this release guard also refuses an older cached policy/configuration.
    with binary.open('rb') as stream:
        previous = b''
        for chunk in iter(lambda: stream.read(65536), b''):
            if CONFIGURATION in previous + chunk:
                return
            previous = chunk[-len(CONFIGURATION):]
    raise ValueError('QS startup allocator policy configuration is missing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    args = parser.parse_args()
    try:
        verify(args.binary)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + '\n')
