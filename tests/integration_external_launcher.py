#!/usr/bin/env python3
"""QML list/map launches must use host libraries and preserve the working dir."""
import os,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-external-launch-') as directory:
 base=Path(directory);script=base/'child.py';a=base/'a.json';b=base/'b.json'
 script.write_text('import os,json,sys,pathlib\npathlib.Path(sys.argv[1]).write_text(json.dumps({"ld":os.environ.get("LD_LIBRARY_PATH"),"cwd":str(pathlib.Path.cwd())}))\n')
 qml=base/'shell.qml';qml.write_text('''import QtQuick
import Quickshell
import Hyprstack
ShellRoot {
 Component.onCompleted:{
  if(!CUtils.execDetached(["/usr/bin/python3",SCRIPT,A]))throw new Error("List launch failed");
  if(!CUtils.execDetached({command:["/usr/bin/python3",SCRIPT,B],workingDirectory:DIR}))throw new Error("Map launch failed");
 }
 Timer {interval:700;running:true;onTriggered:Qt.quit()}
}'''.replace('SCRIPT',json.dumps(str(script))).replace('DIR',json.dumps(str(base))).replace('A]',json.dumps(str(a))+']').replace('B]',json.dumps(str(b))+']'))
 env=dict(os.environ,QT_QPA_PLATFORM='offscreen',LD_LIBRARY_PATH='/usr/share/hics/qs/lib',HYPRSTACK_DATA_DIR='/usr/share/hics',QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'))
 env.pop('WAYLAND_DISPLAY',None);env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 r=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(qml)],env=env,capture_output=True,text=True,timeout=5)
 assert r.returncode==0 and a.exists() and b.exists(),r.stdout+r.stderr
 assert json.loads(a.read_text())['ld'] is None
 assert json.loads(b.read_text())=={'ld':None,'cwd':str(base)}
 print('PASS: QML list/map external launches strip bundled libraries and preserve working directory')
