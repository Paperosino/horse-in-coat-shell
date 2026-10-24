#!/usr/bin/env python3
"""Real-pointer maximized titlebar drag with PiP; isolated nested compositor."""
import json,os,shlex,shutil,subprocess,tempfile,time
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
  csd=bool(os.environ.get('HICS_TEST_DRAG_CSD'))
  if csd:ctl('eval','hl.bind("mouse:272",hl.dsp.window.drag(),{mouse=true})')
  main=subprocess.Popen(['kitty','--class','code' if csd else 'org.hics.DragFixture','--title','Drag fixture','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);apps.append(main)
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
