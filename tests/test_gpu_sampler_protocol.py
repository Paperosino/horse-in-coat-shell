"""Hostile helper responses must not outlive or cross sampler requests."""
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
mode=os.environ['HICS_PROTOCOL_CASE']
first=None
for command in sys.stdin:
 request=command.strip().rsplit(' ',1)[-1]
 row=dict(requestId=request,available=True,usage=43,temperature=71,cpuTemperature=-1)
 if first is None:first=dict(row)
 elif mode=='late':row=first
 if mode in ('oversize','unterminated'):
  os.write(1,b'x'*100000+(b'\n' if mode=='oversize' else b''));time.sleep(2);continue
 if mode=='wrong-id':row['requestId']='wrong'
 if mode=='wrong-type':row['available']='yes'
 if mode=='out-of-range':row['usage']=1000
 if mode=='inconsistent':row['available']=False
 data=(json.dumps(row)+'\n').encode()
 if mode in ('malformed','recover'):data=b'{not-json}\n'
 if mode in ('multiple','delete'):data+=data
 if mode in ('overlap','cancel'):time.sleep(.1)
 if mode=='fragmented':
  for i in range(0,len(data),9):os.write(1,data[i:i+9]);time.sleep(.002)
 else:os.write(1,data)
 if mode=='unsolicited':time.sleep(.04);os.write(1,data)
 if mode=='exit':break
'''

PROBE = r'''
#include "gpumetricssampler.hpp"
#include <QCoreApplication>
#include <QTimer>
#include <QElapsedTimer>
#include <cassert>
#include <memory>
using Sampler=hics::performance::GpuMetricsSampler;
int main(int argc,char **argv) {
 QCoreApplication app(argc,argv);auto owner=std::make_unique<QObject>();
 auto sampler=std::make_unique<Sampler>(owner.get());QElapsedTimer elapsed;elapsed.start();
 const auto mode=qgetenv("HICS_PROTOCOL_CASE");int callbacks=0;
 QTimer::singleShot(mode=="recover"?36000:4000,&app,[]{std::abort();});
 QTimer::singleShot(0,&app,[&]{
  if(mode=="cancel") {
   sampler->request([&](double,double,double,bool){std::abort();});
   QTimer::singleShot(20,&app,[&]{sampler->reset();sampler->request([&](double value,double,double,bool ok){assert(ok&&value==43);++callbacks;app.quit();});});
   return;
  }
  sampler->request([&](double value,double,double,bool ok){
   ++callbacks;
   if(mode=="delete"||mode=="delete-owner") {
    sampler.reset();if(mode=="delete-owner")owner.reset();QTimer::singleShot(100,&app,[&]{assert(callbacks==1);app.quit();});return;
   }
   if(mode=="overlap") {assert(ok&&value==43&&callbacks==2);app.quit();return;}
   if(mode=="recover") {
    assert(!ok);
    sampler->request([&](double,double,double,bool again){assert(!again);++callbacks;});
    qputenv("HICS_PROTOCOL_CASE","fragmented");
    QTimer::singleShot(30500,Qt::PreciseTimer,&app,[&]{sampler->request([&](double next,double,double,bool valid){++callbacks;assert(valid&&next==43&&callbacks==3);app.quit();});});
    return;
   }
   if(mode=="fragmented"||mode=="late"||mode=="exit"||mode=="unsolicited") {
    assert(ok&&value==43);
    auto next=[&]{sampler->request([&](double n,double,double,bool valid){++callbacks;assert(callbacks==2);if(mode=="fragmented")assert(valid&&n==43);else assert(!valid);app.quit();});};
    if(mode=="unsolicited")QTimer::singleShot(150,&app,next);else next();
    return;
   }
   assert(!ok);
   if(mode=="oversize"||mode=="unterminated")assert(elapsed.elapsed()<700);
   sampler->request([&](double,double,double,bool again){++callbacks;assert(!again&&callbacks==2);app.quit();});
  });
  if(mode=="overlap")sampler->request([&](double,double,double,bool ok){assert(!ok);++callbacks;});
 });
 return app.exec();
}
'''


class GpuProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='hics-gpu-protocol-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        helper = cls.base / 'hics-gpu-monitor'
        helper.write_text('#!' + sys.executable + '\n' + HELPER)
        helper.chmod(0o700)
        source = cls.base / 'probe.cpp'
        source.write_text(PROBE)
        includes = ['-I' + str(SERVICES)]
        if os.environ.get('HICS_TEST_GPU_SAMPLER_HEADER'):
            override = cls.base / 'override'
            override.mkdir()
            (override / 'gpumetricssampler.hpp').write_bytes(
                Path(os.environ['HICS_TEST_GPU_SAMPLER_HEADER']).read_bytes())
            includes.insert(0, '-I' + str(override))
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', 'Qt6Core'], text=True))
        sanitizers = ['-fsanitize=address', '-fno-omit-frame-pointer'] if os.environ.get('HICS_TEST_ASAN') else []
        result = subprocess.run(['c++', '-std=c++20', '-fPIC', '-g', *sanitizers,
                                 str(source), *includes, *flags, '-o', str(cls.base / 'probe')],
                                capture_output=True, text=True, timeout=40)
        if result.returncode:
            raise RuntimeError(result.stderr)

    def run_case(self, mode):
        env = dict(os.environ, HICS_HELPER_DIR=str(self.base), HICS_PROTOCOL_CASE=mode)
        result = subprocess.run([str(self.base / 'probe')], env=env, capture_output=True,
                                text=True, timeout=40 if mode == 'recover' else 6)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('QProcess: Destroyed while process', result.stderr)

    def test_fragmented_valid_response_and_reentrant_request(self):
        self.run_case('fragmented')

    def test_bounded_and_strict_frames(self):
        for mode in ('oversize', 'unterminated', 'wrong-id', 'wrong-type',
                     'out-of-range', 'inconsistent', 'malformed', 'multiple'):
            with self.subTest(mode=mode):
                self.run_case(mode)

    def test_callback_may_delete_sampler(self):
        self.run_case('delete')
        self.run_case('delete-owner')

    def test_late_row_cannot_complete_new_request(self):
        self.run_case('late')

    def test_unsolicited_output_invalidates_idle_helper(self):
        self.run_case('unsolicited')

    def test_overlap_gets_a_reply_and_preserves_first_request(self):
        self.run_case('overlap')

    def test_reset_cancels_old_generation_before_new_request(self):
        self.run_case('cancel')

    def test_helper_exit_completes_pending_request(self):
        self.run_case('exit')

    @unittest.skipUnless(os.environ.get('HICS_TEST_GPU_RECOVERY'), 'Opt-in real 30-second backoff')
    def test_real_backoff_expires_and_fresh_helper_recovers(self):
        self.run_case('recover')
