"""Actual broker runtime on a private bus; the backend never touches the host."""
import json,os,shlex,signal,socket,subprocess,tempfile,time,unittest,uuid
from pathlib import Path
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
ROOT=Path(__file__).resolve().parents[1]
DBusGMainLoop(set_as_default=True)

class BrokerRuntime(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-broker-tests-');cls.addClassCleanup(cls.temp.cleanup);cls.base=Path(cls.temp.name);cls.binary=cls.base/'broker'
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus','libsystemd'],text=True))
  moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
  subprocess.run([str(moc),str(ROOT/'native/system/main.cpp'),'-o',str(cls.base/'main.moc'),*shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6DBus'],text=True))],check=True)
  stub=cls.base/'backend.cpp';stub.write_text('''#include "backend.hpp"
#include <QThread>
#include <QFile>
#include <QJsonDocument>
namespace System {
QString encode(const QJsonObject&o){return QString::fromUtf8(QJsonDocument(o).toJson(QJsonDocument::Compact));}
QJsonObject failure(const std::exception&e){const auto*f=dynamic_cast<const Failure*>(&e);return {{"error",QString::fromUtf8(e.what())},{"code",f?f->code:QString("failed")}};}
void authorize(const QString&,const QString&,uint){}
void validate(const QString&,const QString&,const QJsonObject&){}
void apply(const QString&,const QString&,const QJsonObject&,uint){}
QJsonObject status(const QString&domain,uint uid){
 if(domain=="hang"){QFile file(qEnvironmentVariable("HICS_TEST_MARKER"));if(file.open(QIODevice::WriteOnly))file.write("started");QThread::sleep(30);}
 if(domain=="slow")QThread::msleep(900);
 return {{"domain",domain},{"uid",int(uid)}};
}}
''')
  subprocess.run(['c++','-std=c++20','-fPIC',str(ROOT/'native/system/main.cpp'),str(stub),'-I'+str(cls.base),'-I'+str(ROOT/'native/system'),*flags,'-o',str(cls.binary)],check=True)
 def setUp(self):
  self.case=tempfile.TemporaryDirectory(dir=self.base);self.addCleanup(self.case.cleanup);self.dir=Path(self.case.name);self.marker=self.dir/'started'
  self.bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True);self.address=self.bus.stdout.readline().strip()
  self.notify=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);self.notify.bind(str(self.dir/'notify'));self.notify.settimeout(.05)
  self.env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=self.address,NOTIFY_SOCKET=str(self.dir/'notify'),WATCHDOG_USEC='200000',HICS_TEST_MARKER=str(self.marker));self.env.pop('WATCHDOG_PID',None)
  self.connections=[];self.broker=subprocess.Popen([str(self.binary)],env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
  self.conn=self.connect()
  self.until(lambda:self.conn.name_has_owner('org.hics.System1'))
 def connect(self):
  connection=dbus.bus.BusConnection(self.address);self.connections.append(connection);return connection
 def until(self,condition,timeout=5):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
   if condition():return
   time.sleep(.01)
  self.fail('Condition timed out')
 def iface(self,connection=None):return dbus.Interface((connection or self.conn).get_object('org.hics.System1','/org/hics/System1',introspect=False),'org.hics.System1')
 def status(self,domain='fast',connection=None):return json.loads(str(self.iface(connection).Status(domain,signature='s')))
 def stop_broker(self):
  if self.broker and self.broker.poll() is None:self.broker.terminate();self.broker.wait(timeout=7)
  if self.broker and self.broker.stderr:self.broker.stderr.close()
  self.broker=None
 def tearDown(self):
  self.stop_broker()
  # Deliver outstanding async replies before releasing their Python connection
  # wrappers; dbus-python otherwise dispatches stale GLib callbacks next case.
  while GLib.MainContext.default().pending():GLib.MainContext.default().iteration(False)
  for connection in self.connections:connection.close()
  self.notify.close();self.bus.terminate();self.bus.wait(timeout=3);self.bus.stdout.close()
 def test_readiness_and_main_loop_watchdog_notifications(self):
  messages=[];until=time.monotonic()+.6
  while time.monotonic()<until:
   try:messages.append(self.notify.recv(4096).decode())
   except socket.timeout:pass
  self.assertTrue(any('READY=1' in m for m in messages),messages);self.assertGreaterEqual(sum('WATCHDOG=1' in m for m in messages),3,messages)
 def test_caller_rate_limit_does_not_block_another_connection(self):
  results=[self.status() for _ in range(12)]
  self.assertTrue(any(r.get('code')=='rate_limited' for r in results),results)
  self.assertEqual(self.status(connection=self.connect())['domain'],'fast')
 def test_inflight_client_cannot_occupy_all_workers(self):
  done=[];self.iface().Status('slow',signature='s',reply_handler=lambda r:done.append(r),error_handler=lambda e:done.append(e))
  self.assertEqual(self.status().get('code'),'busy')
  other=self.connect();self.assertEqual(self.status(connection=other)['domain'],'fast')
  self.iface(other).Status('slow',signature='s',reply_handler=lambda r:done.append(r),error_handler=lambda e:done.append(e))
  self.assertEqual(self.status(connection=self.connect()).get('code'),'busy')
  self.until(lambda:len(done)==2)
 def occupy_uid(self):
  for connection in (self.conn,self.connect()):self.iface(connection).Status('slow',signature='s',reply_handler=lambda r:None,error_handler=lambda e:None)
  # The next synchronous call is ordered after the second slow request.
  self.assertEqual(self.status(connection=self.connect()).get('code'),'busy')
 def test_native_client_retries_busy_reads(self):
  client=ROOT/'build/native/system/hics-systemctl'
  if not client.exists():self.skipTest('Build the native client first')
  self.occupy_uid()
  result=subprocess.run([str(client),'status','fast'],env=self.env,capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(json.loads(result.stdout)['domain'],'fast')
 def test_native_client_does_not_replay_writes(self):
  client=ROOT/'build/native/system/hics-systemctl'
  if not client.exists():self.skipTest('Build the native client first')
  self.occupy_uid();start=time.monotonic()
  result=subprocess.run([str(client),'apply','power','profile'],input='{"profile":"balanced"}',env=self.env,capture_output=True,text=True,timeout=2)
  self.assertEqual(result.returncode,1,result.stdout+result.stderr);self.assertEqual(json.loads(result.stdout)['code'],'busy');self.assertLess(time.monotonic()-start,.8)
 def test_shutdown_does_not_destroy_qt_under_a_blocked_worker(self):
  self.iface().Status('hang',signature='s',reply_handler=lambda r:None,error_handler=lambda e:None)
  self.until(self.marker.exists)
  start=time.monotonic();self.broker.terminate();self.assertEqual(self.broker.wait(timeout=7),0)
  self.assertLess(time.monotonic()-start,6.5)
 def test_systemd_restarts_a_stopped_main_loop(self):
  if subprocess.run(['systemctl','--user','show-environment'],capture_output=True).returncode:self.skipTest('User systemd manager required')
  self.stop_broker();unit='hics-watchdog-test-'+uuid.uuid4().hex
  def prop(key):return subprocess.check_output(['systemctl','--user','show',unit,'-p',key,'--value'],text=True).strip()
  try:
   subprocess.run(['systemd-run','--user','--quiet','--collect','--unit='+unit,'--service-type=notify','-p','WatchdogSec=1','-p','WatchdogSignal=SIGKILL','-p','Restart=on-failure','-p','RestartSec=100ms','-p','StartLimitIntervalSec=120','-p','StartLimitBurst=3','-p','RuntimeMaxSec=10','-p','TimeoutStopSec=7','-p','LimitCORE=0','--setenv=DBUS_SYSTEM_BUS_ADDRESS='+self.address,str(self.binary)],check=True,capture_output=True)
   original=int(prop('MainPID'));self.assertGreater(original,0);os.kill(original,signal.SIGSTOP)
   self.until(lambda:int(prop('NRestarts'))>=1 and int(prop('MainPID')) not in (0,original) and prop('ActiveState')=='active',timeout=7)
   self.assertEqual(prop('ActiveState'),'active')
  finally:
   subprocess.run(['systemctl','--user','stop',unit],capture_output=True,timeout=9)
   subprocess.run(['systemctl','--user','reset-failed',unit],capture_output=True)

class AdmissionPolicies(unittest.TestCase):
 def test_uid_reconnect_fairness_capacity_and_refill(self):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);source=base/'probe.cpp';binary=base/'probe'
   source.write_text('''#include "admission.hpp"
#include <cassert>
int main(){using A=System::Admission;A a;
 assert(a.reserve(1,"one",0)==A::Result::Allowed);assert(a.reserve(1,"one",0)==A::Result::Busy);
 assert(a.reserve(1,"two",0)==A::Result::Allowed);assert(a.reserve(1,"reconnect",0)==A::Result::Busy);
 assert(a.reserve(2,"other-user",0)==A::Result::Allowed);
 a.finish(1,"one");a.finish(1,"two");a.finish(2,"other-user");assert(a.pending()==0);
 A reconnects;for(int i=0;i<40;++i){auto sender=QString::number(i);assert(reconnects.reserve(42,sender,0)==A::Result::Allowed);reconnects.finish(42,sender);}
 assert(reconnects.reserve(42,"new-connection",0)==A::Result::RateLimited);assert(reconnects.reserve(43,"different-user",0)==A::Result::Allowed);
 assert(reconnects.reserve(42,"after-refill",1000)==A::Result::Allowed);
 A capacity;for(uint i=0;i<16;++i)assert(capacity.reserve(i,QString::number(i),0)==A::Result::Allowed);
 assert(capacity.reserve(100,"full",0)==A::Result::Busy);capacity.stop();assert(capacity.reserve(101,"stop",0)==A::Result::Stopping);
 for(uint i=0;i<16;++i)capacity.finish(i,QString::number(i));assert(capacity.pending()==0);
 A bounded;for(int i=0;i<3000;++i){auto sender=QString::number(i);assert(bounded.reserve(1,sender,i*1000)==A::Result::Allowed);bounded.finish(1,sender);}
}''')
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
   subprocess.run(['c++','-std=c++20','-fPIC',str(source),'-I'+str(ROOT/'native/system'),*flags,'-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True,timeout=5)
