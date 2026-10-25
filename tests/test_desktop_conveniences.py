"""Native camera-policy rollback and bounded cleanup use private paths and commands."""
import os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'
class DesktopConveniences(unittest.TestCase):
 def test_camera_transaction_and_cleanup(self):
  with tempfile.TemporaryDirectory(prefix='hics-conveniences-') as directory:
   base=Path(directory);(base/'bin').mkdir();(base/'bin/systemctl').write_text('#!/bin/sh\n[ "$HICS_TEST_FAIL" = 1 ] && exit 1\nexit 0\n');(base/'bin/systemctl').chmod(0o700)
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui','Qt6Qml','Qt6DBus','Qt6Concurrent','Qt6Multimedia'],text=True));moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
   subprocess.run([str(moc),str(SERVICES/'desktopconveniences.hpp'),'-o',str(base/'moc.cpp'),*[f for f in flags if f.startswith(('-I','-D'))]],check=True)
   src=base/'probe.cpp';src.write_text('''#include "desktopconveniences.hpp"
#include <QCoreApplication>
#include <QTimer>
#include <QFile>
#include <QDir>
#include <QDBusInterface>
#include <QDBusConnection>
#include <cassert>
int main(int argc,char**argv){QCoreApplication app(argc,argv);hyprstack::services::DesktopConveniences service;int phase=0;QString path=qEnvironmentVariable("XDG_CONFIG_HOME")+"/wireplumber/wireplumber.conf.d/90-hics-camera-privacy.conf";
if(argc>1){int step=0;service.setDockInhibitRequested(true);QTimer timer;timer.setInterval(20);QObject::connect(&timer,&QTimer::timeout,[&]{
QDBusInterface session("org.freedesktop.login1","/org/freedesktop/login1/session/test","org.hics.Test",QDBusConnection::systemBus());
if(step==0&&service.dockInhibited()){session.call("SetActive",false);step=1;}
else if(step==1&&!service.dockInhibited()){assert(service.dockInhibitRequested());session.call("SetActive",true);step=2;}
else if(step==2&&service.dockInhibited()){service.setDockInhibitRequested(false);assert(!service.dockInhibited());app.quit();}
});timer.start();QTimer::singleShot(8000,&app,[]{std::abort();});return app.exec();}
qputenv("HICS_TEST_FAIL","1");service.setCameraBlocked(true);
QTimer timer;timer.setInterval(20);QObject::connect(&timer,&QTimer::timeout,[&]{if(service.busy())return;
if(phase==0){assert(!service.cameraBlocked());assert(!QFile::exists(path));assert(!service.error().isEmpty());qputenv("HICS_TEST_FAIL","0");service.setCameraBlocked(true);phase=1;}
else if(phase==1){assert(service.cameraBlocked());assert(QFile::exists(path));service.setCameraBlocked(false);phase=2;}
else if(phase==2){assert(!service.cameraBlocked());assert(!QFile::exists(path));service.clean("../../outside",0);assert(!service.error().isEmpty());service.inspectCleanup();phase=3;}
else if(phase==3){assert(service.cleanup().contains("thumbnails"));service.openPortal("file:///etc/passwd");assert(!service.error().isEmpty());service.openPortal("https://user:pass@example.com/");assert(!service.error().isEmpty());assert(!service.launch("arbitrary-command"));app.quit();}
});timer.start();QTimer::singleShot(8000,&app,[]{std::abort();});return app.exec();}
''')
   subprocess.run(['c++','-std=c++20','-fPIC',str(src),str(SERVICES/'desktopconveniences.cpp'),str(base/'moc.cpp'),'-I'+str(SERVICES),'-I'+str(ROOT/'shell/plugin/include'),*flags,'-o',str(base/'probe')],check=True,capture_output=True)
   result=subprocess.run([str(base/'probe')],env=dict(os.environ,XDG_CONFIG_HOME=str(base/'config'),XDG_CACHE_HOME=str(base/'cache'),XDG_DATA_HOME=str(base/'data'),PATH=str(base/'bin')+':'+os.environ['PATH']),capture_output=True,text=True,timeout=12)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)

   bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True)
   address=bus.stdout.readline().strip();env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=address,XDG_CONFIG_HOME=str(base/'config'))
   mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_lid_bus.py')],env=env,stdout=subprocess.PIPE,text=True)
   try:
    self.assertEqual(mock.stdout.readline().strip(),'ready')
    result=subprocess.run([str(base/'probe'),'lid'],env=env,capture_output=True,text=True,timeout=12)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   finally:
    mock.terminate();mock.wait();mock.stdout.close();bus.terminate();bus.wait();bus.stdout.close()
