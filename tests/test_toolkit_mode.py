"""The shell mode must reach GTK portals, Qt Quick and KDE as well as palettes."""
import configparser,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'shell/assets'))
import gtk_theme
class ToolkitModeTests(unittest.TestCase):
 def test_dark_light_mode_reaches_all_toolkits(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);config=root/'config'
   colours=dict.fromkeys(('surface','onSurface','surfaceContainer','primary','onPrimary','outlineVariant'),'112233')
   env={'XDG_DATA_HOME':str(root/'data'),'HYPRLAND_INSTANCE_SIGNATURE':'fixture','DBUS_SESSION_BUS_ADDRESS':'unix:path=/fixture'}
   with patch.dict(os.environ,env),patch('gtk_theme.subprocess.run') as run,patch('gtk_theme.shutil.which',return_value='/fixture/gsettings'):
    for mode in ('dark','light'):
     run.reset_mock();gtk_theme.apply_palette(colours,config,mode);gtk_theme.sync_session_preference(colours,config,mode)
     calls=[c.args[0]for c in run.call_args_list]
     self.assertIn(['gsettings','set','org.gnome.desktop.interface','color-scheme','prefer-'+mode],calls)
     self.assertIn(['gsettings','set','org.gnome.desktop.interface','gtk-theme','Adwaita-dark' if mode=='dark' else 'Adwaita'],calls)
     quick=configparser.ConfigParser();quick.read(config/'hics/qtquickcontrols2.conf')
     for style in ('Material','Universal'):self.assertEqual(quick[style]['Theme'],mode.title())
     self.assertNotIn('Controls',quick) # preserve application style choice
     self.assertTrue((root/'data/color-schemes/hics.colors').is_file())
     self.assertIn('QT_QUICK_CONTROLS_CONF', (config/'environment.d/91-hics-toolkit.conf').read_text())
     self.assertTrue(any(c[0]=='dbus-update-activation-environment' and '--systemd' in c for c in calls))

class RealQtModeTests(unittest.TestCase):
 def test_material_and_universal_follow_dark_and_light(self):
  import shlex,subprocess
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);binary=root/'probe'
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6Quick','Qt6Qml'],text=True))
   subprocess.run(['c++','-std=c++20','-fPIC',str(ROOT/'tests/fixtures/toolkit-mode-probe.cpp'),*flags,'-o',str(binary)],check=True)
   config=root/'config'
   env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='qt5ct',XDG_CONFIG_HOME=str(config))
   env.pop('QT_QUICK_CONTROLS_CONF',None)
   env.pop('QT_STYLE_OVERRIDE',None)
   colours=dict(surface='101018',onSurface='e0e0e0',surfaceContainer='202028',primary='aaccee',onPrimary='102030',outlineVariant='505060')
   gtk_theme.apply_palette(colours,config,'dark')
   baseline=subprocess.run([str(binary),'Material'],env=dict(env,QT_QUICK_CONTROLS_STYLE='Material'),capture_output=True,text=True,timeout=8,check=True)
   self.assertFalse(json.loads(baseline.stdout)['dark'],baseline.stdout)
   for style in ('Material','Universal'):
    with self.subTest(style=style):
     for mode in ('dark','light'):
      gtk_theme.apply_palette(colours,config,mode)
      run=subprocess.run([str(binary),style],env=dict(env,QT_QUICK_CONTROLS_STYLE=style,QT_QUICK_CONTROLS_CONF=str(config/'hics/qtquickcontrols2.conf')),capture_output=True,text=True,timeout=8,check=True)
      data=json.loads(run.stdout);self.assertEqual(data['dark'],mode=='dark',data);self.assertEqual(data['window'],'#101018')

class PlatformThemeTests(unittest.TestCase):
 def test_native_palette_and_automatic_scheme_agree(self):
  import shlex,subprocess
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);source=base/'probe.cpp'
   source.write_text('''#include <QApplication>
#include <QPalette>
#include <QStyleHints>
#include <QJsonDocument>
#include <QJsonObject>
#include <cstdio>
int main(int argc,char**argv){QApplication app(argc,argv);QJsonObject r{{"window",app.palette().color(QPalette::Window).name()}};
#if QT_VERSION >= QT_VERSION_CHECK(6,5,0)
r["scheme"]=int(app.styleHints()->colorScheme());
#endif
puts(QJsonDocument(r).toJson(QJsonDocument::Compact).constData());}''')
   for version in (5,6):
    with self.subTest(qt=version):
     plugins=ROOT/f'build/qt-themes/qt{version}'
     if not list((plugins/'platformthemes').glob('*.so')):self.fail('Build the Qt theme adapter first')
     flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',f'Qt{version}Widgets'],text=True));binary=base/f'probe{version}'
     subprocess.run(['c++','-fPIC',str(source),*flags,'-o',str(binary)],check=True)
     config=base/f'config{version}'
     env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='hics',QT_PLUGIN_PATH=str(plugins),XDG_CONFIG_HOME=str(config));env.pop('LD_LIBRARY_PATH',None)
     for mode,surface,scheme in [('dark','101018',2),('light','f5f5f5',1)]:
      colours=dict(surface=surface,onSurface='808080',surfaceContainer=surface,primary='aaccee',onPrimary='102030',outlineVariant='505060')
      gtk_theme.apply_palette(colours,config,mode)
      run=subprocess.run([str(binary)],env=env,capture_output=True,text=True,check=True,timeout=5);result=json.loads(run.stdout)
      self.assertEqual(result['window'],'#'+surface,result)
      if version==6:self.assertEqual(result['scheme'],scheme,result)
