"""Real HyprExtras sockets against private local servers; device model stubbed."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / 'shell/plugin/src/Hyprstack/Services'
DEVICE = r'''
#pragma once
#include <QObject>
#include <QJsonObject>
namespace hyprstack::services::hypr {
class HyprDevices:public QObject {
 Q_OBJECT
public:
 explicit HyprDevices(QObject *parent=nullptr):QObject(parent){}
 int updates=0;
 bool updateLastIpcObject(const QJsonObject&){++updates;return true;}
};
}
'''
PROBE = r'''
#include "hyprextras.hpp"
#include "hyprdevices.hpp"
#include <QCoreApplication>
#include <QJSEngine>
#include <QJsonDocument>
#include <QJsonArray>
#include <QLocalServer>
#include <QDir>
#include <QPointer>
#include <QTimer>
#include <QElapsedTimer>
#include <cassert>
#include <memory>
using hyprstack::services::hypr::HyprExtras;
class Bridge:public QObject {
 Q_OBJECT
public:
 std::function<void()> remove;
 Q_INVOKABLE void erase(){remove();}
};
int main(int argc,char **argv){
 QCoreApplication app(argc,argv);
 const auto mode=qgetenv("HICS_HYPR_CASE");
 const auto path=qEnvironmentVariable("XDG_RUNTIME_DIR")+"/hypr/fixture";
 assert(QDir().mkpath(path));qputenv("HYPRLAND_INSTANCE_SIGNATURE","fixture");
 QLocalServer requests,events;assert(requests.listen(path+"/.socket.sock"));assert(events.listen(path+"/.socket2.sock"));
 int descriptions=0,devices=0,connections=0,phase=0;QPointer<QLocalSocket> eventPeer;QElapsedTimer reconnectTime;
 QObject::connect(&events,&QLocalServer::newConnection,&app,[&]{
  while(events.hasPendingConnections()){
   auto *peer=events.nextPendingConnection();eventPeer=peer;++connections;
   QObject::connect(peer,&QLocalSocket::disconnected,peer,&QObject::deleteLater);
  }
 });
 QObject::connect(&requests,&QLocalServer::newConnection,&app,[&]{
  while(requests.hasPendingConnections()){
   auto *peer=requests.nextPendingConnection();
   QObject::connect(peer,&QLocalSocket::disconnected,peer,&QObject::deleteLater);
   QObject::connect(peer,&QLocalSocket::readyRead,peer,[&,peer]{
    const auto command=peer->readAll();QByteArray response;
    if(qEnvironmentVariableIsSet("HICS_HYPR_TRACE"))fprintf(stderr,"request %s\n",command.constData());
    if(command=="j/descriptions")response="[{\"name\":\"fixture:value\",\"current\":"+QByteArray::number(++descriptions)+"}]";
    else if(command=="j/devices"){++devices;response="{\"keyboards\":[]}";}
    else if(command.startsWith("[[BATCH]]"))response="\n";
    else if(command=="overflow")response=QByteArray(17*1024*1024,'x');
    else if(command=="limit")response=QByteArray(16*1024*1024,'x');
    else response="hello";
    if(command=="overflow"||command=="limit"){
     peer->write(response);peer->disconnectFromServer();return;
    }
    peer->write(response.left(3));
    QTimer::singleShot(10,peer,[peer,response]{
     if(peer->state()!=QLocalSocket::ConnectedState)return;
     peer->write(response.mid(3));peer->disconnectFromServer();
    });
   });
  }
 });
 Bridge bridge;QJSEngine js;std::unique_ptr<HyprExtras> extra=std::make_unique<HyprExtras>();
 bridge.remove=[&]{extra.reset();};QJSEngine::setObjectOwnership(&bridge,QJSEngine::CppOwnership);
 js.globalObject().setProperty("bridge",js.newQObject(&bridge));js.globalObject().setProperty("store",js.newObject());
 const auto callback=js.evaluate("(function(ok,text){store.answer={ok:ok,n:text.length};})");
 QTimer poll;poll.setInterval(20);
 QObject::connect(&poll,&QTimer::timeout,&app,[&]{
  if(phase==0){
   if(!eventPeer||extra->options().value("fixture:value").toInt()<1||extra->devices()->updates<1)return;
   phase=1;
   if(mode=="unterminated"){
    eventPeer->write("PRIVATE_EVENT_MARKER"+QByteArray(2*1024*1024,'x'));
    QTimer::singleShot(150,&app,[&]{
     for(auto *socket:extra->findChildren<QLocalSocket*>())if(socket->serverName().endsWith(".socket2.sock"))assert(socket->bytesAvailable()<=65536);
     eventPeer->write("\nconfigreloaded>>\nactivelayout>>us\n");
    });
   }else if(mode=="malformed")eventPeer->write("PRIVATE_EVENT_MARKER\nPRIVATE_EVENT_MARKER\nconfigreloaded>>\nactivelayout>>us\n");
   else if(mode=="burst"){
    QByteArray burst;for(int i=0;i<100;++i)burst+="configreloaded>>\nactivelayout>>us\n";eventPeer->write(burst);
   }else if(mode=="fragmented"){
    eventPeer->write("configre");QTimer::singleShot(10,&app,[&]{eventPeer->write("loaded>>\nactivelayout>>us\n");});
   }else if(mode=="reconnect")eventPeer->disconnectFromServer();
   else if(mode=="reconnect-unavailable"){
    reconnectTime.start();events.close();QLocalServer::removeServer(path+"/.socket2.sock");eventPeer->disconnectFromServer();
    QTimer::singleShot(1500,&app,[&]{assert(events.listen(path+"/.socket2.sock"));});
   }
   else if(mode=="delete-options"){
    QObject::connect(extra.get(),&HyprExtras::optionsChanged,&app,[&]{extra.reset();});extra->refreshOptions(true);
   }else if(mode=="delete-failure"){
    requests.close();QLocalServer::removeServer(path+"/.socket.sock");
    extra->request("missing",js.evaluate("(function(ok,text){bridge.erase();store.answer={ok:ok,n:text.length};})"));
   }else extra->request(QString::fromLatin1(mode),callback);
  }else if(mode=="delete-options"){
   if(!extra)app.quit();
  }else if(mode=="overflow"||mode=="limit"||mode=="success"||mode=="delete-failure"){
   const auto answer=js.globalObject().property("store").property("answer");if(!answer.isObject())return;
   const bool ok=answer.property("ok").toBool();const int length=answer.property("n").toInt();
   if(mode=="overflow"||mode=="delete-failure")assert(!ok&&length==0);
   else assert(ok&&length==(mode=="limit"?16*1024*1024:5));
   if(mode=="delete-failure")assert(!extra);
   app.quit();
  }else if(extra->options().value("fixture:value").toInt()>=2&&extra->devices()->updates>=2){
   if(mode=="burst")assert(descriptions<=3&&devices<=3);
   if(mode=="reconnect"||mode=="reconnect-unavailable")assert(connections>=2);
   if(mode=="reconnect-unavailable")assert(reconnectTime.elapsed()>=2000&&reconnectTime.elapsed()<5000);
   app.quit();
  }
 });poll.start();
 QTimer::singleShot(7000,&app,[&]{fprintf(stderr,"timeout phase=%d descriptions=%d devices=%d connections=%d updates=%d value=%d\n",phase,descriptions,devices,connections,extra?extra->devices()->updates:-1,extra?extra->options().value("fixture:value").toInt():-1);std::abort();});
 return app.exec();
}
#include "probe.moc"
'''


class HyprIpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='hics-hypr-ipc-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        # The production socket implementation is unchanged. Only the device
        # publication dependency is replaced; real device/QML coverage is separate.
        source = Path(os.environ.get('HICS_TEST_HYPR_SOURCE', SERVICES / 'hyprextras.cpp'))
        (cls.base / 'hyprextras.cpp').write_bytes(source.read_bytes())
        (cls.base / 'hyprextras.hpp').write_bytes((SERVICES / 'hyprextras.hpp').read_bytes())
        (cls.base / 'hyprdevices.hpp').write_text(DEVICE)
        (cls.base / 'probe.cpp').write_text(PROBE)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Core', 'Qt6Qml', 'Qt6Network'], text=True))
        moc_flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'Qt6Core', 'Qt6Qml', 'Qt6Network'], text=True))
        moc = Path(subprocess.check_output(['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip()) / 'moc'
        generated = []
        for source, output in [('hyprextras.hpp','moc_extras.cpp'),('hyprdevices.hpp','moc_devices.cpp'),('probe.cpp','probe.moc')]:
            result = subprocess.run([str(moc), str(cls.base / source), *moc_flags, '-o', str(cls.base / output)], capture_output=True, text=True, timeout=15)
            if result.returncode: raise RuntimeError(result.stderr)
            if output.endswith('.cpp'): generated.append(str(cls.base / output))
        sanitizer = ['-fsanitize=address', '-fno-omit-frame-pointer'] if os.environ.get('HICS_TEST_ASAN') else []
        result = subprocess.run(['c++', '-std=c++20', '-fPIC', '-g', *sanitizer,
                                 str(cls.base / 'probe.cpp'), str(cls.base / 'hyprextras.cpp'),
                                 *generated, *flags, '-o', str(cls.base / 'probe')],
                                capture_output=True, text=True, timeout=45)
        if result.returncode: raise RuntimeError(result.stderr)

    def run_case(self, mode):
        with tempfile.TemporaryDirectory(prefix='case-', dir=self.base) as directory:
            base = Path(directory)
            runtime = base / 'run';runtime.mkdir(mode=0o700)
            env = dict(os.environ, HOME=str(base), XDG_RUNTIME_DIR=str(runtime),
                       XDG_CONFIG_HOME=str(base/'config'), XDG_STATE_HOME=str(base/'state'),
                       DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'absent'),
                       DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'),
                       HICS_HYPR_CASE=mode, QT_FORCE_STDERR_LOGGING='1',
                       QT_LOGGING_RULES='hyprstack.services.hypr.warning=true')
            result = subprocess.run([str(self.base/'probe')],env=env,capture_output=True,text=True,timeout=9)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertNotIn('PRIVATE_EVENT_MARKER',result.stdout+result.stderr)
            if mode=='malformed':self.assertEqual(result.stderr.count('malformed event discarded'),1)
            if mode=='unterminated':self.assertEqual(result.stderr.count('oversized event discarded'),1)

    def test_fragmented_events_and_burst_snapshot_coalescing(self):
        for mode in ('fragmented','burst'):
            with self.subTest(mode=mode):self.run_case(mode)

    def test_event_bounds_privacy_and_resynchronization(self):
        for mode in ('unterminated','malformed'):
            with self.subTest(mode=mode):self.run_case(mode)

    def test_event_socket_reconnects_and_refreshes_snapshots(self):
        self.run_case('reconnect')

    def test_event_reconnect_backs_off_until_server_returns(self):
        self.run_case('reconnect-unavailable')

    def test_request_fragments_boundary_and_overflow(self):
        for mode in ('success','limit','overflow'):
            with self.subTest(mode=mode):self.run_case(mode)

    def test_callbacks_can_destroy_owner(self):
        for mode in ('delete-options','delete-failure'):
            with self.subTest(mode=mode):self.run_case(mode)
