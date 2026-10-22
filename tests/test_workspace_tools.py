"""Native clipboard policies, binding persistence and desktop-session formats."""
import json, os, shlex, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'
class WorkspaceToolsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-workspace-tests-');cls.base=Path(cls.temp.name);cls.binary=cls.base/'probe'
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui','Qt6Qml','Qt6Concurrent','Qt6DBus','libnm'],text=True))
  moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
  subprocess.run([str(moc),str(SERVICES/'workspacetools.hpp'),'-o',str(cls.base/'moc.cpp'),*shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6Qml'],text=True))],check=True)
  subprocess.run(['c++','-std=c++20','-fPIC',str(ROOT/'tests/fixtures/workspace-probe.cpp'),str(SERVICES/'workspacetools.cpp'),str(SERVICES/'workspacestore.cpp'),str(cls.base/'moc.cpp'),'-I',str(SERVICES),*flags,'-o',str(cls.binary)],check=True)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def setUp(self):
  self.case=tempfile.TemporaryDirectory(dir=self.base);self.addCleanup(self.case.cleanup);self.dir=Path(self.case.name)
  for name in ['config','state','data','runtime','bin']:(self.dir/name).mkdir(mode=0o700)
  self.env=dict(os.environ,XDG_CONFIG_HOME=str(self.dir/'config'),XDG_STATE_HOME=str(self.dir/'state'),XDG_DATA_HOME=str(self.dir/'data'),XDG_RUNTIME_DIR=str(self.dir/'runtime'),HYPRLAND_INSTANCE_SIGNATURE='fixture',XDG_CURRENT_DESKTOP='Hyprland',PATH=str(self.dir/'bin')+':'+os.environ['PATH'],HICS_TEST_ROOT=str(self.dir))
  tool=self.dir/'bin/hyprctl';tool.write_text('''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
p=Path(os.environ['HICS_TEST_ROOT'])
with (p/'calls').open('a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
a=sys.argv[1:]
if a==['-j','clients']:print(json.dumps([{'address':'0x1234','mapped':True,'hidden':False,'pinned':False,'class':'org.hics.Fixture','initialClass':'org.hics.Fixture','title':'Document','workspace':{'id':2},'monitor':0,'at':[180,160],'size':[600,400],'floating':True,'fullscreen':0,'focusHistoryID':0}]))
elif a==['-j','monitors']:print(json.dumps([{'id':0,'name':'TEST-1','x':0,'y':0}]))
elif a==['eval','return hyprstack_layouts.mode()']:print('canvas')
elif a==['configerrors']:print('')
else:print('ok')
''');tool.chmod(0o700)
  apps=self.dir/'data/applications';apps.mkdir();(apps/'org.hics.Fixture.desktop').write_text('[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/true "argument with spaces" %U\nStartupWMClass=org.hics.Fixture\n')
  self.config('session',windowTimeout=2,launchDelay=0)
 def probe(self,*args):
  result=subprocess.run([str(self.binary),*map(str,args)],env=self.env,capture_output=True,text=True,timeout=20)
  self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
 def config(self,group,**values):
  result=self.probe('settings',group,json.dumps(values));self.assertNotIn('error',result);return result
 def store(self,text,app='fixture'):return self.probe('clipboard-store',text,'text/plain',app)
 def test_duplicate_pinning_and_clear_preserve_payload_permissions(self):
  first=self.store('first')['entries'][0];self.store('second');entries=self.store('first')['entries'];self.assertEqual(len(entries),2);self.assertEqual(entries[0]['id'],first['id'])
  self.probe('clipboard-pin',first['id']);self.assertEqual(len(self.probe('clipboard-clear','keep')['entries']),1)
  path=self.dir/'state/hics/workspace/clipboard'/first['id'];self.assertEqual(path.stat().st_mode&0o777,0o600)
  self.assertEqual(self.probe('clipboard-clear','all')['entries'],[])
 def test_limits_and_pins(self):
  self.config('clipboard',maxEntries=1);first=self.store('pinned')['entries'][0];self.probe('clipboard-pin',first['id']);self.store('ordinary one');entries=self.store('ordinary two')['entries'];self.assertEqual(len(entries),2);self.assertTrue(entries[0]['pinned']);self.assertNotIn('ordinary one',[e['text'] for e in entries])
 def test_privacy_filters_and_pause(self):
  self.config('clipboard',excludedApps='^secret-app$',excludedText='token=[a-z]+');self.assertFalse(self.store('safe','secret-app')['stored']);self.assertFalse(self.store('token=hidden')['stored']);self.assertTrue(self.store('ordinary')['stored'])
  self.config('clipboard',paused=True);self.assertFalse(self.store('paused')['stored'])
 def test_invalid_regex_does_not_replace_valid_settings(self):
  self.config('clipboard',excludedText='secret');bad=self.probe('settings','clipboard',json.dumps({'excludedText':'['}));self.assertIn('error',bad);self.assertFalse(self.store('secret')['stored'])
 def test_expiry_keeps_pins(self):
  one=self.store('expired')['entries'][0];two=self.store('kept')['entries'][0];self.probe('clipboard-pin',two['id'])
  path=self.dir/'state/hics/workspace/clipboard/index.json';data=json.loads(path.read_text())
  for entry in data['entries']:entry['timestamp']=1
  path.write_text(json.dumps(data));entries=self.probe('clipboard-list')['entries'];self.assertEqual([e['id'] for e in entries],[two['id']]);self.assertFalse((path.parent/one['id']).exists())
 def test_ephemeral_history_uses_runtime(self):
  self.config('clipboard',persistent=False);entry=self.store('temporary')['entries'][0];self.assertTrue((self.dir/'runtime/hics-workspace/clipboard'/entry['id']).exists());self.assertFalse((self.dir/'state/hics/workspace/clipboard').exists())
 def test_chord_normalization_rejects_injection(self):
  self.assertEqual(self.probe('chord','shift + meta + ctrl + t')['chord'],'SUPER + CTRL + SHIFT + T');self.assertIn('error',self.probe('chord','SUPER + X; os.execute("bad")'))
 def catalogue(self):
  actions=[{'id':'Shell: First\n','description':'Shell: First','submap':'','keys':['SUPER + T'],'flags':{}},{'id':'Shell: Second\n','description':'Shell: Second','submap':'','keys':['SUPER + Y'],'flags':{}}]
  (self.dir/'runtime/hics-shortcuts-fixture.json').write_text(json.dumps({'actions':actions}));return actions
 def test_shortcut_conflicts_and_persistence(self):
  actions=self.catalogue();self.assertIn('already assigned',self.probe('shortcut-save',json.dumps(dict(actions[0],keys=['SUPER + Y'])))['error'])
  result=self.probe('shortcut-save',json.dumps(dict(actions[0],keys=['SUPER + SHIFT + T'],flags={'release':True})));self.assertEqual(result['error'],'');saved=result['settings']['overrides'][actions[0]['id']];self.assertEqual(saved['keys'],['SUPER + SHIFT + T']);self.assertTrue(saved['flags']['release'])
  self.assertEqual(self.probe('shortcut-reset',actions[0]['id'])['settings']['overrides'],{})
 def test_snapshot_capture_uses_desktop_entries_and_window_state(self):
  result=self.probe('capture','Work');self.assertEqual(result['error'],'');snapshot=result['preview'];self.assertEqual(snapshot['mode'],'canvas');entry=snapshot['windows'][0];self.assertEqual(entry['command'],['/bin/true','argument with spaces']);self.assertEqual(entry['workspace'],2);self.assertTrue(entry['floating']);path=self.dir/'state/hics/workspace/sessions'/(snapshot['id']+'.json');self.assertEqual(path.stat().st_mode&0o777,0o600)
 def test_restore_running_windows_without_duplicate_launch(self):
  snapshot=self.probe('capture','Work')['preview'];result=self.probe('restore',snapshot['id']);self.assertEqual(result['error'],'');self.assertEqual(result['report'][0]['status'],'Already running');self.assertEqual(result['report'][0]['placement'],'Restored');self.assertIn('workspace=',(self.dir/'calls').read_text())
 def test_gnome_import_is_preview_only_and_keeps_arguments(self):
  directory=self.dir/'config/gnome-session/saved-session';directory.mkdir(parents=True);(directory/'editor.desktop').write_text('[Desktop Entry]\nType=Application\nName=Editor\nExec=/bin/true "saved document" --sm-client-id=session-id\nStartupWMClass=Editor\n')
  result=self.probe('import-desktop','gnome');self.assertEqual(result['error'],'');entry=result['preview']['windows'][0];self.assertEqual(entry['command'],['/bin/true','saved document','--sm-client-id=session-id']);self.assertFalse((self.dir/'state/hics/workspace/sessions').exists())
 def test_kde_import_preserves_restart_command(self):
  (self.dir/'config/ksmserverrc').write_text('[Session: saved at previous logout]\ncount=1\nprogram1=editor\nrestartCommand1=/bin/true,--session,client-token\nclientId1=client-token\n')
  result=self.probe('import-desktop','kde');self.assertEqual(result['error'],'');self.assertEqual(result['preview']['windows'][0]['command'],['/bin/true','--session','client-token'])
 def test_xdg_autostart_is_opt_in_and_desktop_scoped(self):
  path=self.dir/'config/autostart/hics-session-restore.desktop';self.assertFalse(path.exists());self.probe('session-configure',json.dumps({'enabled':True,'startup':'ask'}));self.assertIn('OnlyShowIn=Hyprland;hics;',path.read_text());self.probe('session-configure',json.dumps({'crossDesktop':True}));self.assertNotIn('OnlyShowIn',path.read_text());self.probe('session-configure',json.dumps({'enabled':False}));self.assertFalse(path.exists())
 def test_export_portable_does_not_install_autostart(self):
  snapshot=self.probe('capture','Export')['preview'];directory=self.dir/'portable';result=self.probe('export',snapshot['id'],directory,'portable');self.assertEqual(result['error'],'');self.assertIn('argument with spaces',(directory/'hics-session-1.desktop').read_text());self.assertFalse((self.dir/'config/autostart').exists())

 def test_clear_all_erases_persistent_and_ephemeral_stores(self):
  first=self.store('disk')['entries'][0];self.config('clipboard',persistent=False);second=self.store('runtime')['entries'][0]
  self.probe('clipboard-clear','all');self.assertFalse((self.dir/'state/hics/workspace/clipboard'/first['id']).exists());self.assertFalse((self.dir/'runtime/hics-workspace/clipboard'/second['id']).exists())
 def test_physical_and_media_key_recording(self):
  self.catalogue();self.config('shortcuts',physicalKeys=True)
  self.assertEqual(self.probe('record-key',84,0x12000000,28)['chord'],'SUPER + SHIFT + code:28')
  self.config('shortcuts',physicalKeys=False);self.assertEqual(self.probe('record-key',0x01000072,0,0)['chord'],'XF86AudioRaiseVolume')
 def test_reset_checks_conflicts_with_reassigned_defaults(self):
  actions=self.catalogue();self.assertEqual(self.probe('shortcut-save',json.dumps(dict(actions[0],keys=['SUPER + SHIFT + T'])))['error'],'')
  self.assertEqual(self.probe('shortcut-save',json.dumps(dict(actions[1],keys=['SUPER + T'])))['error'],'')
  self.assertIn('conflicts',self.probe('shortcut-reset',actions[0]['id'])['error'])
 def test_automatic_capture_does_not_replace_the_open_snapshot(self):
  result=self.probe('capture-and-autosave');self.assertEqual(result['error'],'');self.assertEqual(result['preview']['name'],'Manual');self.assertEqual(len(result['snapshots']),2)
 def test_portable_desktop_round_trip_preserves_literal_arguments(self):
  snapshot=self.probe('capture','Arguments')['preview'];expected=['/bin/true','with spaces','quote"','slash\\','100%value','$literal','`literal`']
  snapshot['windows'][0]['command']=expected;self.assertEqual(self.probe('save-preview',json.dumps(snapshot))['error'],'')
  directory=self.dir/'config/gnome-session/saved-session';result=self.probe('export',snapshot['id'],directory,'portable');self.assertEqual(result['error'],'')
  imported=self.probe('import-desktop','gnome');self.assertEqual(imported['error'],'');self.assertEqual(imported['preview']['windows'][0]['command'],expected)
 def test_export_does_not_change_existing_directory_permissions(self):
  snapshot=self.probe('capture','Permissions')['preview'];directory=self.dir/'export';directory.mkdir(mode=0o750)
  self.assertEqual(self.probe('export',snapshot['id'],directory/'session.json')['error'],'');self.assertEqual(directory.stat().st_mode&0o777,0o750)
