"""Panel persistence, recovery boundaries and real isolated worker capabilities."""
import importlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shell/assets'))
class DesktopCompletion(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
  self.env=patch.dict(os.environ,{f'XDG_{key}_HOME':str(self.base/key.lower()) for key in ('CONFIG','STATE','DATA')});self.env.start();self.addCleanup(self.env.stop)
  for name in ('feature_common','panel_manager','plugin_manager','extension_recovery','isolated_extension'):
   module=importlib.import_module(name);setattr(self,name,importlib.reload(module))
 def test_independent_panel_layers_and_undo(self):
  manager=self.panel_manager
  state=manager.apply('add',payload={'screen':'TEST-1'});first=state['panels'][0]
  state=manager.apply('add',payload={'screen':'TEST-1'});second=state['panels'][1]
  path=manager.layer(first);config=json.loads(path.read_text());config['bar']['entries']=[{'id':'clock','enabled':True}];path.write_text(json.dumps(config))
  manager.apply('update',first['id'],{'edge':'top','autoHide':True})
  self.assertEqual(json.loads(path.read_text())['bar']['entries'],[{'id':'clock','enabled':True}]);self.assertFalse(json.loads(path.read_text())['bar']['persistent'])
  self.assertTrue(json.loads(manager.layer(second).read_text())['bar']['persistent'])
  manager.apply('remove',first['id']);restored=manager.apply('restore',first['id']);self.assertEqual(len(restored['panels']),2)
  before=manager.PATH.read_bytes()
  with self.assertRaises(ValueError):manager.apply('update',first['id'],{'thickness':10000})
  self.assertEqual(manager.PATH.read_bytes(),before)
 def test_clean_restart_and_crash_recovery(self):
  recovery=self.extension_recovery;recovery.begin();recovery.finish(0);recovery.begin()
  self.assertFalse(self.feature_common.read_json(recovery.CONFIG/'plugins.json').get('recoveryMode',False))
  recovery.finish(-11);recovery.begin();prefs=self.feature_common.read_json(recovery.CONFIG/'plugins.json')
  self.assertTrue(prefs['recoveryMode']);self.assertEqual(prefs['recoveryAllow'],{})
 def test_extension_marker_fifo_never_blocks_and_disables_extensions(self):
  r=self.extension_recovery;r.MARKER.parent.mkdir(parents=True);os.mkfifo(r.MARKER)
  r.begin()
  self.assertTrue(self.feature_common.read_json(r.CONFIG/'plugins.json')['recoveryMode'])
  self.assertTrue(r.MARKER.is_file());r.finish(0)
 def test_extension_marker_symlink_never_reads_or_modifies_target(self):
  r=self.extension_recovery;r.MARKER.parent.mkdir(parents=True)
  external=self.base/'external';external.write_text('{"clean":true}')
  r.MARKER.symlink_to(external);r.begin()
  self.assertTrue(self.feature_common.read_json(r.CONFIG/'plugins.json')['recoveryMode'])
  self.assertEqual(external.read_text(),'{"clean":true}');self.assertFalse(r.MARKER.is_symlink())
 def test_extension_marker_oversize_fails_closed(self):
  r=self.extension_recovery;r.MARKER.parent.mkdir(parents=True)
  with r.MARKER.open('wb') as stream:stream.truncate(16*1024*1024)
  r.begin();self.assertTrue(self.feature_common.read_json(r.CONFIG/'plugins.json')['recoveryMode'])
 def test_extension_marker_invalid_schema_fails_closed(self):
  r=self.extension_recovery
  for record in ({'clean':'false','boot':'x'},{'clean':True,'boot':[]},{'clean':False,'boot':'x','exitCode':{}}):
   with self.subTest(record=record):
    self.feature_common.atomic_json(r.MARKER,record)
    r.begin();self.assertTrue(self.feature_common.read_json(r.CONFIG/'plugins.json')['recoveryMode'])
 def test_widget_placement_does_not_replace_settings(self):
  manager=self.plugin_manager;manager.atomic_json(manager.PREFS,{'settings':{'system-monitor':{'refresh':5}}})
  manager.desktop_layout('system-monitor',{'screen':'TEST-1','geometry':{'x':48,'y':64,'locked':True}})
  manager.desktop_layout('system-monitor',{'screen':'TEST-2','geometry':{'x':128,'width':320}})
  prefs=manager.read_json(manager.PREFS);self.assertEqual(prefs['settings']['system-monitor']['refresh'],5)
  self.assertEqual(prefs['desktopLayout']['system-monitor']['TEST-1']['x'],48)
  self.assertEqual(prefs['desktopLayout']['system-monitor']['TEST-2']['x'],128)
  with self.assertRaises(ValueError):manager.desktop_layout('system-monitor',{'screen':'TEST-1','geometry':{'x':float('nan')}})
 def test_real_sandbox_denies_home_bus_and_network(self):
  worker=self.base/'worker.py';secret=self.base/'secret';secret.write_text('host-only')
  worker.write_text('''import json,os,socket
from pathlib import Path
assert not Path(%r).exists()
assert not os.environ.get('DBUS_SESSION_BUS_ADDRESS')
try:
 socket.create_connection(('1.1.1.1',53),timeout=.2)
 raise AssertionError('network escaped')
except OSError:pass
Path('/data/counter').write_text('private')
print(json.dumps({'slots':{'desktopWidget':[{'type':'label','text':'sandbox passed'}]}}))
'''%str(secret))
  command=self.isolated_extension.sandbox_command({'path':str(self.base),'worker':str(worker),'id':'fixture','networkRequested':False})
  # The plugin itself is readable, so use a separate host path as secret.
  with tempfile.NamedTemporaryFile(prefix='hics-host-secret-') as outside:
   worker.write_text(worker.read_text().replace(str(secret),outside.name))
   result=subprocess.run(command,capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['slots']['desktopWidget'][0]['text'],'sandbox passed')
  self.assertEqual((self.feature_common.STATE/'plugins/fixture/counter').read_text(),'private')
 def test_declarative_protocol_rejects_executable_properties(self):
  validate=self.isolated_extension.validate_state
  for row in ({'type':'label','text':'x','onClicked':'exec()'},{'type':'progress','value':float('nan')},{'type':'toggle','value':'true'}):
   with self.assertRaises(ValueError):validate({'slots':{'desktopWidget':[row]}})
if __name__=='__main__':unittest.main()
