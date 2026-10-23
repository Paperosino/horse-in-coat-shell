"""The selected installation prefix must be inherited by Python helpers."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class LauncherPathsTests(unittest.TestCase):
    def test_system_prefix_is_exported_to_helpers_and_shell(self):
        with tempfile.TemporaryDirectory(prefix='hics-launcher-paths-') as directory:
            base=Path(directory);prefix=base/'package';assets=prefix/'shell/assets';assets.mkdir(parents=True)
            (assets/'migrate_branding.py').write_text('')
            report='import os\nprint(os.environ.get("HYPRSTACK_DATA_DIR","missing"))\n'
            for name in ('diagnostics.py','hics_cli.py'):(assets/name).write_text(report)
            qs=prefix/'qs/bin/hics-qs';qs.parent.mkdir(parents=True);qs.write_text('#!/usr/bin/python3\n'+report);qs.chmod(0o700)
            env={k:v for k,v in os.environ.items() if not k.startswith(('HICS_','HYPRSTACK_'))}
            for name in ('hics','hics-doctor','hics-shell'):
                with self.subTest(launcher=name):
                    source=(ROOT/'distribution/bin'/name).read_text().replace('/usr/share/hics',str(prefix))
                    path=base/name;path.write_text(source)
                    result=subprocess.run(['bash',str(path)],env=env,capture_output=True,text=True,check=True,timeout=5)
                    self.assertEqual(result.stdout.strip(),str(prefix))
