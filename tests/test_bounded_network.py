"""Exercise real Qt HTTP draining against hostile sizes and chunked responses."""
import contextlib,json,shlex,subprocess,tempfile,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class BoundedNetwork(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);base=Path(cls.tmp.name);cls.bin=base/'probe'
  source=base/'probe.cpp';source.write_text('''#include "boundednetwork.hpp"
#include <QCoreApplication>
#include <QNetworkAccessManager>
#include <QJsonDocument>
#include <QJsonObject>
int main(int argc,char**argv){QCoreApplication app(argc,argv);QNetworkAccessManager manager;
 auto*r=manager.get(QNetworkRequest(QUrl(app.arguments()[1])));hics::boundNetworkReply(r,65536);
 QObject::connect(r,&QNetworkReply::finished,&app,[&]{auto b=hics::networkBody(r);QJsonObject o{{"bytes",int(b.size())},{"error",int(r->error())},{"oversize",r->property("hicsResponseTooLarge").toBool()}};puts(QJsonDocument(o).toJson(QJsonDocument::Compact).constData());app.quit();});
 QTimer::singleShot(5000,&app,&QCoreApplication::quit);return app.exec();}''')
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Network'],text=True))
  subprocess.run(['c++','-std=c++20','-fPIC',str(source),'-I'+str(ROOT/'shell/plugin/src/Hyprstack'),*flags,'-o',str(cls.bin)],check=True)
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    body=b'hello' if self.path=='/small' else b'x'*(2*1024*1024)
    self.send_response(200)
    if self.path!='/stream':self.send_header('Content-Length',str(len(body)))
    self.end_headers()
    with contextlib.suppress(BrokenPipeError,ConnectionResetError):
     for i in range(0,len(body),4096):self.wfile.write(body[i:i+4096]);self.wfile.flush()
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
  cls.addClassCleanup(cls.server.server_close);cls.addClassCleanup(cls.server.shutdown)
 def probe(self,path):
  r=subprocess.run([str(self.bin),f'http://127.0.0.1:{self.server.server_port}/{path}'],capture_output=True,text=True,timeout=8);self.assertEqual(r.returncode,0,r.stderr);return json.loads(r.stdout)
 def test_small_body_preserved(self):self.assertEqual(self.probe('small'),{'bytes':5,'error':0,'oversize':False})
 def test_content_length_does_not_allow_unbounded_buffer(self):
  r=self.probe('large');self.assertTrue(r['oversize']);self.assertNotEqual(r['error'],0);self.assertEqual(r['bytes'],0)
 def test_stream_without_content_length_is_bounded(self):
  r=self.probe('stream');self.assertTrue(r['oversize']);self.assertNotEqual(r['error'],0);self.assertEqual(r['bytes'],0)
