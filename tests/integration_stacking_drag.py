#!/usr/bin/env python3
"""Real-pointer maximized titlebar drag with PiP; isolated nested compositor."""
import json,os,re,shlex,shutil,subprocess,tempfile,time,signal
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-stacking-drag-') as directory:
 base=Path(directory);(base/'config/hics').mkdir(parents=True);(base/'native').mkdir()
 for name in ('libhics-render-dispatch.so','hics-bars.so','libspatialoverview.so'):
  source=Path(os.environ['HICS_TEST_NATIVE_DIR'])/name if os.environ.get('HICS_TEST_NATIVE_DIR') else next(p for p in (ROOT/'build'/name,ROOT/'build/third_party/phantomat'/name) if p.exists())
  shutil.copy2(source,base/'native'/name)
 (base/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
 lua=base/'test.lua';lua.write_text('package.path='+json.dumps(str(ROOT/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\nhl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/animations.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
 fixtures=ROOT/'tests/fixtures'
 subprocess.run(['wayland-scanner','client-header',str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/'virtual-pointer.h')],check=True)
 subprocess.run(['wayland-scanner','private-code',str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/'virtual-pointer-protocol.c')],check=True)
 flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
 subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(base/'virtual-pointer-protocol.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),HYPRSTACK_DATA_DIR=str(base));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 parent=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['wl_socket']==Path(os.environ['WAYLAND_DISPLAY']).name),None)
 compositor=None;apps=[];pointer=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  for _ in range(100):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   assert compositor.poll() is None,(base/'compositor.log').read_text()[-4000:]
   time.sleep(.1)
  assert instance
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],HYPRSTACK_POINTER_WIDTH='1280',HYPRSTACK_POINTER_HEIGHT='900')
  def ctl(*args):
   result=subprocess.run(['hyprctl','-i',instance['instance'],*args],env=env,capture_output=True,text=True,timeout=10)
   assert result.returncode==0,(result.stdout+result.stderr,(base/'compositor.log').read_text()[-4000:]);return result.stdout.strip()
  if parent:
   for _ in range(60):
    parents=json.loads(subprocess.check_output(['hyprctl','-i',parent['instance'],'clients','-j']))
    own=next((w for w in parents if w['pid']==compositor.pid),None)
    if own:break
    time.sleep(.1)
   assert own,'Nested test surface did not map in its parent'
   subprocess.run(['hyprctl','-i',parent['instance'],'repl','local w=hl.get_window("address:'+own['address']+'");hl.dispatch(hl.dsp.window.float({window=w,action="enable"}));hl.dispatch(hl.dsp.window.resize({window=w,x=1280,y=900,relative=false}))'],check=True,capture_output=True)
  for _ in range(60):
   monitor=json.loads(ctl('monitors','-j'))[0]
   if monitor['width']>=1000 and monitor['height']>=700:break
   time.sleep(.1)
  assert monitor['width']>=1000 and monitor['height']>=700,monitor
  env['HYPRSTACK_POINTER_WIDTH']=str(monitor['width']);env['HYPRSTACK_POINTER_HEIGHT']=str(monitor['height'])
  time.sleep(.4);assert not ctl('configerrors'),ctl('configerrors')
  x11=bool(os.environ.get('HICS_TEST_DRAG_X11'))
  if x11:
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','xcb'],text=True))
   subprocess.run(['cc',str(fixtures/'x11-csd-drag.c'),*flags,'-o',str(base/'x11-csd')],check=True)
   for _ in range(60):
    children=subprocess.run(['ps','--ppid',str(compositor.pid),'-o','args='],capture_output=True,text=True).stdout
    display=re.search(r'Xwayland\s+(:\d+)',children)
    if display:break
    time.sleep(.1)
   assert display,children
   env['DISPLAY']=display.group(1)
  gtk=bool(os.environ.get('HICS_TEST_DRAG_GTK'))
  if gtk:env['HICS_TEST_CSD_CONTROLS']=str(base/'gtk-controls.json')
  csd=x11 or gtk or bool(os.environ.get('HICS_TEST_DRAG_CSD'))
  if csd and not x11 and not gtk:ctl('eval','hl.bind("mouse:272",hl.dsp.window.drag(),{mouse=true})')
  main=subprocess.Popen([str(base/'x11-csd')] if x11 else ['python3',str(fixtures/'canvas-input-app.py')] if gtk else ['kitty','--class','code' if csd else 'org.hics.DragFixture','--title','Drag fixture','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.PIPE if x11 else subprocess.DEVNULL,stderr=subprocess.DEVNULL,text=True);apps.append(main)
  xid=main.stdout.readline().strip() if x11 else None
  def window(pid):return next((w for w in json.loads(ctl('-j','clients')) if w['pid']==pid),None)
  for _ in range(60):
   if window(main.pid):break
   time.sleep(.1)
  address=window(main.pid)['address']
  # A second floating video exercises activation/z-order reentrancy during dragBegin.
  pip=subprocess.Popen(['kitty','--class','helium','--title','Picture-in-Picture','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);apps.append(pip)
  for _ in range(60):
   if window(pip.pid):break
   time.sleep(.1)
  time.sleep(1)
  ctl('eval','local w=hl.get_window("address:'+address+'");hl.dispatch(hl.dsp.window.resize({window=w,x=600,y=400,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=200,y=180,relative=false}));hl.dispatch(hl.dsp.focus({window=w}))')
  pip_address=window(pip.pid)['address']
  ctl('eval','local w=hl.get_window("address:'+pip_address+'");hl.dispatch(hl.dsp.window.resize({window=w,x=320,y=180,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=900,y=650,relative=false}))')
  pointer=subprocess.Popen([str(base/'pointer')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
  assert pointer.stdout.readline().strip()=='ready'
  def send(command):
   pointer.stdin.write(command+'\n');pointer.stdin.flush()
   reply=pointer.stdout.readline().strip();assert reply=='ok',(reply,compositor.poll(),(base/'compositor.log').read_text()[-4500:]);time.sleep(.06)
  if x11:
   time.sleep(.3)
   original=window(main.pid)
   # Requests without an actual held button must not start a sticky grab.
   subprocess.run([str(base/'x11-csd'),xid,'8'],env=env,check=True)
   send('move 500 430');send('move 550 460')
   assert window(main.pid)['at']==original['at'],'Unsolicited X11 move was accepted'
   # The client body remains ordinary content, not a guessed draggable header.
   send('move 500 430');send('button 272 1');send('move 550 460');send('button 272 0')
   assert window(main.pid)['at']==original['at'],'Client content became draggable'
   print('PASS: X11 late move rejected and client content untouched',flush=True)
  for iteration in range(5):
   ctl('eval','hyprstack_layouts.action("maximize-set",'+json.dumps(address)+')');time.sleep(.4)
   w=window(main.pid);assert w['fullscreenClient']==1,w
   x=round(w['at'][0]+w['size'][0]*.30);y=w['at'][1]+20 if csd else max(1,w['at'][1]-14)
   button=272
   send(f'move {x} {y}');send(f'button {button} 1')
   for delta in (8,20,55,110):send(f'move {x+delta} {y+delta}')
   send(f'button {button} 0');time.sleep(.2)
   assert compositor.poll() is None
   restored=window(main.pid);assert restored['fullscreenClient']==0,restored
   assert restored['size'][0]<1200 and restored['size'][1]<850,restored
   assert window(pip.pid)['pinned']
   print('PASS: maximized drag restores normal geometry with PiP', 'CSD' if csd else 'server titlebar', 'round',iteration+1,flush=True)
  if x11:
   w=window(main.pid)
   x=w['at'][0]+w['size'][0]-8;y=w['at'][1]+w['size'][1]-8
   send(f'move {x} {y}');send('button 272 1')
   for delta in (12,30,60):send(f'move {x+delta} {y+delta}')
   send('button 272 0');time.sleep(.3)
   resized=window(main.pid)
   assert resized['size'][0]>w['size'][0]+20 and resized['size'][1]>w['size'][1]+20,(w,resized)
   w=resized;x=w['at'][0]+160;y=w['at'][1]+20
   send(f'move {x} {y}');send('button 272 1');send(f'move {x+20} {y+20}')
   subprocess.run([str(base/'x11-csd'),xid,'11'],env=env,check=True);time.sleep(.5)
   stopped=window(main.pid)['at'];send(f'move {x+90} {y+90}');send('button 272 0')
   assert window(main.pid)['at']==stopped,('Cancelled X11 drag kept moving',stopped,window(main.pid))
   print('PASS: native X11 CSD resize grip and cancel request',flush=True)
  if x11 or gtk:
   def native_action(operation):
    if x11:subprocess.run([str(base/'x11-csd'),'state',xid,operation],env=env,check=True)
    else:main.send_signal(signal.SIGUSR1 if operation=='minimize' else signal.SIGUSR2)
    time.sleep(.65)
   if gtk:
    buttons=json.loads((base/'gtk-controls.json').read_text())
    assert buttons.get('minimize') and buttons.get('maximize'),buttons
    print('PASS: GTK4 exposes native minimize and maximize buttons',flush=True)
   native_action('maximize')
   assert window(main.pid)['fullscreenClient']==1,window(main.pid)
   native_action('maximize')
   assert window(main.pid)['fullscreenClient']==0,window(main.pid)
   native_action('minimize')
   assert 'minimized' in window(main.pid)['workspace']['name'],window(main.pid)
   ctl('eval','hyprstack_layouts.action("restore",'+json.dumps(address)+')');time.sleep(.65)
   assert 'minimized' not in window(main.pid)['workspace']['name'],window(main.pid)
   print('PASS: native CSD maximize toggle, minimize and restore', 'X11 EWMH' if x11 else 'GTK4 xdg-shell',flush=True)
  assert not ctl('configerrors'),ctl('configerrors')
 except Exception:
  for path in (Path(os.environ['XDG_RUNTIME_DIR'])/'hypr'/instance['instance']).glob('*.log'):
   text=path.read_text(errors='replace');Path('/tmp/hics-drag-compositor-last.log').write_text(text);print(text[-6000:],flush=True)
  raise
 finally:
  if pointer and pointer.poll() is None:pointer.terminate();pointer.wait(timeout=3)
  for app in apps:
   if app.poll() is None:app.terminate();app.wait(timeout=3)
  if compositor and compositor.poll() is None:compositor.terminate();compositor.wait(timeout=5)
