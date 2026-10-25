"""Exercise both lazy search engines and list changes in the real QML engine."""
import os, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SearchBackend(unittest.TestCase):
 def test_switch_engine_and_refresh_list(self):
  with tempfile.TemporaryDirectory(prefix='hics-search-') as directory:
   qml=Path(directory)/'shell.qml'
   qml.write_text('''import QtQuick
import Quickshell
import "'''+(ROOT/'shell/utils').as_uri()+'''" as Utils
ShellRoot {
 id:root
 property int phase:0
 QtObject{id:one;property string name:"Firefox Browser"}
 QtObject{id:two;property string name:"Music Player"}
 QtObject{id:three;property string name:"File Manager"}
 Utils.Searcher{id:search;list:[one,two]}
 Timer{interval:100;running:true;repeat:true;onTriggered:{
  function check(value){if(!value){console.error("SEARCH_FAILED",root.phase);Qt.exit(1);}}
  if(root.phase===0){check(search.query("ffox")[0]===one);search.useFuzzy=true;}
  else if(root.phase===1){check(search.query("music")[0]===two);search.list=[three];}
  else if(root.phase===2){check(search.query("file")[0]===three);search.list=[];}
  else if(root.phase===3){check(search.query("file").length===0);search.useFuzzy=false;search.list=[two];}
  else{check(search.query("music")[0]===two);console.log("SEARCH_OK");Qt.quit();}
  root.phase++;
 }}
}''')
   result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(qml)],env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_CACHE_HOME=str(Path(directory)/'cache')),capture_output=True,text=True,timeout=15)
   output=result.stdout+result.stderr
   self.assertEqual(result.returncode,0,output)
   self.assertIn('SEARCH_OK',output)
   self.assertFalse(any(e in output for e in ('TypeError:','ReferenceError:','Binding loop')),output)
