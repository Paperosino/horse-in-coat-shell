"""Exercise the actual Qt JS controller with reordered/deferred IPC callbacks."""
import json,os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class KeyboardStateBindings(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);base=Path(cls.tmp.name);cls.binary=base/'probe'
  source=base/'probe.cpp';source.write_text('''#include <QCoreApplication>
#include <QJSEngine>
#include <QFile>
#include <QTextStream>
int main(int argc,char**argv){QCoreApplication app(argc,argv);QJSEngine engine;engine.installExtensions(QJSEngine::ConsoleExtension);
 QFile file(app.arguments()[1]);if(!file.open(QIODevice::ReadOnly))return 2;auto source=QString::fromUtf8(file.readAll());source.remove(0,source.indexOf('\\n')+1);
 auto value=engine.evaluate(source);if(value.isError()){QTextStream(stderr)<<value.toString();return 3;}
 const auto test=QTextStream(stdin).readAll();value=engine.evaluate("JSON.stringify((function(){"+test+"\\n})())");
 if(value.isError()){QTextStream(stderr)<<value.toString();return 4;}
 QTextStream(stdout)<<value.toString();}''')
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Qml'],text=True))
  subprocess.run(['c++','-std=c++20','-fPIC',str(source),*flags,'-o',str(cls.binary)],check=True)
 def probe(self,body):
  prelude='var sent=[];var transport={request:function(text,done){sent.push({text:text,done:done});}};var c=create();'
  r=subprocess.run([str(self.binary),str(ROOT/'shell/services/KeyboardStateBindings.js')],input=prelude+body,env=dict(os.environ,QT_FORCE_STDERR_LOGGING='1'),capture_output=True,text=True,timeout=5)
  self.assertEqual(r.returncode,0,r.stderr);self.last_stderr=r.stderr;return json.loads(r.stdout)
 def test_lua_burst_is_coalesced_until_ack(self):
  r=self.probe('''for(var i=0;i<30;i++)c.update(transport,true);var first=sent.length;
 sent[0].done(true,"ok");var second=sent.length;sent[1].done(true,"ok");
 return {first:first,second:second,busy:c.busy(),same:sent[0].text===sent[1].text};''')
  self.assertEqual(r,{'first':1,'second':2,'busy':False,'same':True})
 def test_stale_legacy_snapshot_is_discarded(self):
  r=self.probe('''c.update(transport,false);c.update(transport,false);sent[0].done(true,"[]");
 var before=sent.map(x=>x.text);sent[1].done(true,"[]");var pending=c.busy();sent[2].done(true,"ok\\n\\nok");
 return {before:before,pending:pending,busy:c.busy(),commit:sent[2].text};''')
  self.assertEqual(r['before'],['j/binds','j/binds']);self.assertTrue(r['pending']);self.assertFalse(r['busy']);self.assertTrue(r['commit'].startswith('[[BATCH]]'))
 def test_parser_change_never_commits_old_legacy_snapshot(self):
  r=self.probe('''c.update(transport,false);c.update(transport,true);sent[0].done(true,"[]");sent[1].done(true,"ok");return {messages:sent.map(x=>x.text),busy:c.busy()};''')
  self.assertEqual(r['messages'][0],'j/binds');self.assertTrue(r['messages'][1].startswith('eval '));self.assertFalse(r['busy'])
 def test_only_missing_global_binding_is_added_and_queue_waits_for_commit(self):
  r=self.probe('''var caps={key:"Caps_Lock",modmask:0,submap:"",dispatcher:"global",arg:"hyprstack:refreshDevices",locked:true,non_consuming:true,release:false};
 c.update(transport,false);sent[0].done(true,JSON.stringify([caps]));var commit=sent[1].text;
 c.update(transport,false);var before=sent.length;sent[1].done(true,"ok");
 var num=Object.assign({},caps,{key:"Num_Lock"});sent[2].done(true,JSON.stringify([caps,num]));return {commit:commit,before:before,total:sent.length,busy:c.busy()};''')
  self.assertNotIn('Caps_Lock',r['commit']);self.assertIn('Num_Lock',r['commit']);self.assertEqual(r['before'],2);self.assertEqual(r['total'],3);self.assertFalse(r['busy'])
 def test_failure_releases_queue_without_logging_raw_ipc_response(self):
  r=self.probe('''c.update(transport,true);sent[0].done(false,"synthetic-private-token");var idle=!c.busy();c.update(transport,true);sent[1].done(true,"ok");return {idle:idle,busy:c.busy(),total:sent.length};''')
  self.assertEqual(r,{'idle':True,'busy':False,'total':2});self.assertIn('Unable to install',self.last_stderr);self.assertNotIn('synthetic-private-token',self.last_stderr)
 def test_malformed_legacy_and_rejected_commit_allow_retry(self):
  r=self.probe('''c.update(transport,false);sent[0].done(true,"bad-json");var first=!c.busy();c.update(transport,false);sent[1].done(true,"[null,1,{},[]]");sent[2].done(true,"rejected");var second=!c.busy();c.update(transport,false);return {first:first,second:second,total:sent.length,pending:c.busy()};''')
  self.assertEqual(r,{'first':True,'second':True,'total':4,'pending':True})
