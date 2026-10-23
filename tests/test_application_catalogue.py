"""Exercise real XDG file watches and GIO launch dispatch without the host bus."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / 'shell/plugin/src/Hyprstack/Services'

class ApplicationCatalogueTests(unittest.TestCase):
    def test_live_create_edit_remove_and_gio_launch(self):
        with tempfile.TemporaryDirectory(prefix='hics-catalogue-') as directory:
            base = Path(directory)
            flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Core', 'Qt6Gui', 'Qt6Qml', 'gio-unix-2.0'], text=True))
            moc = Path(subprocess.check_output(['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip()) / 'moc'
            subprocess.run([str(moc), str(SERVICES/'applicationcatalogue.hpp'), '-o', str(base/'moc.cpp')], check=True)
            subprocess.run(['c++', '-std=c++20', '-fPIC', str(ROOT/'tests/fixtures/application-catalogue-probe.cpp'), str(SERVICES/'applicationcatalogue.cpp'), str(base/'moc.cpp'), '-I', str(SERVICES), '-I', str(ROOT/'shell/plugin/include'), *flags, '-o', str(base/'probe')], check=True)
            (base/'bin').mkdir()
            gio = base/'bin/gio'
            gio.write_text('#!/usr/bin/python3\nimport json,os,sys\nopen(os.environ["LAUNCH_LOG"],"w").write(json.dumps(sys.argv[1:]))\n')
            gio.chmod(0o700)
            env = dict(os.environ, XDG_DATA_HOME=str(base/'data'), XDG_DATA_DIRS=str(base/'system'), LAUNCH_LOG=str(base/'launch'), PATH=str(base/'bin')+':'+os.environ['PATH'])
            result = subprocess.run([str(base/'probe')], env=env, capture_output=True, text=True, check=True, timeout=10)
            self.assertEqual(json.loads(result.stdout), dict(created=True, updated=True, removed=True, lookup=True))
            self.assertEqual(json.loads((base/'launch').read_text()), ['launch', str(base/'data/applications/org.hics.CatalogueFixture.desktop')])

            apps = base/'system/applications'
            apps.mkdir(parents=True)
            for n in range(500):
                (apps/f'org.hics.Bench{n}.desktop').write_text(f'[Desktop Entry]\nType=Application\nName=Benchmark {n}\nExec=/bin/true\n')
            executable=base/'try-exec'
            executable.write_text('#!/bin/sh\n');executable.chmod(0o700)
            (apps/'org.hics.TryExec.desktop').write_text('[Desktop Entry]\nType=Application\nName=TryExec fixture\nExec=/bin/true\nTryExec='+str(executable)+'\n')
            env['BENCH_TRYEXEC']=str(executable)
            benchmark=subprocess.run([str(base/'probe'),'benchmark'],env=env,capture_output=True,text=True,check=True,timeout=15)
            data=json.loads(benchmark.stdout)
            self.assertTrue(data['idle'],data)
            self.assertTrue(data['tryExec'],data)
            self.assertTrue(data['fallback'],data)
            self.assertTrue(data['actions'],data)
            print('Catalogue benchmark (500 apps, 15 scans):',json.dumps(data),flush=True)
