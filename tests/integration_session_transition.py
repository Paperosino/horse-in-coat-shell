#!/usr/bin/env python3
"""Production transition handler and real Wayland session lock, isolated display.

Authentication is a fixture; this never unlocks the parent desktop.
"""
import json,os,re,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
QS='/usr/share/hics/qs/bin/hics-qs'
source=(ROOT/'shell/shell.qml').read_text()
handler=re.search(r'    IpcHandler \{\n        target: "sessionControl".*?\n    }',source,re.S).group()
lock_source=(ROOT/'shell/modules/lock/Lock.qml').read_text()
request_lock=re.search(r'    function requestLock\(\): void \{.*?\n    }',lock_source,re.S).group()
with tempfile.TemporaryDirectory(prefix='hics-transition-') as directory:
 base=Path(directory);lua=base/'test.lua';lua.write_text('hl.monitor({output="",mode="preferred",position="auto",scale=1})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'absent'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'))
 compositor=None;shell=None;racers=[]
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
   (entry/'shell.qml').write_text(('''import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
ShellRoot {
 Scope {
  id:lock
  property bool transitioning:false
  property alias lock:nativeLock
__REQUEST_LOCK__
  WlSessionLock {id:nativeLock;locked:true;WlSessionLockSurface {color:"#1c1b22"}}
 }
 IpcHandler {target:"fixture";function unlock():void{lock.lock.locked=false;}function lock():void{lock.requestLock();}}
'''+handler+'\n}\n').replace('__REQUEST_LOCK__',request_lock))
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
   def wait_locked(expected):
    for _ in range(60):
     value=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'-j','locked']))['locked']
     if value==expected:return
     time.sleep(.05)
    raise AssertionError('Nested compositor lock state did not reach '+str(expected))
   wait_locked(True)
   assert call('fixture','unlock').returncode==0
   wait_locked(False)
   invalid=call('sessionControl','transition','invalid')
   assert invalid.returncode==0 and invalid.stdout.strip()=='false'
   commands=[['call','fixture','lock'],['call','sessionControl','transition',mode]]
   if mode=='resume':commands.reverse()
   racers=[subprocess.Popen([QS,'ipc','-p',str(entry),*args],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for args in commands]
   results=[p.communicate(timeout=5) for p in racers]
   transition=results[0 if mode=='resume' else 1][0].strip()
   if transition=='false':
    assert shell.poll() is None,'Rejected transition killed lock owner'
    wait_locked(True)
    assert call('fixture','unlock').returncode==0
    wait_locked(False)
    accepted=call('sessionControl','transition',mode)
   else:
    assert transition=='true',results
    accepted=transition
   assert shell.wait(timeout=5)==code,(accepted,(base/(mode+'.log')).read_text())
   wait_locked(False)
   print(mode,'race reply:',transition,'shell exit:',code,'compositor unlocked after accepted transition')
  print('PASS: real Wayland lock rejects transitions, concurrent lock/transition leaves no abandoned lock')
 finally:
  for p in [*racers,shell,compositor]:
   if p and p.poll() is None:
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
