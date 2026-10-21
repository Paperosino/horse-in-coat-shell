import importlib.util, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shell/assets'))
import appearance_themes as themes
class AppearanceThemesTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);base=Path(self.temp.name)
  for key,relative in [('HOME','home'),('CONFIG','home/config'),('DATA','home/data'),('CACHE','cache'),('STATE','home/config/hics/appearance.json')]:
   p=patch.object(themes,key,base/relative);p.start();self.addCleanup(p.stop)
  p=patch.dict(os.environ,{'XDG_DATA_DIRS':str(base/'system')},clear=False);p.start();self.addCleanup(p.stop)
  icon=themes.DATA/'icons/Test';(icon/'32x32/places').mkdir(parents=True)
  (icon/'index.theme').write_text('[Icon Theme]\nName=Test icons\nDirectories=32x32/places\n')
  (icon/'32x32/places/folder.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
  cursor=themes.DATA/'icons/Pointer';(cursor/'cursors').mkdir(parents=True)
  (cursor/'index.theme').write_text('[Icon Theme]\nName=Test pointer\nHidden=true\n')
 def test_icon_selection_preserves_toolkit_settings(self):
  themes.update_ini(themes.CONFIG/'gtk-3.0/settings.ini','Settings',{'gtk-font-name':'Test 10'})
  themes.update_ini(themes.CONFIG/'qt6ct/qt6ct.conf','Appearance',{'style':'Fusion'})
  result=themes.apply('icons','Test',runtime=False)
  self.assertEqual(result['current']['icons'],'Test')
  self.assertEqual(themes.ini(themes.CONFIG/'gtk-3.0/settings.ini').get('Settings','gtk-font-name'),'Test 10')
  for version in (5,6):self.assertEqual(themes.ini(themes.CONFIG/f'qt{version}ct/qt{version}ct.conf').get('Appearance','icon_theme'),'Test')
  self.assertEqual(themes.ini(themes.CONFIG/'qt6ct/qt6ct.conf').get('Appearance','style'),'Fusion')
 def test_hidden_icon_metadata_does_not_hide_cursor_themes(self):
  self.assertIn('Pointer',[x['id'] for x in themes.catalogue()['cursors']])
 def test_invalid_theme_and_size_do_not_write_preferences(self):
  for kind,name,size in [('icons','../bad',24),('cursors','Pointer',2),('wrong','Test',24),('icons','Test\nInjected',24)]:
   with self.assertRaises(ValueError):themes.apply(kind,name,size,runtime=False)
  self.assertFalse(themes.STATE.exists())
 def test_cursor_size_and_inheritance_survive_reload(self):
  themes.apply('cursors','Pointer',40,runtime=False)
  self.assertEqual(themes.current()['size'],40)
  self.assertEqual(themes.session_environment()['XCURSOR_THEME'],'Pointer')
  self.assertEqual(themes.ini(themes.DATA/'icons/default/index.theme').get('Icon Theme','Inherits'),'Pointer')
 def test_icon_preview_rejects_manifest_path_traversal_and_cycles(self):
  outside=themes.DATA/'icons/outside';outside.mkdir();(outside/'folder.svg').write_text('private')
  catalog=themes.themes();catalog['Test']['directories']=['../outside'];catalog['Test']['inherits']=['Test']
  self.assertIsNone(themes.resolve_icon('Test','folder',catalog))
 def test_flatpak_uses_app_configs_without_home_access_grants(self):
  calls=[]
  def command(argv,warnings=None,input=None):
   calls.append(argv)
   return 'org.example.App\n../escape' if argv[1]=='list' else ''
  with patch.object(themes.shutil,'which',return_value='/bin/flatpak'),patch.object(themes,'command',side_effect=command):
   themes.flatpak_settings('icons','Test',24,[])
   themes.flatpak_settings('cursors','Pointer',32,[])
  config=themes.HOME/'.var/app/org.example.App/config'
  self.assertEqual(themes.ini(config/'gtk-4.0/settings.ini').get('Settings','gtk-icon-theme-name'),'Test')
  self.assertEqual(themes.ini(config/'qt6ct/qt6ct.conf').get('Appearance','icon_theme'),'Test')
  self.assertFalse(any(arg.startswith('--filesystem') for call in calls for arg in call))
  self.assertFalse((themes.HOME/'.var/escape').exists())
 def test_runtime_updates_are_reported_and_saved(self):
  with patch.object(themes,'command',return_value=None),patch.object(themes,'flatpak_settings'):
   themes.apply('icons','Test')
  self.assertTrue((themes.CONFIG/'environment.d/90-hics-appearance.conf').is_file())
  self.assertEqual(themes.current()['icons'],'Test')
if __name__=='__main__':unittest.main()
