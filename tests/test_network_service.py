"""Exercise real libnm cache, signals, permissions and bounded native helpers."""
import json,os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'
class NetworkNative(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-network-native-');cls.addClassCleanup(cls.temp.cleanup);cls.base=Path(cls.temp.name)
  moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Qml','Qt6Network','Qt6DBus','libnm'],text=True))
  subprocess.run([str(moc),str(SERVICES/'networkservice.hpp'),'-o',str(cls.base/'moc.cpp'),*[f for f in flags if f.startswith(('-I','-D'))]],check=True)
  source=cls.base/'probe.cpp';source.write_text('''#include "networkservice.hpp"
#include <QCoreApplication>
#include <QTimer>
#include <QDBusInterface>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <cassert>
using namespace hyprstack::services;
int main(int argc,char**argv){QCoreApplication app(argc,argv);if(argc>1){for(int i=0;i<30;++i){NetworkService transient;transient.request("scan");}return 0;}NetworkService network;int phase=0,expected=0;QElapsedTimer clock;clock.start();
QObject::connect(&network,&NetworkService::operationFinished,[&](int id,QVariantMap result){if(id!=expected)return;
if(phase==1){assert(result["success"].toBool());phase=2;expected=network.request("autoconnect",{{"connection","Wired fixture"},{"enabled",false}});}
else if(phase==2){assert(result["success"].toBool());phase=3;expected=network.request("ipv4",{{"connection","Wired fixture"},{"config",QVariantMap{{"method","auto-dns"},{"dns","9.9.9.9,1.1.1.1"}}}});}
else if(phase==3){assert(result["success"].toBool());phase=4;expected=network.request("wifi",{{"enabled",false}});}
else if(phase==4){assert(!result["success"].toBool() && result["error"].toString().contains("denied"));phase=5;QDBusInterface bus("org.freedesktop.NetworkManager","/org/freedesktop/NetworkManager","org.hics.Test",QDBusConnection::systemBus());bus.call("Signal");}
});
QTimer poll;poll.setInterval(20);QObject::connect(&poll,&QTimer::timeout,[&]{auto state=network.state();
if(phase==0&&state["profiles"].toList().size()==31 && state["activeConnection"]=="Wired fixture"){assert(state["available"].toBool());assert(state["connectivity"].toInt()==4);assert(state["ethernet"].toList().size()==1);assert(state["wireless"].toList().size()==1);auto ap=state["networks"].toList()[0].toMap();assert(ap["ssid"].toString()==QString::fromUtf8("Cafe:Сеть"));assert(ap["strength"].toInt()==77);assert(state["activeConnection"]=="Wired fixture");auto eth=state["ethernet"].toList()[0].toMap();assert(eth["ipAddress"]=="192.0.2.10");assert(eth["subnet"]=="255.255.255.0");assert(network.interfaceStats("eth0;touch /tmp/escape").isEmpty());assert(network.interfaceStats("../lo").isEmpty());assert(network.interfaceStats("lo").contains("rx"));phase=1;expected=network.request("scan");}
if(phase==5&&state["connectivity"].toInt()==2&&state["networks"].toList()[0].toMap()["strength"].toInt()==33){QTimer::singleShot(100,&app,&QCoreApplication::quit);phase=6;}
if(clock.elapsed()>6000){fprintf(stderr,"network timeout phase %d state %s\\n",phase,QJsonDocument::fromVariant(state).toJson().constData());std::abort();}
});poll.start();app.exec();assert(phase==6);}
''')
  subprocess.run(['c++','-std=c++20','-fPIC','-pthread',str(source),str(SERVICES/'networkservice.cpp'),str(cls.base/'moc.cpp'),'-I'+str(SERVICES),*flags,'-o',str(cls.base/'probe')],check=True,capture_output=True)
 def test_cancel_initialization_and_pending_requests_on_shutdown(self):
  result=subprocess.run([str(self.base/"probe"),"lifecycle"],env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS="unix:path=/nonexistent-network-test-bus"),capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_cached_profiles_live_ap_signals_and_async_mutations(self):
  bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True)
  address=bus.stdout.readline().strip();log=self.base/'calls.jsonl';log.write_text('')
  env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=address,NETWORK_TEST_LOG=str(log))
  mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_network_bus.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertEqual(mock.stdout.readline().strip(),'ready')
   result=subprocess.run([str(self.base/'probe')],env=env,capture_output=True,text=True,timeout=12)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr+'\nmock:'+log.read_text()[-1500:])
   rows=[json.loads(s) for s in log.read_text().splitlines()]
   self.assertEqual(sum(row['method']=='RequestScan' for row in rows),1)
   updates=[row['data'] for row in rows if row['method']=='Update2'];self.assertEqual(len(updates),2)
   self.assertEqual(updates[-1]['ipv6']['dns-search'],['keep.example'])
   self.assertEqual(updates[-1]['ipv4']['dns-data'],['9.9.9.9','1.1.1.1'])
  finally:
   mock.terminate();mock.wait(timeout=4);mock.stdout.close();mock.stderr.close();bus.terminate();bus.wait();bus.stdout.close()
