"""Native NVML uses one helper; a hung driver never blocks Qt's main loop."""
import json,os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'
class GpuSampler(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-nvml-tests-');cls.addClassCleanup(cls.temp.cleanup);cls.base=Path(cls.temp.name)
  helper=ROOT/'build/native/system/hics-gpu-monitor'
  if not helper.exists():raise unittest.SkipTest('Build native helpers first')
  (cls.base/'hics-gpu-monitor').symlink_to(helper)
  mock=cls.base/'nvml.c';mock.write_text('''#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
static void logit(const char*s){const char*p=getenv("HICS_NVML_LOG");if(p){FILE*f=fopen(p,"a");if(f){fprintf(f,"%s\\n",s);fclose(f);}}}
int nvmlInit_v2(){logit("init");return getenv("HICS_NVML_UNAVAILABLE")?1:0;}int nvmlShutdown(){logit("shutdown");return 0;}
int nvmlDeviceGetCount_v2(unsigned*n){*n=2;return 0;}
int nvmlDeviceGetHandleByIndex_v2(unsigned i,void**p){*p=(void*)(uintptr_t)(i+1);return 0;}
struct usage{unsigned gpu,memory;};
int nvmlDeviceGetUtilizationRates(void*d,struct usage*u){if(getenv("HICS_NVML_HANG"))sleep(30);u->gpu=41+(uintptr_t)d;u->memory=0;return 0;}
int nvmlDeviceGetTemperature(void*d,unsigned kind,unsigned*t){*t=69+(uintptr_t)d;return 0;}
''')
  subprocess.run(['cc','-shared','-fPIC',str(mock),'-o',str(cls.base/'libnvidia-ml.so.1')],check=True)
  source=cls.base/'probe.cpp';source.write_text('''#include "gpumetricssampler.hpp"
#include <QCoreApplication>
#include <QTimer>
#include <QElapsedTimer>
#include <cassert>
int main(int argc,char**argv){QCoreApplication app(argc,argv);QObject owner;hics::performance::GpuMetricsSampler sampler(&owner);QElapsedTimer elapsed;elapsed.start();int ticks=0;QTimer heartbeat;heartbeat.setInterval(50);QObject::connect(&heartbeat,&QTimer::timeout,[&]{++ticks;});heartbeat.start();
QTimer::singleShot(0,&owner,[&]{sampler.request([&](double gpu,double temp,double,bool available){
if(qEnvironmentVariableIsSet("HICS_NVML_HANG")){assert(!available);assert(elapsed.elapsed()<2200);assert(ticks>=15);sampler.request([&](double,double,double,bool again){assert(!again);assert(elapsed.elapsed()<2250);app.quit();});}
else{assert(available && gpu==43 && temp==71);sampler.request([&](double next,double,double,bool valid){assert(valid && next==43);app.quit();});}
});});QTimer::singleShot(4000,&app,[]{std::abort();});return app.exec();}''')
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
  subprocess.run(['c++','-std=c++20','-fPIC',str(source),'-I'+str(SERVICES),*flags,'-o',str(cls.base/'probe')],check=True)
 def env(self,**overrides):
  return dict(os.environ,HICS_HELPER_DIR=str(self.base),HICS_GPU_SYSFS_ROOT=str(self.base/'sys'),LD_LIBRARY_PATH=str(self.base)+':'+os.environ.get('LD_LIBRARY_PATH',''),**overrides)
 def test_helper_reuses_nvml_and_reports_maximum_device_load(self):
  log=self.base/'direct.log'
  result=subprocess.run([str(self.base/'hics-gpu-monitor')],input='sample\nsample\n',env=self.env(HICS_NVML_LOG=str(log)),capture_output=True,text=True,check=True,timeout=4)
  rows=[json.loads(x) for x in result.stdout.splitlines()];self.assertEqual(len(rows),2)
  self.assertTrue(all(r=={'available':True,'usage':43,'temperature':71,'cpuTemperature':-1} for r in rows));self.assertEqual(log.read_text().splitlines(),['init','shutdown'])
 def test_sampler_reuses_native_helper(self):
  log=self.base/'sampler.log';subprocess.run([str(self.base/'probe')],env=self.env(HICS_NVML_LOG=str(log)),check=True,timeout=4)
  self.assertEqual(log.read_text().splitlines().count('init'),1)
 def test_hung_driver_keeps_main_loop_responsive_and_backs_off(self):
  log=self.base/'hung.log';subprocess.run([str(self.base/'probe')],env=self.env(HICS_NVML_LOG=str(log),HICS_NVML_HANG='1'),check=True,timeout=4)
  self.assertEqual(log.read_text().splitlines().count('init'),1)

 def test_generic_gpu_and_cpu_package_sensors_are_read_outside_ui(self):
  root=self.base/'generic-sys'
  files={
   'class/drm/card0/device/gpu_busy_percent':'87',
   'class/hwmon/hwmon0/name':'amdgpu',
   'class/hwmon/hwmon0/temp1_label':'edge','class/hwmon/hwmon0/temp1_input':'64000',
   'class/hwmon/hwmon0/temp2_label':'junction','class/hwmon/hwmon0/temp2_input':'95000',
   'class/hwmon/hwmon1/name':'coretemp',
   'class/hwmon/hwmon1/temp1_label':'Package id 0','class/hwmon/hwmon1/temp1_input':'86000',
   'class/hwmon/hwmon1/temp2_label':'Core 0','class/hwmon/hwmon1/temp2_input':'120000'}
  for relative,value in files.items():
   path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
  env=self.env(HICS_NVML_UNAVAILABLE='1');env['HICS_GPU_SYSFS_ROOT']=str(root)
  run=subprocess.run([str(self.base/'hics-gpu-monitor')],input='thermal\n',env=env,capture_output=True,text=True,check=True,timeout=4)
  self.assertEqual(json.loads(run.stdout),{'available':True,'usage':87,'temperature':95,'cpuTemperature':86})

 def test_generic_only_sampling_does_not_load_nvml(self):
  root=self.base/'generic-only';busy=root/'class/drm/card0/device/gpu_busy_percent';busy.parent.mkdir(parents=True);busy.write_text('12')
  log=self.base/'generic-only.log';env=self.env(HICS_NVML_LOG=str(log));env['HICS_GPU_SYSFS_ROOT']=str(root)
  run=subprocess.run([str(self.base/'hics-gpu-monitor')],input='generic\n',env=env,capture_output=True,text=True,check=True,timeout=4)
  self.assertEqual(json.loads(run.stdout)['usage'],12);self.assertFalse(log.exists())
