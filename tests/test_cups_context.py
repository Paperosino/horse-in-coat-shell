"""CUPS thread defaults survive request reuse and exception unwinding."""
import shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CupsContext(unittest.TestCase):
 def test_parallel_contexts_restore_defaults_on_success_and_failure(self):
  library=ROOT/'build/native/system/libhics-system-backend.a'
  if not library.exists():self.skipTest('Build the system backend first')
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);source=base/'probe.cpp';binary=base/'probe'
   source.write_text('''#include "backend.cpp"
#include <QCoreApplication>
#include <thread>
#include <atomic>
int main(int argc,char**argv){QCoreApplication app(argc,argv);std::atomic_bool ok=true;std::vector<std::thread> threads;
 for(int t=0;t<4;++t)threads.emplace_back([&,t]{auto name=QByteArray("user-")+QByteArray::number(t);cupsSetUser(name.constData());cupsSetServer("sentinel.invalid");
 for(int i=0;i<100;++i){try{System::CupsContext context;if(QByteArray(cupsUser())!="root")ok=false;if(i%2)throw 1;}catch(int){}
 if(QByteArray(cupsUser())!=name||QByteArray(cupsServer())!="sentinel.invalid")ok=false;}});
 for(auto& thread:threads)thread.join();return ok?0:1;}''')
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus'],text=True))
   subprocess.run(['c++','-std=c++20','-fPIC',str(source),str(library),'-I'+str(ROOT/'native/system'),*flags,'-lcups','-pthread','-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True,timeout=5)
