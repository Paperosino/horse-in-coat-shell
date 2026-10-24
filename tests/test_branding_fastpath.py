"""The CLI migrates once, rechecks changed user config, and skips idle scans."""
import os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class BrandingFastPath(unittest.TestCase):
 def test_success_marker_skips_interpreter_on_second_launch(self):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);assets=base/'data/shell/assets';assets.mkdir(parents=True);(assets/'hyprland').mkdir()
   shutil.copy2(ROOT/'shell/assets/migrate_branding.py',assets/'migrate_branding.py')
   (assets/'hyprland/shortcuts.lua').touch();(assets/'hics_cli.py').write_text('raise SystemExit(0)\n')
   bins=base/'bin';bins.mkdir();log=base/'calls';wrapper=bins/'python3'
   wrapper.write_text('#!/bin/bash\nif [[ $1 == */migrate_branding.py ]]; then printf x >> "$HICS_TEST_MIGRATIONS";fi\nexec /usr/bin/python3 "$@"\n');wrapper.chmod(0o700)
   env=dict(os.environ,HOME=str(base),HICS_DATA_DIR=str(base/'data'),HICS_TEST_MIGRATIONS=str(log),XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'user-data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),PATH=str(bins)+':'+os.environ['PATH'])
   for _ in range(2):subprocess.run(['bash',str(ROOT/'distribution/bin/hics'),'--help'],env=env,capture_output=True,check=True)
   self.assertEqual(log.read_text(),'x')
   marker=base/'state/hics/migrations/branding-v2';self.assertTrue(marker.exists())
   main=base/'config/hypr/hyprland.lua';main.parent.mkdir(parents=True);main.write_text('-- updated config\n')
   os.utime(main,ns=(marker.stat().st_mtime_ns+1,marker.stat().st_mtime_ns+1))
   subprocess.run(['bash',str(ROOT/'distribution/bin/hics'),'--help'],env=env,capture_output=True,check=True)
   self.assertEqual(log.read_text(),'xx');self.assertIn('hics-shortcut-editor',main.read_text())
