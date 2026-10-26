"""Fractional point sizes must survive scaling and retain anti-alias preference."""
from pathlib import Path
import subprocess,shlex,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class FontBuilderTests(unittest.TestCase):
 def test_fractional_sizes_and_antialiasing(self):
  with tempfile.TemporaryDirectory(prefix='hics-font-size-') as tmp:
   base=Path(tmp);source=ROOT/'shell/plugin/src/Hyprstack/Config'
   (base/'test.cpp').write_text('''#include "fontbuilder.hpp"
#include <QCoreApplication>
#include <cmath>
int main(int argc,char**argv){QCoreApplication app(argc,argv);QFont font;font.setPointSizeF(12.5);font.setStyleStrategy(QFont::PreferAntialias);
 auto scaled=hyprstack::config::FontBuilder(font).scale(.75).build();
 if(std::abs(scaled.pointSizeF()-9.375)>.001 || !(scaled.styleStrategy()&QFont::PreferAntialias))return 1;
 auto fractional=hyprstack::config::FontBuilder(font).size(10.25).build();
 if(std::abs(fractional.pointSizeF()-10.25)>.001)return 2;
 font.setStyleStrategy(QFont::NoAntialias);font.setHintingPreference(QFont::PreferFullHinting);
 auto plain=hyprstack::config::FontBuilder(font).scale(1.25).build();
 if(plain.styleStrategy()!=QFont::NoAntialias || plain.hintingPreference()!=QFont::PreferFullHinting)return 4;
 auto guarded=hyprstack::config::FontBuilder(font).size(NAN).build();return guarded.pointSizeF()==1?0:3;}
''')
   subprocess.run(['/usr/lib/qt6/moc',str(source/'fontbuilder.hpp'),'-o',str(base/'moc.cpp')],check=True,capture_output=True)
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Gui','Qt6Qml'],text=True))
   result=subprocess.run(['c++','-std=c++20','-fPIC',str(base/'test.cpp'),str(base/'moc.cpp'),str(source/'fontbuilder.cpp'),'-I'+str(source),*flags,'-o',str(base/'probe')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(subprocess.run([str(base/'probe')]).returncode,0)
