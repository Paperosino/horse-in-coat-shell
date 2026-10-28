#!/usr/bin/env python3
"""Apply/check audited QS source fixes and attest the staged runtime binary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA256 = '946a27e2a276917a03c1079e5c60971af84ece73088c3661dee455d92eb420f7'
PATCHES = ('quickshell-v0.3.2-logging-lifetime.patch', 'quickshell-v0.3.2-shutdown-lifetime.patch', 'quickshell-v0.3.2-process-lifetime.patch', 'quickshell-v0.3.2-fontconfig-xml.patch', 'quickshell-v0.3.2-video-capture-nodes.patch')
MANIFEST = 'hics-quickshell-patches.json'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def patch_hashes():
    return {name: sha(ROOT / 'distribution/patches' / name) for name in PATCHES}


def source_check(source, apply=False):
    if not re.search(r'project\(quickshell\s+VERSION\s+"0\.3\.2"', (source / 'CMakeLists.txt').read_text()):
        raise ValueError('Audited Quickshell v0.3.2 source is required')
    for name in PATCHES:
        command = ['patch', '--force', '--batch', '--fuzz=0', '-p1', '-i', str(ROOT / 'distribution/patches' / name)]
        reverse = subprocess.run([*command, '--reverse', '--dry-run'], cwd=source, capture_output=True)
        if reverse.returncode == 0:
            continue
        if not apply:
            raise ValueError('QS source fix is missing: ' + name)
        subprocess.run([*command, '--forward', '--dry-run'], cwd=source, check=True, capture_output=True)
        subprocess.run([*command, '--forward'], cwd=source, check=True, capture_output=True)


def binary(root):
    path = root / 'bin/hics-qs'
    if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError('A regular executable bin/hics-qs is required')
    return path


def allocator_library(root):
    path = (root / 'lib/libjemalloc.so.2').resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Allocator must be a regular library inside the runtime')
    return path


def allocator_info(root):
    dynamic = subprocess.check_output(['readelf', '-d', str(binary(root))], text=True, timeout=10)
    if not re.search(r'\(NEEDED\).*\[libjemalloc\.so\.2\]', dynamic):
        return {'kind': 'system'}
    return {'kind': 'jemalloc', 'path': 'lib/libjemalloc.so.2', 'sha256': sha(allocator_library(root))}


def verify(root, require_jemalloc=False):
    descriptor = os.open(root / MANIFEST, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('QS manifest must be a regular file')
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError('QS manifest is too large')
    data = json.loads(raw)
    if (data.get('version') != '0.3.2' or data.get('archiveSha256') != ARCHIVE_SHA256
            or data.get('patches') != patch_hashes() or data.get('executableSha256') != sha(binary(root))):
        raise ValueError('QS runtime provenance/checksum mismatch')
    # Older system-allocator bundles have no allocator field. New linked
    # allocators are attested together with the executable, not supplied by
    # LD_PRELOAD or inherited by subsequently launched applications.
    allocator = data.get('allocator')
    if require_jemalloc and (not isinstance(allocator, dict) or allocator.get('kind') != 'jemalloc'):
        raise ValueError('Bundled jemalloc provenance is required for release packages')
    if allocator is not None and allocator != {'kind': 'system'}:
        if (not isinstance(allocator, dict) or allocator.get('kind') != 'jemalloc'
                or allocator.get('path') != 'lib/libjemalloc.so.2'):
            raise ValueError('Unsupported allocator provenance')
        if allocator.get('sha256') != sha(allocator_library(root)):
            raise ValueError('Allocator checksum mismatch')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['apply', 'stamp', 'verify'])
    p.add_argument('--source', type=Path)
    p.add_argument('--root', type=Path)
    p.add_argument('--require-jemalloc', action='store_true')
    a = p.parse_args()
    if a.action in ('apply', 'stamp'):
        if not a.source:
            p.error('--source is required')
        source_check(a.source, apply=a.action == 'apply')
    if a.action == 'stamp':
        if not a.root:
            p.error('--root is required')
        data = {'version': '0.3.2', 'archiveSha256': ARCHIVE_SHA256,
                'patches': patch_hashes(), 'executableSha256': sha(binary(a.root)),
                'allocator': allocator_info(a.root)}
        descriptor, temporary = tempfile.mkstemp(prefix='.hics-qs-manifest-', dir=a.root)
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(data, stream, indent=2)
                stream.write('\n')
            os.chmod(temporary, 0o644)
            os.replace(temporary, a.root / MANIFEST)
        finally:
            Path(temporary).unlink(missing_ok=True)
    if a.action in ('stamp', 'verify'):
        if not a.root:
            p.error('--root is required')
        verify(a.root, require_jemalloc=a.require_jemalloc)


if __name__ == '__main__':
    main()
