"""Production JSON quoting survives the real Qt JS and Lua parsers."""
import json,re,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class LuaPayload(unittest.TestCase):
 def test_controls_unicode_and_long_string_delimiters_round_trip(self):
  source=(ROOT/'shell/services/Hypr.qml').read_text()
  body=re.search(r'function luaJsonText\(text: string\): string \{(.*?)\n    }',source,re.S).group(1)
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);probe=base/'probe.cpp';binary=base/'probe'
   probe.write_text('''#include <QCoreApplication>
#include <QJSEngine>
#include <QJSValue>
#include <cstdio>
int main(int argc,char**argv){QCoreApplication app(argc,argv);QJSEngine engine;
 auto function=engine.evaluate(QString::fromUtf8(R"HICS((function(text){BODY\n}))HICS"));
 const auto result=function.call({app.arguments()[1]});if(result.isError())return 1;
 const auto bytes=result.toString().toUtf8();fwrite(bytes.constData(),1,bytes.size(),stdout);return 0;}'''.replace('BODY',body))
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Qml'],text=True))
   subprocess.run(['c++','-fPIC','-std=c++20',str(probe),*flags,'-o',str(binary)],check=True)
   payload=json.dumps({'title':'Русский "title"\n\t\0\u2028 ]=] ]==] ]===]','attempt':']] .. os.execute("false") .. [['},ensure_ascii=False)
   quoted=subprocess.check_output([str(binary),payload],text=True)
   restored=subprocess.check_output(['lua','-e','io.write('+quoted+')'],text=True)
   self.assertEqual(restored,payload)
