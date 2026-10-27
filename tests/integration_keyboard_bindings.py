#!/usr/bin/env python3
"""Repeat the production keyboard bind installer across shell/config lifetimes."""
import json,os,re,shutil,signal,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session,snapshot_qml_runtime,run_snapshot_qml
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'shell/services/Hypr.qml').read_text()
body=re.search(r'function reloadDynamicConfs\(\): void \{(.*?)\n    }',source,re.S).group(1)
for mode in ('lua','legacy'):
 with tempfile.TemporaryDirectory(prefix='hics keyboard binds ') as directory:
  base=Path(directory);entry=base/'shell';entry.mkdir();cfg=base/('compositor.lua' if mode=='lua' else 'compositor.conf')
  if mode=='lua':
   cfg.write_text('hl.monitor({output="",mode="preferred",position="auto",scale=1})\n'+''.join('hl.bind("'+key+'",function() end,{description="User '+name+'"})\n' for key,name in [('Caps_Lock','Caps'),('Caps_Lock','Caps alternate'),('Num_Lock','Num')]))
  else:
   cfg.write_text('monitor = ,preferred,auto,1\n'+''.join('bindd = ,'+key+',User '+name+',exec,true\n' for key,name in [('Caps_Lock','Caps'),('Caps_Lock','Caps alternate'),('Num_Lock','Num')]))
  env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),AQ_BACKEND='wayland',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'absent-session'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'))
  Path(env['HOME']).mkdir();env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(cfg)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   instance=None
   for _ in range(100):
    instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
    if instance:break
    if compositor.poll() is not None:raise AssertionError((base/'compositor.log').read_text()[-4000:])
    time.sleep(.1)
   assert instance,'No nested compositor'
   def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],env=env,text=True,timeout=8).strip()
   assert not ctl('configerrors'),ctl('configerrors')
   original=json.loads(ctl('-j','binds'));assert len(original)==3,original
   helper=ROOT/'shell/services/KeyboardStateBindings.js'
   (entry/'KeyboardStateBindings.js').write_text(helper.read_text() if helper.exists() else '.pragma library\nfunction create(){return {busy:function(){return false;}};}')
   (entry/'shell.qml').write_text('''import QtQuick
import Quickshell
import Hyprstack.Services
import "KeyboardStateBindings.js" as KeyboardStateBindings
ShellRoot {
 id:root
 property bool usingLua: __LUA__
 property var deviceBindingController
 HyprExtras {id:extras}
 function reloadDynamicConfs():void {__BODY__}
 onUsingLuaChanged:reloadDynamicConfs()
 Component.onCompleted:reloadDynamicConfs()
 property int phase:0
 Timer {interval:100;running:true;repeat:true;onTriggered:{
  if(root.phase++===0){for(let i=0;i<30;i++)root.reloadDynamicConfs();}
  if(root.phase>10&&!root.deviceBindingController.busy()){console.log("KEYBOARD_BINDS_SENT");Qt.quit();}
 }}
}'''.replace('__LUA__','true' if mode=='lua' else 'false').replace('__BODY__',body))
   env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland')
   env.update(snapshot_qml_runtime(ROOT,base))
   for stage in ('initial','shell-restart','config-reload'):
    if stage=='config-reload':
     ctl('reload');assert not ctl('configerrors'),ctl('configerrors')
     assert len(json.loads(ctl('-j','binds')))==3,'Reload did not clear dynamic binds'
    result=run_snapshot_qml(['/usr/share/hics/qs/bin/hics-qs','-p',str(entry)],env,ROOT/'build',15)
    output=result.stdout+result.stderr
    assert result.returncode==0 and 'KEYBOARD_BINDS_SENT' in output,output[-4000:]
    assert not any(x in output for x in ('TypeError:','ReferenceError:','Binding loop','Unable to install keyboard-state')),output[-4000:]
    current=json.loads(ctl('-j','binds'))
    assert len(current)==5,(mode,stage,'Repeated registration grew binds',len(current))
    users=[{k:v for k,v in row.items() if k!='arg' or mode=='legacy'} for row in current if row['description'].startswith('User ')]
    expected=[{k:v for k,v in row.items() if k!='arg' or mode=='legacy'} for row in original]
    assert users==expected,(mode,stage,'User bindings changed')
   print('PASS:',mode,'30 calls x three shell lifetimes; config reload restores binds; three user bindings preserved')
  finally:
   try:os.killpg(compositor.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   try:compositor.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(compositor.pid,signal.SIGKILL);compositor.wait()
