#!/usr/bin/env python3
"""Real pointer press/release cancellation with bars, canvas and shared renderer."""
import json, os, shlex, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from integration_support import require_wayland_session, resize_nested_compositor
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-titlebar-release-') as temp:
 base=Path(temp);native=base/'native';native.mkdir();config=base/'config';(config/'hics').mkdir(parents=True)
 for name in ('libhics-render-dispatch.so','hics-bars.so','libspatialoverview.so'):
  source=next(p for p in (ROOT/'build'/name,ROOT/'build/third_party/phantomat'/name) if p.is_file())
  shutil.copy2(source,native/name)
 (config/'hics/layouts.json').write_text('{"mode":"stacking"}')
 lua=base/'test.lua';lua.write_text('package.path='+json.dumps(str(ROOT/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function() return require("scheme.default") end\nhl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/animations.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
 fixtures=ROOT/'tests/fixtures'
 for flag,output in [('client-header','virtual-pointer.h'),('private-code','virtual-pointer-protocol.c')]:
  subprocess.run(['wayland-scanner',flag,str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/output)],check=True)
 flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
 subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(base/'virtual-pointer-protocol.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(config),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),HICS_DATA_DIR=str(base),HYPRSTACK_TITLEBAR_PLUGIN=str(native/'hics-bars.so'),HYPRSTACK_DATA_DIR=str(base));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=app=pointer=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(100):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   assert compositor.poll() is None,(base/'compositor.log').read_text()[-4000:]
   time.sleep(.1)
  assert instance
  resize_nested_compositor(compositor.pid)
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
  def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],text=True,env=env,timeout=8).strip()
  ctl('plugin','load',str(native/'libspatialoverview.so'));time.sleep(.5)
  assert not ctl('configerrors'),ctl('configerrors')
  def window():return next((w for w in json.loads(ctl('-j','clients')) if app and w['pid']==app.pid),None)
  def send(op,x,y):
   pointer.stdin.write(f'{op} {round(x)} {round(y)}\n');pointer.stdin.flush();reply=pointer.stdout.readline().strip();assert reply=='ok', (reply,(base/'compositor.log').read_text()[-3500:]);time.sleep(.07)
  def markers():return sorted(p.name for p in base.glob('action-*'))
  def clear():
   for p in base.glob('action-*'):p.unlink()
  def buttons(side):
   ctl('eval','hl.config({plugin={hyprbars={bar_buttons_alignment='+json.dumps(side)+'}}});hl.plugin.hyprbars.clear_buttons()')
   for i in range(3):ctl('eval','hl.plugin.hyprbars.add_button({bg_color="rgb(334455)",fg_color="rgb(eeeeee)",size=26,icon='+json.dumps(str(i))+',action='+json.dumps('touch '+str(base/f'action-{i}'))+'})')
  for scale in (1,1.5):
   ctl('eval',f'hl.monitor({{output="WAYLAND-1",mode="1280x900@60",position="0x0",scale={scale}}})');time.sleep(.3)
   monitor=json.loads(ctl('-j','monitors'))[0]
   penv=dict(env,HYPRSTACK_POINTER_WIDTH=str(round(monitor['width']/monitor['scale'])),HYPRSTACK_POINTER_HEIGHT=str(round(monitor['height']/monitor['scale'])))
   pointer=subprocess.Popen([str(base/'pointer')],env=penv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert pointer.stdout.readline().strip()=='ready'
   app=subprocess.Popen(['kitty','--class','org.hics.ReleaseFixture','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   for _ in range(60):
    if window():break
    time.sleep(.1)
   assert window()
   address=window()['address']
   ctl('eval','local w=hl.get_window("address:'+address+'");hl.dispatch(hl.dsp.window.resize({window=w,x=500,y=250,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=120,y=180,relative=false}))');time.sleep(.6)
   for side in ('left','right'):
    buttons(side);time.sleep(.2);w=window();x,y=w['at'];width=w['size'][0]
    centers=[(x+21+i*30 if side=='left' else x+width-21-i*30,y-16) for i in range(3)]
    for index,(bx,by) in enumerate(centers):
     clear();send('move',bx,by);send('button',272,1);assert not markers(),'Action ran on press'
     send('button',272,0);assert markers()==[f'action-{index}'],markers()
    clear();send('move',*centers[0]);send('button',272,1);send('move',x+width/2,y+80);send('button',272,0)
    assert not markers() and window()['at']==w['at'],'Dragging away from a control activated it or moved the window'
    send('move',*centers[0]);send('button',272,1);send('move',20,40);send('button',272,0);assert not markers(),'Release outside the window activated a control'
    send('move',*centers[0]);send('button',272,1);send('move',*centers[1]);send('button',272,0);assert not markers(),'Release over a different button activated a control'
    send('move',*centers[0]);send('button',272,1);send('move',x+width/2,y+80);send('move',*centers[0]);send('button',272,0);assert markers()==['action-0']
    clear();send('move',*centers[0]);send('button',272,1);send('button',273,1);send('button',273,0);assert not markers();send('button',272,0);assert markers()==['action-0'],'Unrelated release lost the primary capture'
    clear();send('button',273,1);send('button',273,0);assert not markers(),'Secondary button invoked a titlebar action'
    send('move',*centers[0]);send('button',272,1)
    ctl('eval','hl.plugin.hyprbars.clear_buttons();hl.plugin.hyprbars.add_button({bg_color="rgb(334455)",fg_color="rgb(eeeeee)",size=26,icon="changed",action='+json.dumps('touch '+str(base/'action-changed'))+'})')
    send('button',272,0);assert not markers(),'Configuration change activated a replacement command'
    print('PASS: press/release, drag-away, neighbour, return and multiple mouse buttons;',side,'scale',scale,flush=True)
   # The real close action must also leave the client alive until release.
   ctl('eval','hl.plugin.hyprbars.clear_buttons();hl.plugin.hyprbars.add_button({bg_color="rgb(334455)",fg_color="rgb(eeeeee)",size=26,icon="hyprstack:close",action="false"})')
   w=window();send('move',w['at'][0]+w['size'][0]-21,w['at'][1]-16);send('button',272,1);assert window(),'Client closed on press'
   send('button',272,0)
   for _ in range(30):
    if not window():break
    time.sleep(.1)
   assert not window(),'Client did not close on release';app.wait(timeout=5);app=None
   pointer.stdin.close();pointer.wait(timeout=5);pointer=None
 finally:
  for process in (pointer,app,compositor):
   if process and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
