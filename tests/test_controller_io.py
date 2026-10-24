"""Bound actual memory-controller file reads before allocating full contents."""
import shlex,subprocess,tempfile,unittest,os,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ControllerIO(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-controller-io-');cls.addClassCleanup(cls.temp.cleanup);cls.base=Path(cls.temp.name);cls.binary=cls.base/'probe'
  source=cls.base/'probe.cpp';source.write_text('''#include "boundedio.hpp"
#include <QCoreApplication>
#include <QFile>
#include <cstdio>
int main(int argc,char**argv){QCoreApplication app(argc,argv);QFile file(app.arguments()[1]);if(!file.open(QIODevice::ReadOnly))return 2;
 try{auto data=System::readBounded(file,1024);printf("%lld",static_cast<long long>(data.size()));return 0;}catch(const System::Failure&failure){fputs(failure.code.toUtf8().constData(),stdout);return 1;}}''')
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus'],text=True))
  subprocess.run(['c++','-std=c++20','-fPIC',str(source),'-I'+str(ROOT/'native/system'),*flags,'-o',str(cls.binary)],check=True)
 def test_regular_file_is_rejected_before_full_read(self):
  path=self.base/'large';path.write_bytes(b'x'*2048)
  result=subprocess.run([str(self.binary),str(path)],capture_output=True,text=True);self.assertEqual((result.returncode,result.stdout),(1,'invalid'))
 def test_exact_limit_and_empty_file(self):
  for length in (0,1024):
   path=self.base/'small';path.write_bytes(b'x'*length)
   result=subprocess.run([str(self.binary),str(path)],capture_output=True,text=True);self.assertEqual((result.returncode,result.stdout),(0,str(length)))

 def test_stream_cannot_bypass_limit_with_zero_stat_size(self):
  path=self.base/'stream';os.mkfifo(path)
  def write():
   with path.open('wb') as stream:stream.write(b'x'*2048)
  thread=threading.Thread(target=write,daemon=True);thread.start()
  result=subprocess.run([str(self.binary),str(path)],capture_output=True,text=True,timeout=3);thread.join(timeout=3)
  self.assertEqual((result.returncode,result.stdout),(1,'invalid'));self.assertFalse(thread.is_alive())
