"""Build the optional collector independently; check coherent PCM snapshots."""
import os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'

def build_probe(base):
 flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Qml','libpipewire-0.3'],text=True))
 moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
 qtflags=shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6Qml'],text=True))
 for name in ('audiocollector','service'):subprocess.run([str(moc),str(SERVICES/(name+'.hpp')),'-o',str(base/(name+'-moc.cpp')),*qtflags],check=True)
 source=base/'probe.cpp';source.write_text('''#include "audiocollector.hpp"
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QThread>
#include <array>
#include <thread>
#include <atomic>
#include <cassert>
#include <iostream>
using namespace hyprstack::services;
int main(int argc,char**argv){QCoreApplication app(argc,argv);auto&collector=AudioCollector::instance();
 if(app.arguments().value(1)=="buffers"){
 std::atomic_bool done=false,valid=true;
 std::thread producer([&]{std::array<qint16,128> samples;for(int n=1;n<100000;++n){samples.fill(qint16((n%31+1)*500));collector.loadChunk(samples.data(),samples.size());}done=true;});
 auto read=[&]{std::array<float,ac::k_chunkSize> frame;do{collector.readChunk(frame.data());for(int i=1;i<128;++i)if(frame[i]!=frame[0])valid=false;for(unsigned i=128;i<frame.size();++i)if(frame[i]!=0)valid=false;}while(!done);};
 std::thread a(read),b(read);producer.join();a.join();b.join();assert(valid);
 std::array<qint16,512> full;full.fill(1000);collector.loadChunk(full.data(),full.size());collector.clearBuffer();std::array<double,512> empty;collector.readChunk(empty.data());for(auto x:empty)assert(x==0);return 0;
 }
 QObject consumer;
 collector.ref(&consumer);std::cout<<"started"<<std::endl;
 std::string line;
 while(std::getline(std::cin,line)){
  if(line=="stop"){QElapsedTimer timer;timer.start();collector.unref(&consumer);std::cout<<"stopped "<<timer.elapsed()<<std::endl;}
  if(line=="start"){collector.ref(&consumer);std::cout<<"started"<<std::endl;}
  if(line=="quit")break;
 }
 collector.unref(&consumer);
}''')
 binary=base/'probe'
 subprocess.run(['c++','-std=c++20','-fPIC','-O2',str(source),str(SERVICES/'audiocollector.cpp'),str(SERVICES/'service.cpp'),str(base/'audiocollector-moc.cpp'),str(base/'service-moc.cpp'),'-I'+str(SERVICES),'-I'+str(ROOT/'shell/plugin/include'),*flags,'-pthread','-o',str(binary)],check=True)
 return binary

class AudioCollectorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-audio-tests-');cls.addClassCleanup(cls.temp.cleanup);cls.base=Path(cls.temp.name);cls.binary=build_probe(cls.base)
 def test_parallel_readers_never_observe_torn_or_stale_tail(self):subprocess.run([str(self.binary),'buffers'],check=True,timeout=10)
 def test_repeated_stop_without_audio_server(self):
  runtime=self.base/'runtime';runtime.mkdir(mode=0o700,exist_ok=True)
  env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),PIPEWIRE_RUNTIME_DIR=str(runtime),PIPEWIRE_REMOTE='hics-nonexistent-test-server')
  result=subprocess.run([str(self.binary)],input=('stop\nstart\n'*30)+'stop\nquit\n',text=True,capture_output=True,env=env,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('stopped '),31)
  for line in result.stdout.splitlines():
   if line.startswith('stopped '):self.assertLess(int(line.split()[1]),400,line)
