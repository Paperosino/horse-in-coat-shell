"""Real lease controller with hostile helpers, no system power/GameMode calls."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / 'shell/plugin/src/Hyprstack/Services'
HELPER = r'''
import json,os,sys,time
mode=os.environ['HICS_LEASE_CASE']
counter=os.environ['HICS_LEASE_STARTS']
try:count=int(open(counter).read())+1
except FileNotFoundError:count=1
open(counter,'w').write(str(count))
row=dict(lease='power',error='fixture' if mode=='delete' or mode=='switch' and count==1 else '')
if mode=='unknown':row['lease']='arbitrary'
if mode=='type':row['error']=12
data=(json.dumps(row)+'\n').encode()
if mode=='malformed':data=b'{not-json}\n'
if mode in ('duplicate','delete'):data+=data
if mode in ('oversize','flood'):data=b'x'*100000
if mode=='exit':sys.exit(0)
if mode=='silent':data=b''
if mode=='fragmented':
 for i in range(0,len(data),5):os.write(1,data[i:i+5]);time.sleep(.002)
else:os.write(1,data)
if mode=='flood':
 while True:os.write(1,b'x'*100000)
sys.stdin.read()
if mode=='switch' and count==1:
 time.sleep(.05);print(json.dumps(dict(lease='power',error='late old result')),flush=True)
with open(os.environ['HICS_LEASE_EOF'],'a') as f:f.write(str(count)+'\n')
'''

PROBE = r'''
#include "runtimeperformance.hpp"
#include <QCoreApplication>
#include <QFile>
#include <QTimer>
#include <QElapsedTimer>
#include <cassert>
#include <memory>
using hyprstack::services::RuntimePerformance;
int main(int argc,char**argv){
 QCoreApplication app(argc,argv);auto p=std::make_unique<RuntimePerformance>();
 const auto mode=qgetenv("HICS_LEASE_CASE");QElapsedTimer elapsed;elapsed.start();int phase=0;
 assert(p->set("performanceProfile",true));
 p->observeWindow({{"class","steam_app_42"},{"pid",int(app.applicationPid())},{"mapped",true},{"fullscreen",2}});
 if(mode.startsWith("game-")) {
  QObject::connect(p.get(),&RuntimePerformance::gameChanged,&app,[&]{p.reset();});
  QTimer::singleShot(0,&app,[&]{
   if(mode=="game-observe")p->observeWindow({{"class","not-a-game"}});
   else if(mode=="game-set")p->set("gameRules",QStringList{});
   else p->setSessionState(false,false,true);
   assert(!p);app.quit();
  });
  return app.exec();
 }
 QObject::connect(p.get(),&RuntimePerformance::statusChanged,&app,[&]{
  if(!p)return;
  const auto status=p->status();
  if(mode=="switch") {
   if(phase==0&&status.value("powerError").toString()=="fixture") {
    phase=1;p->setSessionState(false,false,false);p->setSessionState(true,false,false);return;
   }
   if(phase==1&&status.contains("powerError")) {
    assert(status.value("powerError").toString().isEmpty());assert(status.value("leaseError").toString().isEmpty());phase=2;p.reset();
   }
   return;
  }
  if(!status.contains("powerError")&&!status.contains("leaseError"))return;
  if(mode=="fragmented")assert(status.value("powerError").toString().isEmpty()&&!status.contains("leaseError"));
  else if(mode!="delete")assert(!status.value("leaseError").toString().isEmpty());
  assert(!status.contains("arbitraryError"));
  if(mode=="oversize"||mode=="flood")assert(elapsed.elapsed()<1000);
  if(mode=="silent")assert(elapsed.elapsed()>=3500&&elapsed.elapsed()<5000);
  phase=2;p.reset(); // Deliberate direct destruction from the notification.
 });
 QTimer poll;poll.setInterval(20);
 QObject::connect(&poll,&QTimer::timeout,&app,[&]{
  if(phase!=2)return;
  QFile file(qEnvironmentVariable("HICS_LEASE_EOF"));
  if(mode=="flood"||mode=="oversize") {
   if(!app.findChildren<QProcess*>().isEmpty())return;
   assert(elapsed.elapsed()<1000);app.quit();return;
  }
  if(mode=="missing"||mode=="exit"){app.quit();return;}
  if(!file.open(QIODevice::ReadOnly))return;
  const auto lines=file.readAll().trimmed().split('\n');
  if(lines.size()<(mode=="switch"?2:1))return;
  app.quit();
 });poll.start();
 QTimer::singleShot(10000,&app,[]{std::abort();});
 QTimer::singleShot(0,&app,[&]{p->setSessionState(true,false,false);});
 return app.exec();
}
'''


class LeaseProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='hics-lease-protocol-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        source = cls.base / 'probe.cpp'
        source.write_text(PROBE)
        controller = SERVICES / 'runtimeperformance.cpp'
        if os.environ.get('HICS_TEST_LEASE_SOURCE'):
            controller = cls.base / 'controller.cpp'
            text = Path(os.environ['HICS_TEST_LEASE_SOURCE']).read_text()
            controller.write_text(text.replace('"../../../../../native/system/game_activity.hpp"',
                                               json.dumps(str(ROOT / 'native/system/game_activity.hpp'))))
        moc = cls.base / 'moc.cpp'
        mocbin = Path(subprocess.check_output(['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip()) / 'moc'
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Core', 'Qt6Qml'], text=True))
        subprocess.run([str(mocbin), str(SERVICES / 'runtimeperformance.hpp'),
                        *shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'Qt6Qml'], text=True)),
                        '-o', str(moc)], check=True, capture_output=True, timeout=15)
        sanitizer = ['-fsanitize=address', '-fno-omit-frame-pointer'] if os.environ.get('HICS_TEST_ASAN') else []
        result = subprocess.run(['c++', '-std=c++20', '-fPIC', '-g', *sanitizer, '-I' + str(SERVICES),
                                 str(source), str(controller), str(moc), *flags, '-o', str(cls.base / 'probe')],
                                capture_output=True, text=True, timeout=45)
        if result.returncode:
            raise RuntimeError(result.stderr)

    def run_case(self, mode):
        with tempfile.TemporaryDirectory(prefix='case-', dir=self.base) as directory:
            base = Path(directory)
            (base / 'run').mkdir(mode=0o700)
            tools = base / 'bin'
            tools.mkdir()
            helper = tools / 'hics-game-lease'
            helper.write_text('#!/hics-fixture-missing-interpreter\n' if mode == 'missing'
                              else '#!' + sys.executable + '\n' + HELPER)
            helper.chmod(0o700)
            env = dict(os.environ, HOME=str(base), XDG_CONFIG_HOME=str(base / 'config'),
                       XDG_STATE_HOME=str(base / 'state'), XDG_DATA_HOME=str(base / 'data'),
                       XDG_RUNTIME_DIR=str(base / 'run'), DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(base / 'absent'),
                       DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(base / 'absent-system'),
                       HICS_HELPER_DIR=str(tools), HICS_LEASE_CASE=mode,
                       HICS_LEASE_STARTS=str(base / 'starts'), HICS_LEASE_EOF=str(base / 'eof'))
            result = subprocess.run([str(self.base / 'probe')], env=env, capture_output=True, text=True, timeout=12)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn('QProcess: Destroyed while process', result.stderr)

    def test_direct_destruction_from_status_handler(self):
        self.run_case('delete')

    def test_game_changed_handler_can_destroy_controller_during_public_calls(self):
        for mode in ('game-observe', 'game-set', 'game-lock'):
            with self.subTest(mode=mode):
                self.run_case(mode)

    def test_fragmented_valid_response_and_graceful_eof(self):
        self.run_case('fragmented')

    def test_invalid_response_is_bounded_and_releases_helper(self):
        for mode in ('unknown', 'type', 'malformed', 'duplicate', 'oversize'):
            with self.subTest(mode=mode):
                self.run_case(mode)

    def test_retiring_helper_cannot_flood_qprocess_buffers(self):
        self.run_case('flood')

    def test_silent_helper_times_out_without_blocking_or_restart(self):
        self.run_case('silent')

    def test_start_failure_and_missing_completion(self):
        for mode in ('missing', 'exit'):
            with self.subTest(mode=mode):
                self.run_case(mode)

    def test_old_helper_response_cannot_overwrite_new_lease(self):
        self.run_case('switch')
