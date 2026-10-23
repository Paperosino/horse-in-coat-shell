"""Exercise native policy and reject malformed requests before privileged I/O."""
import json,os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class MemoryTests(unittest.TestCase):
 def test_policy_transitions_and_validation(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);source=base/'probe.cpp'
   source.write_text('''#include "memory.hpp"
#include <QCoreApplication>
#include <cassert>
namespace System {QString encode(const QJsonObject &){return {};}}
int main(int argc,char**argv){QCoreApplication app(argc,argv);auto c=Memory::defaults();
c["mode"]="smart";assert(Memory::targetStage(c,0,74,100)==0);assert(Memory::targetStage(c,0,75,100)==1);
assert(Memory::targetStage(c,1,99,79)==1);assert(Memory::targetStage(c,1,70,80)==2);
assert(!Memory::recoveryPressureLow(c,100,36,5));assert(Memory::recoveryPressureLow(c,100,50,5));assert(!Memory::recoveryPressureLow(c,0,0,0));
assert(Memory::targetStage(c,2,10,0)==2); // low pressure cannot force a dangerous swapoff
for(auto mode:{"system","off","zram","zswap","both"}){c["mode"]=mode;int target=Memory::targetStage(c,2,99,100);assert(target==(QString(mode)=="zram"?1:QString(mode)=="both"||QString(mode)=="zswap"?2:0));}
for(auto key:{"zramMiB","ramThreshold","zramThreshold","poolPercent","chunkMiB","diskMaxMiB","diskThreshold","reserveMiB","hysteresis","releaseSeconds"}){
for(auto v:{QJsonValue(-1),QJsonValue(1.5),QJsonValue("80"),QJsonValue(true)}){auto bad=Memory::defaults();bad[key]=v;bool rejected=false;try{Memory::validate(bad);}catch(...){rejected=true;}assert(rejected);}}
auto bad=Memory::defaults();bad["chunkMiB"]=16384;bool rejected=false;try{Memory::validate(bad);}catch(...){rejected=true;}assert(rejected);
auto metrics=Memory::metrics();assert(metrics["total"].toDouble()>0);assert(metrics["available"].toDouble()<=metrics["total"].toDouble());}
''')
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus'],text=True))
   subprocess.run(['c++','-std=c++20','-fPIC',str(source),str(ROOT/'native/system/memory.cpp'),'-I',str(ROOT/'native/system'),'-DHYPRSTACK_SYSTEMD_RUN="/usr/bin/false"','-DHYPRSTACK_MEMORY_EXECUTABLE="/usr/bin/false"',*flags,'-o',str(base/'probe')],check=True)
   subprocess.run([str(base/'probe')],check=True)
 def test_invalid_settings_never_reach_system_bus(self):
  client=ROOT/'build/native/system/hics-systemctl'
  env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS='unix:path=/nonexistent/hics-memory-test')
  for settings in [{'mode':'evil'},{'poolPercent':90},{'path':'/etc/fstab'},{'compressor':'zstd; reboot'},{'takeOver':'true'},{'releaseIdle':0}]:
   with self.subTest(settings=settings):
    run=subprocess.run([str(client),'apply','memory','configure'],input=json.dumps(settings),env=env,capture_output=True,text=True,timeout=3)
    self.assertEqual(json.loads(run.stdout)['code'],'invalid',run.stdout)
