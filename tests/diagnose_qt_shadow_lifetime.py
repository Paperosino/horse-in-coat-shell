#!/usr/bin/env python3
"""Check default/custom RectangularShadow material ownership under ASan/LSan."""
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
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists(): p.error('Use a fresh evidence path')
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Quick', 'Qt6Qml', 'Qt6Gui'], text=True))
    headers = Path(subprocess.check_output(['qmake6', '-query', 'QT_INSTALL_HEADERS'], text=True).strip())
    with tempfile.TemporaryDirectory(prefix='hics-shadow-lifetime-') as d:
        binary = Path(d) / 'probe'
        subprocess.run(['c++', '-std=c++20', '-fPIC', '-fsanitize=address', '-fno-omit-frame-pointer', '-g',
            str(ROOT / 'tests/fixtures/qt-shadow-lifetime.cpp'), '-I' + str(headers),
            '-I' + str(headers / 'QtQuickEffects/6.12.0'), '-I' + str(headers / 'QtQuickEffects/6.12.0/QtQuickEffects'),
            '-I' + str(headers / 'QtQml/6.12.0'), '-I' + str(headers / 'QtQml/6.12.0/QtQml'),
            '-I' + str(headers / 'QtGui/6.12.0'), '-I' + str(headers / 'QtGui/6.12.0/QtGui'),
            '-I' + str(headers / 'QtQuick/6.12.0'), '-I' + str(headers / 'QtQuick/6.12.0/QtQuick'),
            '-I' + str(headers / 'QtCore/6.12.0'), '-I' + str(headers / 'QtCore/6.12.0/QtCore'),
            '-L' + str(a.library_dir), '-lQt6QuickEffects', *flags, '-o', str(binary)], check=True, timeout=30)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_NO_XDG_DESKTOP_PORTAL='1',
            ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', LD_LIBRARY_PATH=str(a.library_dir))
        env.pop('LSAN_OPTIONS', None)
        result = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=20)
        a.output.with_suffix('.log').write_text(result.stdout + result.stderr)
        report = {'code':result.returncode, 'librarySha256':hashlib.sha256((a.library_dir / 'libQt6QuickEffects.so.6').read_bytes()).hexdigest(),
            'scope':'100 actual Qt shadow objects, default/custom material switching and teardown; not visual acceptance'}
        a.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 0 if result.returncode == 0 and 'orphaned=0 alive=0' in result.stdout else 1
if __name__ == '__main__': raise SystemExit(main())
