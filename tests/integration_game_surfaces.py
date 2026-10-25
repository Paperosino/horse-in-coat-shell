#!/usr/bin/env python3
"""Game mode unmaps real shell layers, while explicit user drawers remain usable."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session,resize_nested_compositor
require_wayland_session();ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-game-surfaces-') as directory:
 base=Path(directory);shutil.copytree(ROOT/'shell',base/'shell',ignore=shutil.ignore_patterns('plugin','extras','__pycache__'));(base/'config/hics').mkdir(parents=True)
 (base/'config/hics/dock.json').write_text('{"enabled":true,"position":"bottom"}')
 (base/'config/hics/panels.json').write_text(json.dumps({"panels":[{"id":"11111111-1111-1111-1111-111111111111","name":"Test panel","screen":"WAYLAND-1","edge":"top","thickness":36,"autoHide":False,"hideDelay":500,"order":0}]}))
 control=base/'control.json';control.write_text('{"game":false,"launcher":false}')
 (base/'shell/shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import qs.services
import qs.modules.drawers as Drawers
ShellRoot {
 property var policy:PerformancePolicy
 Drawers.Drawers{}
 FileView {path:"'''+str(control)+'''";watchChanges:true;onFileChanged:reload();onLoaded:{const value=JSON.parse(text());GameMode.enabled=value.game;const state=ShellState.forScreen(Quickshell.screens[0]);state.launcher=value.launcher;}}
}''')
 (base/'compositor.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
 bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True);address=bus.stdout.readline().strip()
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address,GSETTINGS_BACKEND='memory',HICS_NO_ONBOARDING='1',HICS_CONFIG_NO_SYSTEMD='1',HICS_DISPLAY_NO_SYSTEMD='1');env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=None;shell=None;app=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'compositor.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance;resize_nested_compositor(compositor.pid)
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QML_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland')
  def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],env=env,text=True)
  def namespaces():
   result=[]
   for monitor in json.loads(ctl('layers','-j')).values():
    for layer in monitor['levels'].values():
     result.extend(item.get('namespace','') for item in layer)
   return result
  def wait(condition,message):
   end=time.monotonic()+12
   while time.monotonic()<end:
    if condition():return
    if shell and shell.poll() is not None:break
    time.sleep(.1)
   raise AssertionError(message+'\nLAYERS '+ctl('layers','-j')+'\nCLIENTS '+ctl('clients','-j')+'\n'+(base/'shell.log').read_text()[-5000:])
  def control_state(game,launcher=False):
   temp=control.with_suffix('.tmp');temp.write_text(json.dumps(dict(game=game,launcher=launcher)));temp.replace(control)
  with (base/'shell.log').open('w') as log:shell=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'shell')],env=env,stdout=log,stderr=subprocess.STDOUT)
  wait(lambda:'hyprstack-drawers' in namespaces() and any(n.startswith('hyprstack-panel-') for n in namespaces()),'Initial shell layers missing')
  app=subprocess.Popen(['kitty','--class','org.hics.GameSurfaceFixture','-o','confirm_os_window_close=0','sleep','90'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  wait(lambda:any(w['pid']==app.pid for w in json.loads(ctl('clients','-j'))),'No fullscreen fixture')
  w=next(w for w in json.loads(ctl('clients','-j')) if w['pid']==app.pid)
  ctl('eval','local w=hl.get_window('+json.dumps('address:'+w['address'])+');hl.dispatch(hl.dsp.window.fullscreen_state({window=w,internal=2,client=2,action="set"}))')
  control_state(True)
  wait(lambda:not any(n in ('hyprstack-drawers','hyprstack-border-exclusion') or n.startswith('hyprstack-panel-') for n in namespaces()),'Automatic shell layers remained mapped over fullscreen game')
  control_state(True,True)
  wait(lambda:'hyprstack-drawers' in namespaces(),'Explicit launcher could not map over game')
  control_state(True,False)
  wait(lambda:'hyprstack-drawers' not in namespaces(),'Closing launcher did not restore the quiet game surface')
  ctl('eval','local w=hl.get_window('+json.dumps('address:'+w['address'])+');hl.dispatch(hl.dsp.window.fullscreen_state({window=w,internal=0,client=0,action="set"}))')
  wait(lambda:'hyprstack-drawers' in namespaces() and any(n.startswith('hyprstack-panel-') for n in namespaces()),'Shell layers did not restore after game fullscreen exit')
  output=(base/'shell.log').read_text();assert not any(e in output for e in ('TypeError:','ReferenceError:','Binding loop')),output[-6000:]
  print('PASS: fullscreen game unmaps drawers/reservations, explicit launcher works, layers restore')
 finally:
  for process in (shell,app,compositor,bus):
   if process and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
  bus.stdout.close()
