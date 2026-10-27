"""Real native game helper against private fake daemons; no host power writes."""
import json,os,shlex,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class GameLeases(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='hics-game-lease-tests-');self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
  self.binary=ROOT/'build/native/system/hics-game-lease'
  if not self.binary.exists():self.skipTest('Build native helpers first')
  self.bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True)
  address=self.bus.stdout.readline().strip()
  self.env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address,HICS_LEASE_TEST_LOG=str(self.base/'calls'),HICS_LEASE_TEST_READY=str(self.base/'ready'))
  self.mock=None;self.game=None;self.helper=None
 def start(self,delay=0):
  self.mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_performance_bus.py')],env=dict(self.env,HICS_LEASE_TEST_DELAY=str(delay)),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  self.until(lambda:(self.base/'ready').exists())
  self.game=subprocess.Popen(['sleep','30'])
  self.helper=subprocess.Popen([str(self.binary),str(self.game.pid),'--gamemode','--performance'],env=self.env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def events(self):
  try:return [json.loads(x) for x in (self.base/'calls').read_text().splitlines()]
  except FileNotFoundError:return []
 def until(self,predicate,timeout=4):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   if predicate():return
   time.sleep(.01)
  self.fail('Timed out: '+repr(self.events()))
 def tearDown(self):
  for child in (self.helper,self.game,self.mock,self.bus):
   if child is None:continue
   if child.poll() is None:child.terminate()
   try:child.wait(timeout=4)
   except subprocess.TimeoutExpired:child.kill();child.wait()
   for stream in (child.stdin,child.stdout,child.stderr):
    if stream:stream.close()
 def assert_released(self):
  self.assertEqual(self.helper.wait(timeout=4),0)
  events=self.events();kinds=[e['kind'] for e in events]
  for what in ('game-acquired','game-released','power-acquired','power-released'):self.assertIn(what,kinds)
  acquired=next(e for e in events if e['kind']=='game-acquired')
  self.assertEqual(acquired['pids'],[self.game.pid,self.helper.pid])
 def test_eof_releases_game_and_power_leases(self):
  self.start();self.until(lambda:len(self.events())==2);self.helper.stdin.close();self.assert_released()
 def test_late_acquisition_after_eof_is_released(self):
  self.start(delay=300);time.sleep(.08);self.helper.stdin.close();self.assert_released()
 def test_game_exit_triggers_pidfd_cleanup(self):
  self.start();self.until(lambda:len(self.events())==2);self.game.terminate();self.game.wait();self.assert_released()

 def test_zero_cookie_is_released_explicitly(self):
  self.env['HICS_LEASE_TEST_COOKIE']='0';self.start();self.until(lambda:len(self.events())==2);self.helper.stdin.close();self.assert_released()
  self.assertEqual(next(e['cookie'] for e in self.events() if e['kind']=='power-released'),0)

 def test_controller_destruction_preserves_late_native_power_release(self):
  self.mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_performance_bus.py')],env=dict(self.env,HICS_LEASE_TEST_DELAY='300',HICS_LEASE_TEST_COOKIE='0'),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  self.until(lambda:(self.base/'ready').exists())
  services=ROOT/'shell/plugin/src/Hyprstack/Services'
  source=self.base/'controller.cpp';source.write_text(r'''#include "runtimeperformance.hpp"
#include <QCoreApplication>
#include <QTimer>
#include <QFile>
#include <cassert>
#include <memory>
using hyprstack::services::RuntimePerformance;
int main(int argc,char**argv){QCoreApplication app(argc,argv);auto p=std::make_unique<RuntimePerformance>();
assert(p->set("performanceProfile",true));p->observeWindow({{"class","steam_app_42"},{"pid",int(app.applicationPid())},{"mapped",true},{"fullscreen",2}});p->setSessionState(true,false,false);
QTimer::singleShot(80,&app,[&]{p.reset();QFile f(qEnvironmentVariable("HICS_LEASE_TEST_LOG"));assert(f.open(QIODevice::WriteOnly|QIODevice::Append));f.write("{\"kind\":\"controller-deleted\"}\n");});
bool done=false;QTimer poll;poll.setInterval(20);QObject::connect(&poll,&QTimer::timeout,&app,[&]{if(done)return;QFile f(qEnvironmentVariable("HICS_LEASE_TEST_LOG"));if(f.open(QIODevice::ReadOnly)&&f.readAll().contains("power-released")){done=true;QTimer::singleShot(250,&app,&QCoreApplication::quit);}});poll.start();QTimer::singleShot(5000,&app,[]{std::abort();});return app.exec();}
''')
  moc=self.base/'moc.cpp';mocbin=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
  subprocess.run([str(mocbin),str(services/'runtimeperformance.hpp'),*shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6Qml'],text=True)),'-o',str(moc)],check=True,capture_output=True,timeout=15)
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Qml'],text=True))
  sanitize=['-fsanitize=address','-fno-omit-frame-pointer'] if os.environ.get('HICS_TEST_ASAN') else []
  binary=self.base/'controller'
  result=subprocess.run(['c++','-std=c++20','-fPIC','-g',*sanitize,str(source),str(services/'runtimeperformance.cpp'),str(moc),'-I'+str(services),*flags,'-o',str(binary)],capture_output=True,text=True,timeout=45)
  self.assertEqual(result.returncode,0,result.stderr)
  (self.base/'run').mkdir(mode=0o700)
  env=dict(self.env,HOME=str(self.base),XDG_CONFIG_HOME=str(self.base/'config'),XDG_STATE_HOME=str(self.base/'state'),XDG_DATA_HOME=str(self.base/'data'),XDG_RUNTIME_DIR=str(self.base/'run'),HICS_HELPER_DIR=str(ROOT/'build/native/system'))
  self.helper=subprocess.Popen([str(binary)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  out,err=self.helper.communicate(timeout=8);self.assertEqual(self.helper.returncode,0,out+err)
  self.assertNotIn('QProcess: Destroyed while process',err)
  events=self.events();kinds=[event['kind'] for event in events]
  self.assertLess(kinds.index('controller-deleted'),kinds.index('power-acquired'))
  self.assertLess(kinds.index('power-acquired'),kinds.index('power-released'))
  self.assertEqual(next(event['cookie'] for event in events if event['kind']=='power-released'),0)
