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
 def test_rules_escape_application_names_and_validate_effects(self):
  rule=rules.validate_rule({'id':'fixture','application':'app.name','name':'App','floating':True,'opacity':.8,'idleInhibit':'focus'});text=rules.rule_lua(rule)
  self.assertIn('app\\\\.name',text);self.assertIn('idle_inhibit',text)
  for invalid in ({'application':'a','opacity':float('nan')},{'application':'a','workspace':0},{'application':'a','regex':True,'title':'['},{'application':'a','idleInhibit':'exec'}):
   with self.assertRaises(ValueError):rules.validate_rule(invalid)
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
