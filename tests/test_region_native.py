"""Exercise native locale validation and format preservation, without mutations."""
import json,shlex,subprocess,tempfile,unittest,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class NativeRegion(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not shutil.which('c++'):raise unittest.SkipTest('C++ compiler required')
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-region-native-');cls.addClassCleanup(cls.temp.cleanup)
  base=Path(cls.temp.name);cls.bin=base/'probe'
  source=base/'probe.cpp';source.write_text('''#include "backend.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonArray>
#include <QTextStream>
int main(int argc,char **argv){QCoreApplication app(argc,argv);auto a=app.arguments();
 if(a[1]=="assign"){auto d=QJsonDocument::fromJson(a[2].toUtf8());QStringList old;for(auto x:d.array())old<<x.toString();QTextStream(stdout)<<QJsonDocument(QJsonArray::fromStringList(System::regionAssignments(old,a[3],a[4]=="all"))).toJson(QJsonDocument::Compact);return 0;}
 try{System::validateRegion("locale",QJsonDocument::fromJson(a[2].toUtf8()).object());QTextStream(stdout)<<"accepted";return 0;}catch(const System::Failure&e){QTextStream(stdout)<<e.code;return 1;}}
''')
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus'],text=True))
  subprocess.run(['c++','-fPIC','-std=c++20',str(source),str(ROOT/'native/system/region.cpp'),'-I'+str(ROOT/'native/system'),'-DHYPRSTACK_SYSTEMD_RUN="/usr/bin/systemd-run"','-DHYPRSTACK_REGION_EXECUTABLE="/usr/bin/hics-region"',*flags,'-o',str(cls.bin)],check=True)
 def assignments(self,old,all_formats=False):
  return json.loads(subprocess.check_output([str(self.bin),'assign',json.dumps(old),'ru_RU.UTF-8','all' if all_formats else 'language'],text=True))
 def test_language_only_preserves_inherited_formats(self):
  values=self.assignments(['LANG=en_US.UTF-8'])
  self.assertIn('LANG=ru_RU.UTF-8',values);self.assertIn('LC_TIME=en_US.UTF-8',values);self.assertIn('LC_NUMERIC=en_US.UTF-8',values)
 def test_explicit_formats_preserved_but_old_message_language_removed(self):
  values=self.assignments(['LANG=en_US.UTF-8','LC_TIME=de_DE.UTF-8','LANGUAGE=en','LC_MESSAGES=en_US.UTF-8'])
  self.assertIn('LC_TIME=de_DE.UTF-8',values);self.assertFalse(any(v.startswith(('LANGUAGE=','LC_MESSAGES=')) for v in values))
 def test_unconfigured_system_keeps_default_formats(self):
  self.assertIn('LC_TIME=C.UTF-8',self.assignments([]))
 def test_all_formats_uses_only_selected_lang(self):
  self.assertEqual(self.assignments(['LANG=en_US.UTF-8','LC_TIME=de_DE.UTF-8'],True),['LANG=ru_RU.UTF-8'])
 def test_invalid_requests_cannot_reach_privileged_worker(self):
  for data in [{'locale':'ru_RU.UTF-8;touch /tmp/invalid'},{'locale':'/etc/passwd'},{'locale':'ru_RU.UTF-8','allFormats':'yes'},{'locale':'ru_RU.UTF-8','command':'anything'}]:
   run=subprocess.run([str(self.bin),'validate',json.dumps(data)],capture_output=True,text=True);self.assertEqual(run.returncode,1);self.assertEqual(run.stdout,'invalid')
if __name__=='__main__':unittest.main()
