#!/usr/bin/env python3
"""Build a private ASan QML object observer; never loads it into the desktop.

Use --extra-import OUTPUT with vm_settings_profile.py and a fixture which imports
Hics.LifetimeProbe 1.0. track(item) covers QObject and visual-child ownership;
report() lists surviving effects without retaining the observed objects.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('Use a new output directory; do not overwrite mapped libraries')
    target = args.output / 'Hics/LifetimeProbe'
    target.mkdir(parents=True)
    source = ROOT / 'tests/fixtures/qt-object-lifetime-probe.cpp'
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Quick', 'Qt6Qml'], text=True))
    moc = Path(subprocess.check_output(['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip()) / 'moc'
    subprocess.run([str(moc), str(source), '-o', str(target / 'qt-object-lifetime-probe.moc'),
        *[f for f in flags if f.startswith(('-I', '-D'))]], check=True, timeout=20)
    subprocess.run(['c++', '-std=c++20', '-fPIC', '-shared', '-g', '-fsanitize=address',
        '-I' + str(target), str(source), *flags, '-o', str(target / 'libhics-lifetimeprobe.so')], check=True, timeout=30)
    (target / 'qmldir').write_text('module Hics.LifetimeProbe\nplugin hics-lifetimeprobe\n')
    report = {'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'librarySha256':hashlib.sha256((target / 'libhics-lifetimeprobe.so').read_bytes()).hexdigest(),
        'scope':'Private test observer; never installed or loaded into the host shell'}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__': main()
