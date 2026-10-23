"""Bundled Qt paths must not escape into host apps; user paths are preserved."""
import json,os,shlex,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'shell/assets'))
from application_environment import application_environment
class ApplicationEnvironmentTests(unittest.TestCase):
 def test_python_and_native_filter_only_shell_runtime(self):
  data={'HOME':'/home/fixture','HYPRSTACK_DATA_DIR':'/custom/hics','LD_LIBRARY_PATH':'/usr/share/hics/qs/lib:/opt/user/lib:/custom/hics/lib',
   'QT_PLUGIN_PATH':'/usr/share/hyprstack/qs/plugins:/opt/user/plugins','QML_IMPORT_PATH':'/home/fixture/.local/share/hics/qml:/opt/user/qml',
   'QML2_IMPORT_PATH':'/custom/hics/qml','QT_QPA_PLATFORMTHEME':'hics','QT_QUICK_CONTROLS_CONF':'/home/fixture/.config/hics/qtquickcontrols2.conf','DISPLAY':':99'}
  expected=dict(data,LD_LIBRARY_PATH='/opt/user/lib',QT_PLUGIN_PATH='/opt/user/plugins',QML_IMPORT_PATH='/opt/user/qml');expected.pop('QML2_IMPORT_PATH')
  self.assertEqual(application_environment(data),expected)
  self.assertEqual(data['LD_LIBRARY_PATH'],'/usr/share/hics/qs/lib:/opt/user/lib:/custom/hics/lib')
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);source=base/'probe.cpp'
   source.write_text('''#include "util/applicationenv.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
int main(int argc,char**argv){QCoreApplication app(argc,argv);auto data=QJsonDocument::fromJson(QTextStream(stdin).readAll().toUtf8()).object();QProcessEnvironment e;for(auto i=data.begin();i!=data.end();++i)e.insert(i.key(),i.value().toString());auto clean=hics::util::applicationEnvironment(e);QJsonObject r;for(const auto&key:clean.keys())r[key]=clean.value(key);QTextStream(stdout)<<QJsonDocument(r).toJson(QJsonDocument::Compact);}''')
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
   subprocess.run(['c++','-std=c++20','-fPIC',str(source),'-I',str(ROOT/'shell/plugin/include'),*flags,'-o',str(base/'probe')],check=True)
   run=subprocess.run([str(base/'probe')],input=json.dumps(data),text=True,capture_output=True,check=True,timeout=5)
   self.assertEqual(json.loads(run.stdout),expected)
