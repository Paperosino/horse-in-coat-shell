"""A fresh HICS login preserves other compositor setups and existing preferences."""
import importlib.util, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hics_bootstrap',ROOT/'shell/assets/session_bootstrap.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)
class SessionBootstrap(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
  self.data=self.base/'data';self.config=self.base/'config'
  default=self.data/'defaults/hics';default.mkdir(parents=True)
  (default/'hypr-user.lua').write_text('-- layouts hook\n')
  (default/'shell.json').write_text('{"general":{"language":"ru_RU"}}')
  self.shipped=self.data/'shell/assets/hyprland/config';(self.shipped/'scheme').mkdir(parents=True)
  (self.shipped/'hyprland.lua').write_text('-- managed root\n')
  (self.shipped/'scheme/default.lua').write_text('return {surface="101010"}\n')
 def test_fresh_user_gets_ready_session_without_creating_unrelated_hypr_dir(self):
  env,entry=bootstrap.prepare(self.data,self.config)
  self.assertEqual(entry,self.config/'hics/hypr/hyprland.lua')
  self.assertEqual(env['HICS_HYPR_CONFIG_DIR'],str(self.config/'hics/hypr'))
  self.assertTrue((self.config/'hics/hypr/scheme/current.lua').is_file())
  self.assertTrue((self.config/'hics/hypr-user.lua').is_file())
  self.assertFalse((self.config/'hypr').exists())
 def test_existing_other_hyprland_configuration_is_untouched(self):
  original=self.config/'hypr/hyprland.lua';original.parent.mkdir(parents=True)
  original.write_text('hl.monitor({output="DP-1",mode="2560x1440@165"})\n')
  before=original.stat();content=original.read_bytes()
  bootstrap.prepare(self.data,self.config)
  self.assertEqual(original.read_bytes(),content)
  self.assertEqual(original.stat().st_mtime_ns,before.st_mtime_ns)
  self.assertEqual(list(original.parent.iterdir()),[original])
 def test_existing_managed_hics_session_retains_local_monitor_configuration(self):
  original=self.config/'hypr/hyprland.lua';original.parent.mkdir(parents=True)
  text='hics_shortcuts={}\nrequire("hypr-user")\nrequire("hyprland.execs")\n-- monitor 165 Hz\n';original.write_text(text)
  env,entry=bootstrap.prepare(self.data,self.config)
  self.assertEqual(entry,original);self.assertEqual(env['HICS_HYPR_CONFIG_DIR'],str(original.parent))
  self.assertEqual(original.read_text(),text)
 def test_repeat_preserves_values_and_mtime(self):
  bootstrap.prepare(self.data,self.config)
  settings=self.config/'hics/shell.json';settings.write_text('{"custom":true}')
  before=settings.stat()
  bootstrap.prepare(self.data,self.config)
  self.assertEqual(settings.read_text(),'{"custom":true}')
  self.assertEqual(settings.stat().st_mtime_ns,before.st_mtime_ns)
 def test_default_target_symlink_is_not_followed(self):
  (self.config/'hics').mkdir(parents=True);outside=self.base/'outside';outside.write_text('preserve')
  (self.config/'hics/shell.json').symlink_to(outside)
  bootstrap.prepare(self.data,self.config);self.assertEqual(outside.read_text(),'preserve')
 def test_bad_other_config_does_not_block_new_session(self):
  original=self.config/'hypr/hyprland.lua';original.parent.mkdir(parents=True);original.write_bytes(b'\xff')
  env,_=bootstrap.prepare(self.data,self.config)
  self.assertEqual(env['HICS_HYPR_CONFIG_DIR'],str(self.config/'hics/hypr'))
  self.assertEqual(original.read_bytes(),b'\xff')
 def test_missing_package_defaults_fail_with_explanation(self):
  (self.shipped/'hyprland.lua').unlink()
  with self.assertRaisesRegex(ValueError,'reinstall'):bootstrap.prepare(self.data,self.config)
 def test_relative_xdg_directory_is_rejected(self):
  with self.assertRaises(ValueError):bootstrap.prepare(self.data,Path('relative'))
 def test_failed_publish_never_leaves_a_partial_default(self):
  target=self.config/'hics/hypr-user.lua'
  with patch.object(bootstrap.os,'link',side_effect=OSError('injected failure')):
   with self.assertRaises(OSError):bootstrap.copy_missing(self.data/'defaults/hics/hypr-user.lua',target)
  self.assertFalse(target.exists())
  self.assertEqual(list(target.parent.iterdir()),[])
 def test_concurrent_preparation_preserves_complete_files(self):
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=4) as pool:
   results=list(pool.map(lambda _:bootstrap.prepare(self.data,self.config),range(8)))
  self.assertTrue(all(entry==self.config/'hics/hypr/hyprland.lua' for _,entry in results))
  self.assertEqual((self.config/'hics/hypr-user.lua').read_text(),'-- layouts hook\n')
  self.assertEqual((self.config/'hics/shell.json').read_text(),'{"general":{"language":"ru_RU"}}')
 def test_wrapper_finds_its_own_install_prefix_with_spaces(self):
  import shutil,subprocess
  prefix=self.base/'prefix with spaces';bin=prefix/'bin';bin.mkdir(parents=True)
  wrapper=bin/'hics-start';shutil.copy2(ROOT/'distribution/bin/hics-start',wrapper)
  helper=prefix/'share/hics/shell/assets/session_bootstrap.py';helper.parent.mkdir(parents=True)
  helper.write_text('from pathlib import Path; import os; assert Path(os.environ["HICS_DATA_DIR"]).resolve()==Path(__file__).resolve().parents[2]; print(Path(__file__).resolve())')
  env=dict(os.environ);env.pop('HICS_DATA_DIR',None);env.pop('HYPRSTACK_DATA_DIR',None)
  result=subprocess.run([str(wrapper)],env=env,capture_output=True,text=True,check=True)
  self.assertEqual(result.stdout.strip(),str(helper))
 def test_desktop_entry_is_parsed_with_a_space_containing_prefix(self):
  try:
   import gi
   from gi.repository import Gio
  except ImportError:self.skipTest('Gio desktop parser required')
  bin=self.base/'prefix with spaces/bin';bin.mkdir(parents=True)
  marker=self.base/'launched'
  program=bin/'hics-start';program.write_text('#!/bin/sh\ntouch "'+str(marker)+'"\n');program.chmod(0o755)
  text=(ROOT/'distribution/sessions/hics.desktop.in').read_text().replace('@CMAKE_INSTALL_FULL_BINDIR@',str(bin))
  desktop=self.base/'hics.desktop';desktop.write_text(text)
  app=Gio.DesktopAppInfo.new_from_filename(str(desktop))
  self.assertIsNotNone(app)
  # GLib get_executable splits the command before unquoting; verify launch.
  self.assertTrue(app.launch([],None))
  import time
  deadline=time.monotonic()+3
  while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
  self.assertTrue(marker.exists(),'Desktop entry did not launch the quoted executable')

 def test_launch_uses_supported_compositor_watchdog_and_private_config(self):
  with patch.object(bootstrap.os,'geteuid',return_value=1000),patch.object(bootstrap.sys,'argv',['hics-start']),patch.dict(os.environ,{'HICS_DATA_DIR':str(self.data),'XDG_CONFIG_HOME':str(self.config)}),patch.object(bootstrap.os,'execvp') as launch:
   with patch.dict(os.environ):
    os.environ.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    bootstrap.main()
  launch.assert_called_once_with('start-hyprland',['start-hyprland','--','--config',str(self.config/'hics/hypr/hyprland.lua')])

 def test_package_root_replacement_does_not_replace_the_user_entrypoint(self):
  _,entry=bootstrap.prepare(self.data,self.config);before=entry.stat();text=entry.read_text()
  (self.shipped/'hyprland.lua').unlink();(self.shipped/'hyprland.lua').write_text('-- new package root')
  _,again=bootstrap.prepare(self.data,self.config)
  self.assertEqual(again,entry);self.assertEqual(entry.read_text(),text);self.assertEqual(entry.stat().st_ino,before.st_ino)
