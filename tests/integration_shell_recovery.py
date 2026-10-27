#!/usr/bin/env python3
"""Real recovery QML, helper and rollback guard in an isolated compositor."""
import json, os, signal, subprocess, sys, tempfile, time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics real recovery ') as directory:
 base=Path(directory);entry=base/'installed shell/recovery';entry.mkdir(parents=True)
 (entry.parent/'assets').symlink_to(ROOT/'shell/assets',target_is_directory=True)
 config=base/'config/hics';config.mkdir(parents=True)
 (config/'shell.json').write_text('{"appearance":{"scale":1}}')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),HICS_CONFIG_NO_SYSTEMD='1',HICS_DISPLAY_NO_SYSTEMD='1',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'absent-session'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'))
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 subprocess.run([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);import shell_recovery as r;assert r.healthy(r.candidate())',str(ROOT/'shell/assets')],env=env,check=True)
 (config/'shell.json').write_text('{"appearance":{"scale":1.5}}')
 warning=base/'state/hics/configuration-recovery-warning.json';warning.write_text(json.dumps({'warning':'dock.json: fixture unsafe section preserved'}))
 damaged_crash_record=base/'state/hics/shell-recovery.json'
 damaged_crash_record.write_bytes(b'{invalid\xff')
 fixture=(ROOT/'shell/recovery/shell.qml').read_text()
 checks='''
 property int phase:0
 property int attempts:0
 property string previewToken:""
 function fail(message){console.error("RECOVERY_REAL_FAILED",message);Qt.quit();}
 Timer {interval:200;running:true;repeat:true;onTriggered:{
  if(++root.attempts>100){root.fail("Timed out");return;}
  if(worker.running)return;
  if(root.phase!==3&&root.error){root.fail(root.error);return;}
  if(root.phase===0){
   if(!recoveryWarningText.visible || !recoveryWarningText.text.includes("fixture unsafe section")){root.fail("Recovery warning is not visible");return;}
   if(!recoveryWarningText.text.includes("state is unknown")){root.fail("Damaged crash journal warning is not visible");return;}
   if(!root.data.startupCheckpoint?.available){root.fail("Real checkpoint is not visible");return;}
   root.invoke("restore");root.phase=1;
  }else if(root.phase===1){
   if(!root.data.pending?.token||root.remaining<1||root.remaining>30){root.fail("No real guarded preview");return;}
   root.previewToken=root.data.pending.token;root.invoke("status");root.phase=2;
  }else if(root.phase===2){
   if(root.data.pending?.token!==root.previewToken){root.fail("Preview vanished while recovery UI was alive");return;}
   root.helperCommand=["python3",Quickshell.shellDir+"/missing-helper.py"];root.invoke("status");root.phase=3;
  }else{
   if(!root.error.includes("missing-helper.py")||root.error.includes("invalid response")){root.fail("Missing helper lost its actual error");return;}
   console.log("RECOVERY_REAL_OK");Qt.quit();
  }
 }}
'''
 (entry/'shell.qml').write_text(fixture[:fixture.rfind('}')]+checks+'}\n')
 lua=base/'compositor.lua';lua.write_text('hl.monitor({output="",mode="preferred",position="auto",scale=1})\n')
 compositor=guard=None
 try:
  with (base/'compositor.log').open('w') as log:
   compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  instance=None
  for _ in range(100):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   if compositor.poll() is not None:raise AssertionError((base/'compositor.log').read_text()[-5000:])
   time.sleep(.1)
  assert instance,'No nested compositor'
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland',QT_QUICK_CONTROLS_STYLE='Basic',FONTCONFIG_FILE=str(ROOT/'shell/recovery/fonts.conf'))
  with (base/'guard.log').open('w') as log:
   guard=subprocess.Popen([sys.executable,str(ROOT/'shell/assets/configuration_manager.py'),'watch'],env=env,stdout=log,stderr=subprocess.STDOUT)
  result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','--path',str(entry)],env=env,capture_output=True,text=True,timeout=30)
  output=result.stdout+result.stderr
  Path('/tmp/hics-recovery-real.log').write_text(output)
  assert result.returncode==0 and 'RECOVERY_REAL_OK' in output and 'RECOVERY_REAL_FAILED' not in output,output[-6000:]
  assert damaged_crash_record.read_bytes()==b'{invalid\xff','Status silently rewrote damaged crash evidence'
  assert json.loads((config/'shell.json').read_text())['appearance']['scale']==1
  journal=base/'state/hics/configuration-preview.json';pending=json.loads(journal.read_text())
  assert pending['shellPid'] is None,'Intentional UI restart must not cancel a startup restore'
  reverted=subprocess.run([sys.executable,str(ROOT/'shell/assets/configuration_manager.py'),'revert'],env=env,input=json.dumps({'token':pending['token']}),capture_output=True,text=True,timeout=10)
  assert reverted.returncode==0,reverted.stdout+reverted.stderr
  assert json.loads((config/'shell.json').read_text())['appearance']['scale']==1.5
  assert all(not (config/name).exists() for name in ('dock.json','shell-tokens.json','panels.json','effects.json')),'Rollback created files absent before preview'
  print('PASS: independent recovery QML resolves real helper outside shell root, reads checkpoint, starts guarded restore and reverts actual settings')
 finally:
  for process in (guard,compositor):
   if process and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
