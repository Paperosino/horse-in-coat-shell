#!/usr/bin/env python3
"""Burst edits coalesce, preserve callbacks, and never cross read/write barriers."""
import json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-coalesce-') as directory:
 base=Path(directory);shell=base/'shell'
 for folder in ('components','utils'): (shell/folder).mkdir(parents=True)
 shutil.copy2(ROOT/'shell/components/FeatureBackend.qml',shell/'components/FeatureBackend.qml')
 (shell/'utils/Paths.qml').write_text('pragma Singleton\nimport Quickshell\nSingleton {function toLocalFile(path){return path.toString().replace("file://","")}}')
 log=base/'calls.jsonl';helper=base/'helper'
 helper.write_text('#!/usr/bin/python3\nimport json,sys\np=json.load(sys.stdin) if sys.argv[1]=="save" else {}\nwith open('+repr(str(log))+',"a") as f:f.write(json.dumps([sys.argv[1],p])+"\\n")\nprint(json.dumps(p))\n');helper.chmod(0o700)
 (shell/'shell.qml').write_text('''import QtQuick
import Quickshell
import qs.components
ShellRoot {
 id:root
 property int replies:0
 FeatureBackend{id:backend;executable:HELPER;coalescePatches:["save"]}
 function require(value,message){if(!value){console.error(message);Qt.exit(1);throw new Error(message)}}
 Component.onCompleted:{
  for(let i=0;i<100;i++)backend.call(["save"],{value:i},d=>{require(d.value===99,"patch lost");root.replies++;});
  for(let i=0;i<100;i++)backend.call(["list"],null,d=>root.replies++);
  backend.call(["save"],{after:true},d=>{require(d.after,"write barrier lost");root.replies++;});
  backend.call(["list"],null,d=>root.replies++);
 }
 Timer{interval:20;repeat:true;running:true;onTriggered:if(root.replies===202&&!backend.busy){console.log("COALESCING_OK");Qt.exit(0)}}
 Timer{interval:8000;running:true;onTriggered:Qt.exit(1)}
}'''.replace('HELPER',json.dumps(str(helper))))
 env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),QML_IMPORT_PATH=str(ROOT/'build/qml'))
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);env.pop('WAYLAND_DISPLAY',None)
 result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(shell)],env=env,capture_output=True,text=True,timeout=12)
 assert result.returncode==0 and 'COALESCING_OK' in result.stdout+result.stderr,result.stdout+result.stderr
 rows=[json.loads(line) for line in log.read_text().splitlines()]
 assert rows==[['save',{'value':99}],['list',{}],['save',{'after':True}],['list',{}]],rows
 print('PASS: 202 edit/read callbacks use four helper processes and preserve mutation barriers')
