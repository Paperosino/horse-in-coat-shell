#!/usr/bin/env python3
"""Nested-compositor regression for shared views and Qt Quick/X11 wheel input."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests/fixtures'
with tempfile.TemporaryDirectory(prefix='hics-canvas-views-') as temporary:
 base=Path(temporary); processes=[]; compositor=None; pointer=None
 (base/'config/hics').mkdir(parents=True);(base/'data/native').mkdir(parents=True)
 for plugin,source in [('libhics-render-dispatch.so',ROOT/'build/libhics-render-dispatch.so'),('hics-bars.so',ROOT/'build/hics-bars.so'),('libspatialoverview.so',ROOT/'build/third_party/phantomat/libspatialoverview.so')]:shutil.copy2(source,base/'data/native'/plugin)
 config=ROOT/'shell/assets/hyprland/config'
 (base/'test.lua').write_text('package.path='+json.dumps(str(config/'?.lua')+';')+'..package.path\ndofile(ANIMATIONS)\npackage.preload["scheme.current"]=function()return require("scheme.default")end\nhl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\ndofile('+json.dumps(str(config/'hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
 text=(base/'test.lua').read_text().replace('ANIMATIONS',json.dumps(str(config/'hyprland/animations.lua')));(base/'test.lua').write_text(text)
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),HYPRSTACK_DATA_DIR=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'user-data'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 try:
  log=(base/'compositor.log').open('w');compositor=subprocess.Popen(['Hyprland','--config',str(base/'test.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance,'Nested compositor did not start'
  sig=instance['instance'];time.sleep(1)
  def ctl(*args):return subprocess.check_output(['hyprctl','-i',sig,*args],text=True,timeout=10).strip()
  assert not ctl('configerrors'),ctl('configerrors')
  ctl('plugin','load',str(base/'data/native/libspatialoverview.so'));time.sleep(.5)
  appenv=dict(env,WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=sig,QT_QPA_PLATFORM='wayland',QT_QUICK_BACKEND='software',HYPRSTACK_POINTER_WIDTH='1280',HYPRSTACK_POINTER_HEIGHT='900')
  def clients():return json.loads(ctl('-j','clients'))
  def launch(platform):
   output=base/(platform+'.log');stream=output.open('w')
   launchenv=dict(appenv,QT_QPA_PLATFORM=platform)
   if platform=='xcb':launchenv['DISPLAY']=ctl('repl','return os.getenv("DISPLAY")').strip('"')
   process=subprocess.Popen(['python3',str(FIXTURES/'canvas-scroll-app.py')],env=launchenv,stdout=stream,stderr=subprocess.STDOUT);processes.append(process)
   for _ in range(50):
    found=next((c for c in clients() if c['pid']==process.pid),None)
    if found:return found,output
    if process.poll() is not None:raise AssertionError((process.returncode,output.read_text(),launchenv.get('DISPLAY')))
    time.sleep(.1)
   raise AssertionError((process.returncode,output.read_text(),launchenv.get('DISPLAY')))
  first,waylandlog=launch('wayland');second,x11log=launch('xcb')
  assert second['xwayland'],'X11 regression client must use XWayland'
  ctl('repl','return hyprstack_layouts.set_mode("canvas")');time.sleep(1)
  def place(window,x,y,w=600,h=500):
   addr=window['address'];ref='hl.get_window("address:'+addr+'")'
   ctl('repl','hl.dispatch(hl.dsp.window.resize({window='+ref+',x='+str(w)+',y='+str(h)+',relative=false}))')
   ctl('repl','hl.dispatch(hl.dsp.window.move({window='+ref+',x='+str(x)+',y='+str(y)+',relative=false}))')
  place(first,2400,200);place(second,3020,200)
  def view():return json.loads(ctl('spatialoverview'))['screens'][0]
  def activate(window):ctl('repl','return hyprstack_layouts.action("dock-activate",'+json.dumps(window['address'])+')');time.sleep(1.4)
  ctl('repl','return hyprstack_layouts.canvas_action("land")');time.sleep(.4)
  ctl('repl','return hyprstack_layouts.canvas_action("viewport 2380 100")');time.sleep(.8)
  shared=view()['view'];assert view()['zoom']==1,view()
  ctl('repl','return hyprstack_layouts.canvas_action("viewport 8000 6000")');time.sleep(.5)
  activate(first);assert all(abs(a-b)<2 for a,b in zip(shared,view()['view'])),('Shared camera was not restored',shared,view())
  ctl('repl','return hyprstack_layouts.canvas_action("viewport 8000 6000")');time.sleep(.4)
  activate(second);assert all(abs(a-b)<2 for a,b in zip(shared,view()['view'])),('Other group member lost the split',shared,view())
  print('PASS: either window restores the shared camera through dock/notification activation',flush=True)
  # Input is injected into the nested compositor, never the user's applications.
  subprocess.run(['wayland-scanner','client-header',str(FIXTURES/'wlr-virtual-pointer-unstable-v1.xml'),str(base/'virtual-pointer.h')],check=True)
  subprocess.run(['wayland-scanner','private-code',str(FIXTURES/'wlr-virtual-pointer-unstable-v1.xml'),str(base/'virtual-pointer-protocol.c')],check=True)
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
  subprocess.run(['cc',str(FIXTURES/'virtual-pointer.c'),str(base/'virtual-pointer-protocol.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
  pointer=subprocess.Popen([str(base/'pointer')],env=appenv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
  assert pointer.stdout.readline().strip()=='ready'
  def send(op,x,y):pointer.stdin.write(f'{op} {x} {y}\n');pointer.stdin.flush();assert pointer.stdout.readline().strip()=='ok';time.sleep(.1)
  for window,output in [(first,waylandlog),(second,x11log)]:
   current=next(c for c in clients() if c['address']==window['address']);camera=view()['view']
   send('move',round(current['at'][0]+200-camera[0]),round(current['at'][1]+200-camera[1]))
   before=output.read_text().count('WHEEL')
   send('wheel',0,1);send('wheel',0,1);time.sleep(.2)
   after=output.read_text();assert after.count('WHEEL')>=before+2,('Wheel input missing',window['xwayland'],after)
   assert 'SCROLLED' in after,('Qt Quick did not scroll',after)
  print('PASS: Qt Quick WheelHandler and scrolling work in Wayland and XWayland',flush=True)
  # Reordering invalidates the old view and records the new arrangement.
  place(first,3520,200);place(second,2900,200);ctl('repl','return hyprstack_layouts.canvas_action("viewport 2880 100")');time.sleep(.8)
  updated=view()['view'];ctl('repl','return hyprstack_layouts.canvas_action("viewport 8000 6000")');time.sleep(.3);activate(second)
  assert all(abs(a-b)<2 for a,b in zip(updated,view()['view'])),('Moved group retained stale camera',view())
  ctl('repl','return hyprstack_layouts.action("close",'+json.dumps(first['address'])+')');processes[0].wait(timeout=5);time.sleep(.5)
  assert not any(c['address']==first['address'] for c in clients()),'Dock close did not close a canvas window'
  ctl('repl','return hyprstack_layouts.canvas_action("viewport 8000 6000")');time.sleep(.3);activate(second)
  assert all(abs(a-b)<2 for a,b in zip(updated,view()['view'])),('Closing a member corrupted the remaining memory',view())
  print('PASS: moved windows rebuild view memory and closed members are removed',flush=True)
 except Exception:
  for output in base.glob('*.log'):
   print(output.name,output.read_text(errors='replace')[-4000:])
  raise
 finally:
  if pointer:
   pointer.stdin.close();pointer.wait(timeout=3)
  for process in reversed(processes):
   if process.poll() is None:process.terminate();process.wait(timeout=5)
  if compositor and compositor.poll() is None:compositor.terminate();compositor.wait(timeout=10)
