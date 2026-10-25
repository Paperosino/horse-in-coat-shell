"""Bounded CPU notification images and PID-safe game memory holds."""
import os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'
class ResourceHelpers(unittest.TestCase):
 def test_notification_image_copy_scale_and_provider_without_a_window(self):
  with tempfile.TemporaryDirectory(prefix='hics-notification-images-') as directory:
   base=Path(directory);moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui','Qt6Quick','Qt6Qml','Qt6Concurrent'],text=True))
   subprocess.run([str(moc),str(SERVICES/'notificationimages.hpp'),'-o',str(base/'moc.cpp'),*[f for f in flags if f.startswith(('-I','-D'))]],check=True)
   source=base/'probe.cpp';source.write_text('''#include "notificationimages.hpp"
#include <QGuiApplication>
#include <QQmlEngine>
#include <QQmlContext>
#include <QImage>
#include <QFile>
#include <QTimer>
#include <QQuickImageProvider>
#include <cassert>
class Provider:public QQuickImageProvider{public:Provider():QQuickImageProvider(Image){}QImage requestImage(const QString&,QSize*size,const QSize&)override{QImage image(1600,800,QImage::Format_ARGB32);image.fill(Qt::green);*size=image.size();return image;}};
int main(int argc,char**argv){QGuiApplication app(argc,argv);QQmlEngine engine;engine.addImageProvider("fixture",new Provider);hyprstack::services::NotificationImages images;QQmlEngine::setContextForObject(&images,engine.rootContext());engine.globalObject().setProperty("cache",engine.newQObject(&images));engine.globalObject().setProperty("quit",engine.evaluate("(function(){})"));QString path=QString::fromLocal8Bit(argv[1])+"/original.png";QImage original(2400,1600,QImage::Format_ARGB32);original.fill(Qt::red);assert(original.save(path));engine.globalObject().setProperty("inputPath",path);engine.evaluate("var paths=[];cache.cache(inputPath,true,p=>paths.push(p));cache.cache(inputPath,false,p=>paths.push(p));cache.cache('image://fixture/id',false,p=>paths.push(p));cache.cache('https://example.org/image.png',false,p=>paths.push(p));");
QTimer timer;timer.setInterval(20);QObject::connect(&timer,&QTimer::timeout,[&]{const auto paths=engine.globalObject().property("paths");if(paths.property("length").toInt()!=4)return;QStringList stored;for(int i=0;i<4;++i)if(!paths.property(i).toString().isEmpty())stored<<paths.property(i).toString();assert(stored.size()==3);bool copied=false,scaled=false,provider=false;QFile source(path);assert(source.open(QIODevice::ReadOnly));const auto bytes=source.readAll();for(const auto& cached:stored){QImage image(cached);if(image.size()==QSize(2400,1600)){QFile file(cached);assert(file.open(QIODevice::ReadOnly));assert(file.readAll()==bytes);copied=true;}if(image.size()==QSize(1280,853))scaled=true;if(image.size()==QSize(1280,640))provider=true;}assert(copied&&scaled&&provider);assert(QGuiApplication::allWindows().isEmpty());app.quit();});timer.start();QTimer::singleShot(8000,&app,[]{std::abort();});return app.exec();}
''')
   subprocess.run(['c++','-std=c++20','-fPIC',str(source),str(SERVICES/'notificationimages.cpp'),str(base/'moc.cpp'),'-I'+str(SERVICES),*flags,'-o',str(base/'probe')],check=True,capture_output=True)
   result=subprocess.run([str(base/'probe'),str(base)],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_CACHE_HOME=str(base/'cache')),capture_output=True,text=True,timeout=12)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_game_hold_rejects_stale_pid_symlink_and_different_start(self):
  with tempfile.TemporaryDirectory(prefix='hics-game-hold-') as directory:
   base=Path(directory);flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
   source=base/'probe.cpp';source.write_text('''#include "game_activity.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QDir>
#include <unistd.h>
#include <cassert>
int main(int argc,char**argv){QCoreApplication app(argc,argv);const QString runtime=QString::fromLocal8Bit(argv[1]);const QString root=runtime+"/"+QString::number(getuid())+"/hics";QDir().mkpath(root);const QString path=root+"/game-mode-fixture.json";const qint64 pid=QCoreApplication::applicationPid();const QString start=QString::fromLatin1(hics::game::processStart("/proc/"+QString::number(pid)+"/stat"));auto write=[&](qint64 id,QString time,bool enabled){QFile f(path);assert(f.open(QIODevice::WriteOnly));f.write(QJsonDocument(QJsonObject{{"pid",id},{"start",time},{"active",enabled}}).toJson());};assert(!hics::game::active(runtime));write(pid,start,true);assert(hics::game::active(runtime));write(pid,start,false);assert(!hics::game::active(runtime));write(pid,"wrong-start",true);assert(!hics::game::active(runtime));write(99999999,start,true);assert(!hics::game::active(runtime));write(pid,start,true);QFile::rename(path,path+".real");assert(QFile::link(path+".real",path));assert(!hics::game::active(runtime));}
''')
   subprocess.run(['c++','-std=c++20','-fPIC',str(source),'-I'+str(ROOT/'native/system'),*flags,'-o',str(base/'probe')],check=True,capture_output=True)
   subprocess.run([str(base/'probe'),str(base/'run')],check=True,timeout=3)
