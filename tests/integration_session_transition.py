#!/usr/bin/env python3
"""Production transition handler under real Quickshell IPC, isolated display.

Lock state is injected here; actual WlSessionLock ownership needs VM coverage.
"""
import json,os,re,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
QS='/usr/share/hics/qs/bin/hics-qs'
source=(ROOT/'shell/shell.qml').read_text()
handler=re.search(r'    IpcHandler \{\n        target: "sessionControl".*?\n    }',source,re.S).group()
with tempfile.TemporaryDirectory(prefix='hics-transition-') as directory:
 base=Path(directory);lua=base/'test.lua';lua.write_text('hl.monitor({output="",mode="preferred",position="auto",scale=1})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'absent'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'))
 compositor=None;shell=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(100):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   if compositor.poll() is not None:raise AssertionError((base/'compositor.log').read_text()[-3000:])
   time.sleep(.1)
  assert instance
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland')
  for mode,code in [('on',75),('resume',76)]:
   entry=base/mode;entry.mkdir()
   (entry/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
 QtObject { id:lock;property bool transitioning:false;property QtObject lock:QtObject {property bool locked:true} }
 IpcHandler {target:"fixture";function unlock():void{lock.lock.locked=false;}}
'''+handler+'\n}\n')
   with (base/(mode+'.log')).open('w') as log:shell=subprocess.Popen([QS,'-p',str(entry)],env=env,stdout=log,stderr=subprocess.STDOUT)
   def call(target,method,*args):
    return subprocess.run([QS,'ipc','-p',str(entry),'call',target,method,*args],env=env,text=True,capture_output=True,timeout=4)
   for _ in range(60):
    denied=call('sessionControl','transition',mode)
    if denied.returncode==0:break
    if shell.poll() is not None:raise AssertionError((base/(mode+'.log')).read_text())
    time.sleep(.1)
   assert denied.returncode==0 and denied.stdout.strip()=='false',denied
   assert shell.poll() is None,'Locked shell exited'
   assert call('fixture','unlock').returncode==0
   invalid=call('sessionControl','transition','invalid')
   assert invalid.returncode==0 and invalid.stdout.strip()=='false'
   accepted=call('sessionControl','transition',mode)
   assert shell.wait(timeout=5)==code,(accepted,(base/(mode+'.log')).read_text())
   print(mode,'IPC reply:',accepted.returncode,repr(accepted.stdout.strip()),'shell exit:',code)
  print('PASS: locked/invalid transitions refused, both accepted modes exit through real production IPC')
 finally:
  for p in (shell,compositor):
   if p and p.poll() is None:
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
