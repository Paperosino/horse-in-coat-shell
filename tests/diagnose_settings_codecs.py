#!/usr/bin/env python3
"""Run codec identity/decode/concurrency and shutdown ownership under ASan/LSan."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library-dir', type=Path, required=True)
    p.add_argument('--serial', action='store_true', help='Single worker for the original thread-unsafe baseline')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('Use a fresh evidence path')
    library = a.library_dir / 'libhyprstack-settings.so'
    with tempfile.TemporaryDirectory(prefix='hics-codec-lifetime-') as d:
        binary = Path(d) / 'probe'
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Core', 'Qt6Qml'], text=True))
        subprocess.run(['c++', '-std=c++20', '-fPIC', '-fsanitize=address', '-fno-omit-frame-pointer', '-g',
            str(ROOT / 'tests/fixtures/settings-codec-lifetime.cpp'),
            '-I' + str(ROOT / 'shell/plugin/src/Hyprstack/Settings'), '-L' + str(a.library_dir),
            '-lhyprstack-settings', *flags, '-o', str(binary)], check=True, capture_output=True, text=True, timeout=30)
        env = dict(os.environ, LD_LIBRARY_PATH=str(a.library_dir), ASAN_OPTIONS='detect_leaks=1:halt_on_error=1')
        env.pop('LSAN_OPTIONS', None)
        result = subprocess.run([str(binary)] + (['--serial'] if a.serial else []), env=env, capture_output=True, text=True, timeout=20)
        text = result.stdout + result.stderr
        a.output.with_suffix('.log').write_text(text)
        report = {'code':result.returncode,'workers':1 if a.serial else 8,
            'librarySha256':hashlib.sha256(library.read_bytes()).hexdigest(),
            'scope':'Repeated codec identity, list/union decode and cache shutdown; not the full settings UI'}
        a.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 0 if result.returncode == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
