"""Real attached tokens allocate font/animation trees only for their consumers."""
import os,shlex,subprocess,tempfile,unittest
from pathlib import Path
from integration_support import snapshot_qml_runtime
ROOT=Path(__file__).resolve().parents[1]
class TokensLazyTests(unittest.TestCase):
 def test_real_qml_lazy_resources_and_late_screen_changes(self):
  with tempfile.TemporaryDirectory(prefix='hics-lazy-tokens-') as directory:
   base=Path(directory);cfg=base/'config/hics';cfg.mkdir(parents=True)
   for screen,scale in [('fixture',1.5),('other',.75)]:
    path=cfg/'monitors'/screen;path.mkdir(parents=True);(path/'shell.json').write_text('{"appearance":{"scale":'+str(scale)+'}}')
   (base/'probe.qml').write_text('''import QtQuick
import Hyprstack.Config
Item {
 Tokens.screen:"fixture"
 property real margin:Tokens.padding.medium
 property real rounding:Tokens.rounding.large
 property real density:Tokens.scale
 function askFont(){return Tokens.font.body.medium.pointSize;}
 function askAnim(){return Tokens.anim!==null;}
 function switchScreen(){Tokens.screen="other";return askFont();}
 function updateScale(){GlobalConfig.forScreen("other").appearance.scale=1.5;return askFont();}
}''')
   (base/'probe.cpp').write_text(r'''#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlComponent>
#include <QPointer>
#include <QDebug>
#include <cmath>
#include <memory>
int main(int argc,char**argv){
 QGuiApplication app(argc,argv);QQmlEngine engine;QQmlComponent component(&engine,QUrl::fromLocalFile(argv[1]));
 std::unique_ptr<QObject> root(component.create());if(!root){qCritical()<<component.errors();return 1;}
 auto resources=[&](const char* name){QList<QObject*> found;for(auto* child:root->findChildren<QObject*>())if(QByteArray(child->metaObject()->className())==name)found<<child;return found;};
 const char* fonts="hyprstack::config::FontTokens";const char* anims="hyprstack::config::AnimTokens";
 if(!resources(fonts).isEmpty()||!resources(anims).isEmpty()){qCritical()<<"Geometry-only tokens eagerly allocated"<<resources(fonts).size()<<resources(anims).size();return 2;}
 auto call=[&](const char* method){QVariant value;if(!QMetaObject::invokeMethod(root.get(),method,Q_RETURN_ARG(QVariant,value)))return QVariant();return value;};
 const auto first=call("askFont").toDouble();if(first<=0||resources(fonts).size()!=1||!resources(anims).isEmpty())return 3;
 QPointer<QObject> font=resources(fonts).first();for(int i=0;i<100;++i)if(call("askFont").toDouble()!=first)return 4;
 const auto second=call("switchScreen").toDouble();if(std::abs(second/first-.5)>.001||resources(fonts).size()!=1||resources(fonts).first()!=font)return 5;
 if(std::abs(call("updateScale").toDouble()/second-2)>.001)return 6;
 if(!call("askAnim").toBool()||resources(anims).size()!=1)return 7;
 QPointer<QObject> anim=resources(anims).first();for(int i=0;i<100;++i)call("askAnim");if(resources(anims).size()!=1)return 8;
 root.reset();if(font||anim)return 9;qInfo()<<"TOKENS_LAZY_OK"<<first<<second;return 0;
}''')
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Gui','Qt6Qml'],text=True))
   result=subprocess.run(['c++','-std=c++20','-fPIC',str(base/'probe.cpp'),*flags,'-o',str(base/'probe')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
   env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),QT_QPA_PLATFORM='offscreen',QT_FORCE_STDERR_LOGGING='1',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'absent-session'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'))
   env.update(snapshot_qml_runtime(ROOT,base))
   result=subprocess.run([str(base/'probe'),str(base/'probe.qml')],env=env,capture_output=True,text=True,timeout=15)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertIn('TOKENS_LAZY_OK',result.stderr)
