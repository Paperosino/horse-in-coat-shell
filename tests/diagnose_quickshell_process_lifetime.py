#!/usr/bin/env python3
"""Three running QS Process children at QML/application shutdown, ASan/LSan."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
QML = '''import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
 id:root
 property int started:0
 function ready(pid){console.log("CHILD_PID",pid);if(++started===3)finish.start();}
 Process {command:["/usr/bin/sleep","30"];running:true;onStarted:root.ready(processId)}
 Process {command:["/usr/bin/sleep","30"];running:true;onStarted:root.ready(processId)}
 Process {command:["/usr/bin/sleep","30"];running:true;onStarted:root.ready(processId)}
 Timer {id:finish;interval:10;onTriggered:{console.log("PROCESSES_COMPLETE");Qt.quit();}}
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--executable',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():p.error('Use fresh evidence path')
 with tempfile.TemporaryDirectory(prefix='hics-qs-process-lifetime-') as d:
  root=Path(d);(root/'run').mkdir(mode=0o700);(root/'shell.qml').write_text(QML)
  config=root/'bus.conf';config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(root)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
  bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(config)],stdout=subprocess.PIPE,text=True)
  try:
   address=bus.stdout.readline().strip();assert address
   env=dict(os.environ,HOME=str(root),XDG_RUNTIME_DIR=str(root/'run'),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),XDG_STATE_HOME=str(root/'state'),XDG_CACHE_HOME=str(root/'cache'),DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'absent'),QT_QPA_PLATFORM='offscreen',QT_NO_XDG_DESKTOP_PORTAL='1',LD_LIBRARY_PATH=str(a.runtime/'lib'),QT_PLUGIN_PATH=str(a.runtime/'lib/qt6/plugins'),QML_IMPORT_PATH=str(a.runtime/'lib/qt6/qml'),QML2_IMPORT_PATH=str(a.runtime/'lib/qt6/qml'),LD_PRELOAD='/usr/lib/libasan.so.8',ASAN_OPTIONS='detect_leaks=1:halt_on_error=1')
   for key in ('LSAN_OPTIONS','WAYLAND_DISPLAY','HYPRLAND_INSTANCE_SIGNATURE'):env.pop(key,None)
   executable=a.executable or a.runtime/'bin/hics-qs'
   result=subprocess.run([str(executable),'-p',str(root/'shell.qml'),'--no-duplicate'],env=env,capture_output=True,text=True,timeout=15)
   text=result.stdout+result.stderr;a.output.with_suffix('.log').write_text(text)
   pids=[int(value) for value in re.findall(r'CHILD_PID (\d+)',text)]
   live=[]
   for pid in pids:
    stat=Path('/proc')/str(pid)/'stat'
    if stat.exists() and stat.read_text().rsplit(')',1)[1].split()[0]!='Z':live.append(pid)
   report={'code':result.returncode,'startedChildren':len(pids),'liveChildrenAfterExit':live,'complete':'PROCESSES_COMPLETE' in text,'executableSha256':hashlib.sha256(executable.read_bytes()).hexdigest(),'scope':'Private QML Process final shutdown, not every subprocess scenario'}
   a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
   return 0 if result.returncode==0 and report['complete'] and len(pids)==3 and not live and 'Destroyed while process' not in text else 1
  finally:bus.terminate();bus.wait(timeout=5);bus.stdout.close()
if __name__=='__main__':raise SystemExit(main())
