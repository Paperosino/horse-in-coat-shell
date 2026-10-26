"""Session entry point imports environment before starting all core services."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SessionActivation(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);bin=self.base/'bin';bin.mkdir();self.log=self.base/'calls'
  (self.base/'shell/assets').mkdir(parents=True);(self.base/'shell/assets/migrate_branding.py').touch()
  tool='''#!/usr/bin/python3
import os,json,sys
from pathlib import Path
with open(os.environ['HICS_SESSION_TEST_LOG'],'a') as out:out.write(json.dumps([Path(sys.argv[0]).name,*sys.argv[1:]])+'\\n')
'''
  for name in ('systemctl','dbus-update-activation-environment','python3','hyprctl'):
   file=bin/name;file.write_text(tool);file.chmod(0o755)
  self.env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],HICS_SESSION_TEST_LOG=str(self.log),HICS_DATA_DIR=str(self.base),XDG_CONFIG_HOME=str(self.base/'config'),XDG_STATE_HOME=str(self.base/'state'),HYPRLAND_INSTANCE_SIGNATURE='fixture',WAYLAND_DISPLAY='wayland-fixture')
 def run_entry(self,action):
  result=subprocess.run(['bash',str(ROOT/'distribution/bin/hics-session'),action],env=self.env,text=True,capture_output=True,timeout=5)
  calls=[json.loads(row) for row in self.log.read_text().splitlines()] if self.log.exists() else []
  return result,calls
 def test_start_imports_environment_and_activates_core_helpers_before_shell(self):
  result,calls=self.run_entry('start');self.assertEqual(result.returncode,0,result.stderr)
  imported=next(i for i,c in enumerate(calls) if c[:3]==['systemctl','--user','import-environment'])
  helpers=['systemctl','--user','start','hics-desktop.service','hics-displays.service','hics-configuration.service']
  shell=['systemctl','--user','start','hic-session.service']
  self.assertLess(imported,calls.index(helpers));self.assertLess(calls.index(helpers),calls.index(shell))
  self.assertIn(['systemctl','--user','enable','hic-session.service','hics-desktop.service','hics-displays.service','hics-configuration.service'],calls)
  self.assertFalse(any('hics-screen-reader.service' in call or 'mask' in call for call in calls))
 def test_shell_restart_keeps_running_display_rollback_helpers(self):
  result,calls=self.run_entry('restart');self.assertEqual(result.returncode,0,result.stderr)
  self.assertIn(['systemctl','--user','restart','hic-session.service'],calls)
  self.assertFalse(any('restart' in c and any(unit in c for unit in ('hics-displays.service','hics-configuration.service','hics-desktop.service')) for c in calls))
 def test_no_compositor_environment_does_not_start_anything(self):
  self.env.pop('WAYLAND_DISPLAY');result,calls=self.run_entry('start');self.assertNotEqual(result.returncode,0);self.assertEqual(calls,[])
