#!/usr/bin/env python3
"""Compile the actual QS LogMessage header and test queued category ownership.

Exit 1 reports the original ASan lifetime error; exit 0 is the fixed header.
This covers message copies/moves, not the whole logger or the renderer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('Use a fresh evidence path')
    source = Path(__file__).parent / 'fixtures/quickshell-logmessage-lifetime.cpp'
    header = a.source / 'src/core/logging.hpp'
    with tempfile.TemporaryDirectory(prefix='hics-logmessage-') as d:
        binary = Path(d) / 'probe'
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Core'], text=True))
        subprocess.run(['c++', '-std=c++20', '-fPIC', '-fsanitize=address', '-fno-omit-frame-pointer',
            '-g', str(source), '-I' + str(header.parent), *flags, '-o', str(binary)],
            check=True, capture_output=True, text=True, timeout=30)
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1')
        env.pop('LSAN_OPTIONS', None)
        result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=10)
        a.output.with_suffix('.log').write_text(result.stdout + result.stderr)
        report = {'code': result.returncode, 'headerSha256': hashlib.sha256(header.read_bytes()).hexdigest(),
                  'fixtureSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'asanUseAfterFree': 'heap-use-after-free' in result.stderr}
        a.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 0 if result.returncode == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
