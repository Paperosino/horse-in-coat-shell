#!/usr/bin/env python3
"""Real display previews, shell crash timeout, watchdog recovery and hotplug."""
import json,os,signal,shlex,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session();ROOT=Path(__file__).resolve().parents[1];HELPER=ROOT/'shell/assets/display_profiles.py'
with tempfile.TemporaryDirectory(prefix='hics-display-integration-') as directory:
 base=Path(directory);config=base/'config/hics';config.mkdir(parents=True);file=config/'monitors.lua';file.write_text('-- preserved display configuration\n')
 lua=base/'test.lua';lua.write_text('hl.monitor({output="",mode="preferred",position="auto",scale=1})\ndofile('+json.dumps(str(file))+')\n')
 env=dict(os.environ,AQ_BACKEND='wayland,headless',XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),HICS_DISPLAY_NO_SYSTEMD='1');env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=watcher=shell=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(100):
   instance=next((m for m in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if m['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance,(base/'compositor.log').read_text()
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland',QT_QUICK_BACKEND='software')
  def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],env=env,text=True,timeout=10)
  def monitors():return json.loads(ctl('monitors','all','-j'))
  def wait_for(check,timeout=8):
   end=time.monotonic()+timeout
   while time.monotonic()<end:
    value=check()
    if value:return value
    time.sleep(.1)
   raise AssertionError('Display condition timed out: '+str(monitors()))
  wait_for(lambda:monitors())
  primary=monitors()[0]['name'];initial=monitors()[0];before=file.read_bytes()
  def start_watcher():
   log=(base/'watcher.log').open('a');return subprocess.Popen(['python3',str(HELPER),'watch'],env=env,stdout=log,stderr=subprocess.STDOUT)
  watcher=start_watcher()
  def call(op,value=None):
   result=subprocess.run(['python3',str(HELPER),op],input=json.dumps(value) if value is not None else None,env=env,capture_output=True,text=True,timeout=30)
   data=json.loads(result.stdout);assert result.returncode==0,(op,data,(base/'watcher.log').read_text());return data
  state=call('status');call('configure',{'timeout':10});baseline=call('save',{'name':'Laptop'})['profiles'][0]
  preview=call('preview',{'patches':{primary:{'x':initial['x']+64}}})
  wait_for(lambda:monitors()[0]['x']==initial['x']+64)
  assert file.read_bytes()==before
  copy=base/'shell';shutil.copytree(ROOT/'shell',copy,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
  (copy/'shell.qml').write_text('''import QtQuick
import Quickshell
import qs.services
import qs.modules.displays
ShellRoot {Confirmation {} Timer {interval:100;running:true;repeat:true;onTriggered:if(DisplayProfiles.pending){console.log("DISPLAY_CONFIRMATION_VISIBLE");stop();}}}''')
  with (base/'shell.log').open('w') as log:shell=subprocess.Popen(['dbus-run-session','--','quickshell','-p',str(copy)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  wait_for(lambda:'DISPLAY_CONFIRMATION_VISIBLE' in (base/'shell.log').read_text())
  fixtures=ROOT/'tests/fixtures'
  for flag,name in [('client-header','virtual-keyboard.h'),('private-code','keyboard-protocol.c')]:subprocess.run(['wayland-scanner',flag,str(fixtures/'virtual-keyboard.xml'),str(base/name)],check=True)
  (base/'keyboard.c').write_text((fixtures/'virtual-keyboard.c').read_text().replace('1u<<xkb_keymap_mod_get_index(map,XKB_MOD_NAME_LOGO)','0'))
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client','xkbcommon'],text=True))
  subprocess.run(['cc',str(base/'keyboard.c'),str(base/'keyboard-protocol.c'),'-I',str(base),*flags,'-o',str(base/'keyboard')],check=True)
  time.sleep(.4);subprocess.run([str(base/'keyboard'),'1'],env=env,check=True)
  wait_for(lambda:not call('status')['pending']);assert monitors()[0]['x']==initial['x']
  print('PASS: Escape dismisses the real confirmation and reverts display changes',flush=True)
  preview=call('preview',{'patches':{primary:{'x':initial['x']+64}}});time.sleep(.4)
  if os.environ.get('HICS_DISPLAY_PREVIEW'):subprocess.run(['grim',os.environ['HICS_DISPLAY_PREVIEW']],env=env,check=True)
  os.killpg(shell.pid,signal.SIGTERM);shell.wait(timeout=5)
  assert watcher.poll() is None
  wait_for(lambda:not call('status')['pending'],timeout=13)
  assert abs(monitors()[0]['x']-initial['x'])<1 and file.read_bytes()==before
  print('PASS: real preview dialog; independent timeout restores the layout after shell termination',flush=True)
  call('preview',{'patches':{primary:{'x':initial['x']+32}}});watcher.kill();watcher.wait();watcher=start_watcher()
  wait_for(lambda:not call('status')['pending'])
  assert monitors()[0]['x']==initial['x'] and file.read_bytes()==before
  print('PASS: watchdog crash recovery restores the pre-preview layout from its journal',flush=True)
  state=call('preview',{'patches':{primary:{'x':initial['x']+48}}})
  wait_for(lambda:monitors()[0]['x']==initial['x']+48);call('confirm',{'token':state['pending']['token']})
  assert file.read_text().startswith('-- preserved display configuration\n')
  ctl('reload');time.sleep(.4);assert monitors()[0]['x']==initial['x']+48
  print('PASS: explicit confirmation alone persists the layout, retaining user config',flush=True)
  response=ctl('output','create','headless','HICS-DOCK');assert response.strip()=='ok',response
  wait_for(lambda:len(monitors())==2)
  # Save before the settled hotplug handler selects an old one-screen layout.
  dock=call('save',{'name':'Dock'})['profiles'][-1]
  time.sleep(1)
  ctl('output','remove','HICS-DOCK');wait_for(lambda:len(monitors())==1)
  state=wait_for(lambda:(s if (s:=call('status'))['pending'] else None))
  assert state['pending']['profileId']==baseline['id'],state
  wait_for(lambda:monitors()[0]['x']==initial['x']);call('confirm',{'token':state['pending']['token']})
  ctl('output','create','headless','HICS-DOCK');wait_for(lambda:len(monitors())==2)
  state=wait_for(lambda:(s if (s:=call('status'))['pending'] else None))
  assert state['pending']['profileId']==dock['id'],state
  call('revert',{'token':state['pending']['token']})
  assert watcher.poll() is None
  log=(base/'shell.log').read_text();assert not any(x in log for x in ('TypeError:','ReferenceError:','Unable to assign','Binding loop','Failed to load configuration')),log
  assert not ctl('configerrors').strip(),ctl('configerrors')
  print('PASS: real headless-monitor hotplug selects Laptop and Dock profiles automatically',flush=True)
 finally:
  for child in (shell,watcher,compositor):
   if child and child.poll() is None:
    child.terminate()
    try:child.wait(timeout=12)
    except subprocess.TimeoutExpired:child.kill();child.wait()
