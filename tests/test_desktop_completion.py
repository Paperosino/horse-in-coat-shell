"""Data-only appearance imports, private history and validated desktop rules."""
import json,sys,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shell/assets'))
import configuration_manager as config
import desktop_rules as rules
import onboarding_manager as onboarding
class DesktopCompletion(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.cfg=self.root/'config';self.state=self.root/'state';self.cfg.mkdir();self.state.mkdir()
  for module,name,value in [(config,'CONFIG',self.cfg),(config,'STATE',self.state),(config,'HISTORY',self.state/'history'),(config,'PROFILES',self.root/'profiles'),(config,'PREFS',self.cfg/'history.json'),(config,'JOURNAL',self.state/'pending.json'),(rules,'CONFIG',self.cfg),(rules,'APP',self.cfg/'application-rules.json'),(rules,'DEVICE',self.cfg/'device-rules.json'),(rules,'GENERATED',self.cfg/'rules.lua'),(onboarding,'PREFS',self.cfg/'onboarding.json')]:
   p=patch.object(module,name,value);p.start();self.addCleanup(p.stop)
 def write_preview(self,payload):
  journal={'token':'fixture','name':'Fixture','deadline':time.time()+30,'deadlineMonotonic':time.monotonic()+30,'shellPid':None,'shellStart':None,**payload}
  config.atomic_json(config.JOURNAL,journal)
 def test_history_excludes_credentials_and_clipboard_and_deduplicates(self):
  (self.cfg/'shell.json').write_text('{"appearance":{"scale":1}}');(self.cfg/'assistant-key.json').write_text('{"apiKey":"secret"}');(self.state/'clipboard').mkdir();(self.state/'clipboard/payload').write_text('private')
  first=config.snapshot();self.assertEqual(config.snapshot(),first);data=config.load_snapshot(config.HISTORY/(first+'.json.gz'));self.assertIn('shell.json',data['files']);self.assertFalse(any('assistant' in k or 'clipboard' in k for k in data['files']));self.assertEqual((config.HISTORY/(first+'.json.gz')).stat().st_mode&0o777,0o600)
 def test_import_cannot_execute_lua_or_write_arbitrary_paths(self):
  for name in ('../elsewhere.json','assistant-key.json','keyboard.lua','rules.lua'):
   with self.assertRaises(ValueError):config.validate_bundle({'version':1,'files':{name:'{}'}})
 def test_preview_reverts_only_its_own_changes(self):
  before={'appearance':{'scale':1,'highContrast':False},'general':{'language':'ru_RU'}};after={'appearance':{'scale':1.25,'highContrast':False},'general':{'language':'ru_RU'}};current={'appearance':{'scale':1.25,'highContrast':True},'general':{'language':'en_US'}}
  merged=config.merge_revert(before,after,current);self.assertEqual(merged['appearance'],{'scale':1,'highContrast':True});self.assertEqual(merged['general']['language'],'en_US')
 def test_invalid_history_preferences_preserve_previous_policy(self):
  config.atomic_json(config.PREFS,{'keep':20})
  with self.assertRaises(ValueError):config.dispatch('configure',{'keep':-1})
  self.assertEqual(config.read_json(config.PREFS)['keep'],20)
 def test_profile_save_inspect_preview_and_rollback(self):
  (self.cfg/'shell.json').write_text('{"appearance":{"scale":1}}');config.dispatch('save-profile',{'name':'Original'});profile=config.profiles()[0];(self.cfg/'shell.json').write_text('{"appearance":{"scale":1.25}}')
  with patch.object(config,'apply_files',wraps=lambda files,*args: [config.write_text(config.target(k),v) for k,v in files.items()]):
   data=config.dispatch('preview-profile',{'id':profile['id']});self.assertEqual(json.loads((self.cfg/'shell.json').read_text())['appearance']['scale'],1)
   config.dispatch('revert',{'token':data['pending']['token']})
  self.assertEqual(json.loads((self.cfg/'shell.json').read_text())['appearance']['scale'],1.25)
 def test_rollback_removes_files_absent_before_trial_and_keeps_user_edits(self):
  for edited in (False,True):
   path=self.cfg/'dock.json';path.unlink(missing_ok=True)
   self.write_preview({'before':{'dock.json':None},'applied':{'dock.json':'{"enabled":false}'},'absent':['dock.json']})
   path.write_text('{"enabled":false,"userEdit":true}' if edited else '{"enabled":false}')
   config.rollback(False)
   if edited:self.assertTrue(json.loads(path.read_text())['userEdit'])
   else:self.assertFalse(path.exists())
 def test_preview_records_physical_absence_even_for_synthesized_defaults(self):
  with patch.object(config,'apply_files',side_effect=lambda files,*args:[config.write_text(config.target(k),v) for k,v in files.items()]),patch.object(config,'runtime',return_value=self.root/'runtime'):
   data=config.dispatch('preset',{'id':'classic'})
   journal=config.read_json(config.JOURNAL)
   self.assertIn('dock.json',journal['absent'])
   config.rollback(False)
  self.assertFalse((self.cfg/'dock.json').exists());self.assertFalse((self.cfg/'shell.json').exists())
 def test_rollback_does_not_write_defaults_twice_over_late_edit(self):
  path=self.cfg/'dock.json';path.write_text('{"enabled":false}')
  self.write_preview({'before':{'dock.json':None},'applied':{'dock.json':'{"enabled":false}'},'absent':['dock.json']})
  original=config.apply_files
  def apply_then_edit(files,runtime_apply=True,*args):
   original(files,runtime_apply,*args)
   if not runtime_apply:path.write_text('{"userEdit":true}')
  with patch.object(config,'apply_files',side_effect=apply_then_edit):config.rollback()
  self.assertEqual(json.loads(path.read_text()),{'userEdit':True})
 def test_failed_runtime_rollback_still_restores_absence_and_reports_error(self):
  path=self.cfg/'dock.json';path.write_text('{"enabled":false}')
  self.write_preview({'before':{'dock.json':None},'applied':{'dock.json':'{"enabled":false}'},'absent':['dock.json']})
  original=config.apply_files
  def fail_runtime(files,runtime_apply=True,*args):
   if runtime_apply:raise ValueError('Fixture compositor unavailable')
   original(files,False,*args)
  with patch.object(config,'apply_files',side_effect=fail_runtime):config.rollback()
  self.assertFalse(path.exists());self.assertFalse(config.JOURNAL.exists())
  self.assertIn('Fixture compositor unavailable',config.read_json(self.state/'configuration-recovery-warning.json')['warning'])
 def test_rollback_skips_unsafe_changed_sections_and_restores_other_files(self):
  import os
  bad=self.cfg/'dock.json';good=self.cfg/'shell.json';external=self.root/'outside';external.write_text('{}')
  for kind in ('fifo','symlink','oversize','array','invalid-json'):
   with self.subTest(kind=kind):
    bad.unlink(missing_ok=True);good.write_text('{"trial":true}')
    if kind=='fifo':os.mkfifo(bad)
    elif kind=='symlink':bad.symlink_to(external)
    elif kind=='oversize':
     with bad.open('wb') as stream:stream.truncate(2*1024*1024)
    else:bad.write_text('[]' if kind=='array' else '{invalid')
    inode=bad.lstat().st_ino
    self.write_preview({'before':{'dock.json':'{"enabled":true}','shell.json':'{"original":true}'},'applied':{'dock.json':'{}','shell.json':'{"trial":true}'}})
    config.rollback(False)
    self.assertEqual(bad.lstat().st_ino,inode);self.assertEqual(external.read_text(),'{}')
    self.assertEqual(json.loads(good.read_text()),{'original':True});self.assertFalse(config.JOURNAL.exists())
    self.assertIn('dock.json',config.read_json(self.state/'configuration-recovery-warning.json')['warning'])
 def test_invalid_history_policy_never_writes_checkpoint_or_overwrites_policy(self):
  raw=b'{invalid';config.PREFS.write_bytes(raw);inode=config.PREFS.stat().st_ino
  with self.assertRaises(ValueError):config.dispatch('configure',{'keep':20})
  with self.assertRaises(ValueError):config.snapshot('Must not be saved',False)
  self.assertEqual(config.PREFS.read_bytes(),raw);self.assertEqual(config.PREFS.stat().st_ino,inode)
  self.assertFalse(config.HISTORY.exists())
  with patch.object(config,'runtime',return_value=self.root/'run'):
   state=config.state();self.assertFalse(state['settingsValid']);self.assertFalse(state['settings']['enabled'])
 def test_nonregular_history_policy_and_warning_remain_readable_as_diagnostics(self):
  import os
  os.mkfifo(config.PREFS)
  warning=self.state/'configuration-recovery-warning.json';warning.write_text('{"warning":[]}')
  with patch.object(config,'runtime',return_value=self.root/'run'):
   state=config.state();self.assertFalse(state['settingsValid']);self.assertIsInstance(state['recoveryWarning'],str)
  self.assertTrue(__import__('stat').S_ISFIFO(config.PREFS.lstat().st_mode))
 def test_malformed_preview_metadata_and_sections_are_preserved(self):
  cases=[{'deadlineMonotonic':'bad'},{'deadline':True},{'deadline':10**400},{'shellPid':True},{'shellStart':[]},{'before':{}},{'absent':['other.json']},{'applied':{'../escape.json':'{}'},'before':{'../escape.json':None}},{'before':{'dock.json':'[]'}}]
  for changes in cases:
   with self.subTest(changes=changes):
    self.write_preview({'before':{'dock.json':None},'applied':{'dock.json':'{}'},**changes})
    raw=config.JOURNAL.read_bytes()
    with self.assertRaises(ValueError):config.rollback(False)
    self.assertEqual(config.JOURNAL.read_bytes(),raw)
    with patch.object(config,'runtime',return_value=self.root/'run'):self.assertFalse(config.state()['pendingValid'])
 def test_preview_fifo_is_bounded_and_not_overwritten(self):
  import os,stat
  os.mkfifo(config.JOURNAL)
  with self.assertRaises(ValueError):config.rollback(False)
  with patch.object(config,'runtime',return_value=self.root/'run'):self.assertFalse(config.state()['pendingValid'])
  self.assertTrue(stat.S_ISFIFO(config.JOURNAL.lstat().st_mode))
 def test_oversize_preview_is_rejected_before_configuration_changes(self):
  with patch.object(config,'MAX_PREVIEW_BYTES',1):
   with self.assertRaisesRegex(ValueError,'journal exceeds'):config.dispatch('preset',{'id':'classic'})
  self.assertFalse(config.JOURNAL.exists());self.assertFalse((self.cfg/'dock.json').exists());self.assertFalse((self.cfg/'shell.json').exists())
 def test_partial_disk_write_failure_keeps_journal_and_retry_restores_absence(self):
  dock=self.cfg/'dock.json';shell=self.cfg/'shell.json';dock.write_text('{"trial":true}');shell.write_text('{"trial":true}')
  self.write_preview({'before':{'dock.json':None,'shell.json':'{"original":true}'},'applied':{'dock.json':'{"trial":true}','shell.json':'{"trial":true}'},'absent':['dock.json']})
  saved=config.JOURNAL.read_bytes();original=config.write_text
  def fail_second(path,text):
   if path==shell:raise OSError(28,'No space left on device')
   original(path,text)
  with patch.object(config,'write_text',side_effect=fail_second):
   with self.assertRaises(OSError):config.rollback(False)
  self.assertEqual(config.JOURNAL.read_bytes(),saved);self.assertEqual(dock.read_text(),'{}')
  config.rollback(False)
  self.assertFalse(dock.exists());self.assertEqual(json.loads(shell.read_text()),{'original':True});self.assertFalse(config.JOURNAL.exists())
 def test_failed_warning_file_and_stderr_keep_diagnostic_in_memory(self):
  class BrokenLog:
   def write(self,*args):raise OSError(28,'No space left on device')
   def flush(self):pass
  source='Fixture diagnostics write failed'
  self.addCleanup(lambda:config.WARNING_IO_FAILURES.pop(source,None));self.addCleanup(lambda:config.PENDING_WARNINGS.pop(source,None))
  with patch.object(config,'atomic_json',side_effect=OSError(28,'No space left on device')),patch.object(config.sys,'stderr',BrokenLog()):
   config.persist_warning('Fixture section preserved',source)
  self.assertIn('No space left',config.WARNING_IO_FAILURES[source]);self.assertEqual(config.PENDING_WARNINGS[source],'Fixture section preserved')
  config.persist_warning('Fixture section preserved',source)
  self.assertNotIn(source,config.WARNING_IO_FAILURES);self.assertNotIn(source,config.PENDING_WARNINGS)
  self.assertEqual(config.read_json(self.state/'configuration-recovery-warning.json')['warning'],'Fixture section preserved')
 def test_failed_warning_temporary_events_do_not_retrigger_capture(self):
  import struct
  def event(wd,name):
   raw=name.encode()+b'\0';return struct.pack('iIII',wd,0x100,0,len(raw))+raw
  paths={1:self.state,2:self.cfg}
  own=event(1,'.configuration-recovery-warning.jsonabc123')
  self.assertFalse(config.configuration_event_relevant(own+own,paths))
  self.assertTrue(config.configuration_event_relevant(event(1,'configuration-recovery-warning.json'),paths))
  self.assertTrue(config.configuration_event_relevant(own+event(2,'dock.json'),paths))
  self.assertTrue(config.configuration_event_relevant(event(2,'.configuration-recovery-warning.jsonabc'),paths))
  self.assertTrue(config.configuration_event_relevant(struct.pack('iIII',-1,0x4000,0,0),paths))
  self.assertTrue(config.configuration_event_relevant(own[:-1],paths))
 def test_bad_history_archives_do_not_hide_valid_checkpoint(self):
  import gzip,os
  good=config.snapshot('Good');path=config.HISTORY/(good+'.json.gz');payload=json.loads(gzip.decompress(path.read_bytes()))
  payload['created']=10**400;(config.HISTORY/'huge.json.gz').write_bytes(gzip.compress(json.dumps(payload).encode()))
  (config.HISTORY/'corrupt.json.gz').write_bytes(b'\x1f\x8b'+b'x'*30)
  os.mkfifo(config.HISTORY/'fifo.json.gz');(config.HISTORY/'link.json.gz').symlink_to(path)
  self.assertEqual([row['id'] for row in config.history()],[good])
 def test_snapshot_checksum_and_file_identity_are_verified(self):
  import gzip
  good=config.snapshot('Good');path=config.HISTORY/(good+'.json.gz');raw=path.read_bytes();payload=json.loads(gzip.decompress(raw))
  payload['files']['dock.json']='{"enabled":false}';path.write_bytes(gzip.compress(json.dumps(payload).encode()))
  with self.assertRaisesRegex(ValueError,'checksum'):config.load_snapshot(path)
  path.write_bytes(raw);other=config.HISTORY/'00000000-0000-0000-0000-000000000000.json.gz';other.write_bytes(raw)
  self.assertEqual([row['id'] for row in config.history()],[good])
 def test_rules_escape_application_names_and_validate_effects(self):
  rule=rules.validate_rule({'id':'fixture','application':'app.name','name':'App','floating':True,'opacity':.8,'idleInhibit':'focus'});text=rules.rule_lua(rule)
  self.assertIn('app\\\\.name',text);self.assertIn('idle_inhibit',text)
  for invalid in ({'application':'a','opacity':float('nan')},{'application':'a','workspace':0},{'application':'a','regex':True,'title':'['},{'application':'a','idleInhibit':'exec'}):
   with self.assertRaises(ValueError):rules.validate_rule(invalid)
 def test_initial_title_rules_do_not_match_other_application_windows(self):
  rule=rules.validate_rule({'id':'dialog','application':'app.name','initialTitle':'Open (file)','mode':'stacking','titlebar':'hide'})
  text=rules.rule_lua(rule)
  self.assertIn('initial_title',text);self.assertIn('app\\\\.name',text);self.assertNotIn('["title"]',text)
  with self.assertRaises(ValueError):rules.validate_rule(dict(rule,initialTitle='bad\nvalue'))
 def test_tablet_mapping_validates_vectors_and_generates_real_lua_tables(self):
  device={'name':'fixture-pen','values':{'output':'DP-1','transform':3,'relative_input':False,'active_area_size':[152,95],'region_position':[-10,20]}}
  text=rules.regenerate([], [device]);self.assertIn('["active_area_size"]={152,95}',text)
  for values in ({'output':'DP-1;command'},{'active_area_size':[-1,2]},{'region_size':[float('inf'),0]},{'region_position':[1]},{'transform':8}):
   with self.assertRaises(ValueError):rules.validate_device({'name':'fixture-pen','values':values})
 def test_mode_rules_are_registered_with_typed_effects(self):
  rule=rules.validate_rule({'id':'scoped','application':'Code','mode':'stacking','titlebar':'hide','decorate':True,'borderSize':0,'rounding':12,'noShadow':True,'keepAspectRatio':True,'noInitialFocus':True,'matchXwayland':False})
  text=rules.rule_lua(rule)
  self.assertIn('application_rule("stacking"',text)
  for effect in ('hyprbars:no_bar','border_size','rounding','keep_aspect_ratio','no_initial_focus','xwayland'):self.assertIn(effect,text)
  for key,value in [('mode','unknown'),('titlebar','execute'),('noShadow',1),('borderSize',True),('rounding',100),('matchModal','yes')]:
   with self.assertRaises(ValueError):rules.validate_rule({'application':'app',key:value})
 def test_rule_edit_preserves_priority_and_explicit_move_changes_it(self):
  first={'id':'first','application':'one'};second={'id':'second','application':'two'}
  with patch.object(rules,'save') as save,patch.object(rules,'state',return_value={}),patch.object(rules,'read_json',return_value={'rules':[first,second]}):
   rules.dispatch('save-rule',dict(first,title='new'));self.assertEqual([r['id'] for r in save.call_args.args[0]],['first','second'])
   rules.dispatch('move-rule',{'id':'first','direction':1});self.assertEqual([r['id'] for r in save.call_args.args[0]],['second','first'])
 def test_device_limits_do_not_accept_commands(self):
  rules.validate_device({'name':'mouse','values':{'sensitivity':.5,'natural_scroll':True}})
  for values in ({'sensitivity':2},{'enabled':False},{'kb_layout':'us;os.execute("x")'},{'repeat_delay':True}):
   with self.assertRaises(ValueError):rules.validate_device({'name':'keyboard','values':values})
 def test_setup_skip_and_replay_are_resumable(self):
  with patch.object(onboarding,'directory',return_value=self.root/'wallpapers'):
   self.assertEqual(onboarding.state()['settings']['state'],'new');onboarding.dispatch('configure',{'step':4});onboarding.dispatch('skip',{})
   self.assertFalse(onboarding.state()['settings']['autoShow']);self.assertEqual(onboarding.state()['settings']['step'],4)
   onboarding.dispatch('configure',{'autoShow':True});self.assertEqual(onboarding.state()['settings']['state'],'new')
 def test_checkpoint_resets_sections_created_later(self):
  checkpoint=config.snapshot();data=config.load_snapshot(config.HISTORY/(checkpoint+'.json.gz'))
  self.assertEqual(data['files']['dock.json'],'{}');self.assertIn('keyboard.lua',data['files'])
 def test_portable_wallpaper_checksum_and_signature(self):
  p=patch.object(config,'DATA',self.root/'data');p.start();self.addCleanup(p.stop)
  image=self.root/'example.jpg';image.write_bytes(bytes([255,216,255])+b'example')
  bundle={'version':1,'files':{'state/wallpaper/path.txt':str(image)}};packed=config.pack_wallpaper(bundle);image.unlink();unpacked=config.unpack_wallpaper(packed)
  self.assertTrue(Path(unpacked['files']['state/wallpaper/path.txt']).is_file())
  packed['wallpaperAsset']['sha256']='0'*64
  with self.assertRaises(ValueError):config.unpack_wallpaper(packed)
 def test_diagnostics_redacts_values_without_corrupting_json(self):
  import desktop_diagnostics as diagnostics
  with patch.object(diagnostics,'checks',return_value=[{'detail':'token=secret-value'}]),patch.object(diagnostics,'capture',return_value=''):
   result=diagnostics.report();self.assertEqual(result['checks'][0]['detail'],'token=[redacted]')
 def test_wallpaper_conversion_failure_keeps_partial_images_out_of_gallery(self):
  import subprocess
  with patch.object(onboarding,'directory',return_value=self.root/'wallpapers'):
   originals=self.root/'wallpapers/.originals';originals.mkdir(parents=True)
   (originals/'adwaita-d.jxl').write_bytes(b'original')
   def fail(*args,**kwargs):
    (originals.parent/'adwaita-d.part.jpg').write_bytes(b'incomplete')
    raise subprocess.CalledProcessError(1,['ffmpeg'])
   with patch.object(onboarding.subprocess,'run',side_effect=fail):
    with self.assertRaises(subprocess.CalledProcessError):onboarding.download()
   self.assertFalse((originals.parent/'adwaita-d.part.jpg').exists())
   self.assertEqual(onboarding.state()['wallpapers'],[])
if __name__=='__main__':unittest.main()
