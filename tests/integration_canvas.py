#!/usr/bin/env python3
"""Nested Wayland canvas regression. Requires Hyprland, kitty and built native modules.
Use --pointer to include real Ctrl-wheel input via /dev/uinput. Isolates all
configuration/state from the user's session and always closes its own clients.
"""
import subprocess,os,json,time,traceback,shutil,signal
from pathlib import Path
import tempfile,sys
from integration_support import require_wayland_session
require_wayland_session()
repo=Path(__file__).resolve().parents[1]
workspace=tempfile.TemporaryDirectory(prefix='hyprstack-canvas-test-')
base=Path(workspace.name)
(base/'config/hics').mkdir(parents=True)
(base/'data/native').mkdir(parents=True)
for plugin in ['libhics-render-dispatch.so','hics-bars.so','libspatialoverview.so']:
 candidates=[repo/'build'/plugin,repo/'build/third_party/phantomat'/plugin,Path('/usr/share/hics/native')/plugin]
 source=next((p for p in candidates if p.is_file()),None)
 if source is None:raise RuntimeError('Build native modules before running this integration test')
 shutil.copy2(source,base/'data/native'/plugin)
config=repo/'shell/assets/hyprland/config'
(base/'test.lua').write_text('package.path = '+json.dumps(str(config/'?.lua')+';')+' .. package.path\n'+
    'dofile('+json.dumps(str(config/'hyprland/animations.lua'))+')\n'+
    'package.preload["scheme.current"] = function() return require("scheme.default") end\n'+
    'hl.monitor({output="WAYLAND-1",mode="1280x720@60",position="0x0",scale=1})\n'+
    'dofile('+json.dumps(str(config/'hyprland/gestures.lua'))+')\n'+
    'dofile('+json.dumps(str(repo/'shell/assets/hyprland/layouts.lua'))+')\n')
env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),HYPRSTACK_DATA_DIR=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'user-data'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
(base/'config/hics/layouts.json').write_text(json.dumps({'mode':'scrolling'}))
p=None;apps=[];instance=None
try:
 log=(base/'compositor.log').open('w');p=subprocess.Popen(['Hyprland','--config',str(base/'test.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
 for attempt in range(80):
  if p.poll() is not None:raise RuntimeError('Nested compositor exited during startup')
  instances=json.loads(subprocess.check_output(['hyprctl','instances','-j']));instance=next((i for i in instances if i['pid']==p.pid),None)
  if instance:break
  time.sleep(.1)
 if not instance:raise RuntimeError('Nested compositor IPC did not start')
 sig=instance['instance'] # readiness is checked by the production loader
 def ctl(*args):
  r=subprocess.run(['hyprctl','-i',sig,*args],capture_output=True,text=True,timeout=15)
  if r.returncode or r.stdout.strip().startswith('error:'):raise RuntimeError(r.stdout+r.stderr)
  return r.stdout.strip()
 errors=ctl('configerrors');print('Startup errors:',errors or 'none',flush=True);assert not errors,errors
 canvas_plugin=str(base/'data/native/libspatialoverview.so')
 if 'spatialoverview' not in ctl('plugin','list'):
  subprocess.run(['python3',str(repo/'shell/assets/load_canvas_plugin.py'),canvas_plugin],env=dict(env,HYPRLAND_INSTANCE_SIGNATURE=sig),check=True,timeout=35);time.sleep(1)
 print('Plugins:',ctl('-j','plugin','list'),flush=True)
 print('Bridge:',ctl('repl','return type(hl.plugin.spatialoverview.hyprstack_close)'),flush=True)
 app_env=dict(env,WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=sig)
 for n in range(4):apps.append(subprocess.Popen(['kitty','-o','confirm_os_window_close=0','--class','hyprstack-nested-test','--title',f'Nested test {n}','sleep','90'],env=app_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
 time.sleep(2)
 ctl('repl','return hyprstack_layouts.set_mode("scrolling")');time.sleep(.5)
 ctl('repl','hl.dispatch(hl.dsp.window.move({direction="left"}))')
 print('PASS: directional window move binding accepts its arguments',flush=True)
 wins=[c for c in json.loads(ctl('clients','-j')) if c['class']=='hyprstack-nested-test'];floating=wins[-1]['address']
 ctl('repl','hl.dispatch(hl.dsp.window.float({window=hl.get_window("address:'+floating+'"),action="enable"}))')
 ctl('repl','hl.dispatch(hl.dsp.window.resize({window=hl.get_window("address:'+floating+'"),x=400,y=280,relative=false}))')
 ctl('repl','hl.dispatch(hl.dsp.window.move({window=hl.get_window("address:'+floating+'"),workspace="2",follow=false}))')
 time.sleep(.4)
 before={c['address']:c for c in json.loads(ctl('clients','-j')) if c['class']=='hyprstack-nested-test'}
 print('Before canvas:',[(c['floating'],c['at'],c['size']) for c in before.values()],flush=True)
 ctl('repl','return hyprstack_layouts.set_mode("canvas")');time.sleep(1)
 assert ctl('repl','return hl.get_config("plugin.hyprbars.enabled")')=='false'
 assert ctl('repl','return hl.get_config("general.layout")')=='scrolling'
 print('PASS: no titlebars, no stacking layout migration',flush=True)
 state=lambda:json.loads(ctl('spatialoverview'))['screens'][0]
 print('Initial canvas:',state(),flush=True)
 ctl('repl','return hyprstack_layouts.canvas_action("zoom out")');time.sleep(.5);z=state()['zoom'];assert z<1,z
 ctl('repl','return hyprstack_layouts.canvas_action("zoom in")');time.sleep(.5);assert state()['zoom']>z
 ctl('repl','return hyprstack_layouts.canvas_action("zoom reset")');time.sleep(.5);assert abs(state()['zoom']-1)<.01,state()
 print('PASS: zoom in/out/reset changes actual camera zoom',flush=True)
 ctl('repl','return hyprstack_layouts.canvas_action("land")');time.sleep(.5)
 assert not state()['navigating'],state()
 if "--pointer" in sys.argv:
  # Real wheel input through the nested compositor's Wayland surface.
  import struct,fcntl
  host_env=os.environ.copy()
  host=lambda *a:subprocess.check_output(['hyprctl',*a],env=host_env,text=True).strip()
  original=json.loads(host('activewindow','-j'));cursor=json.loads(host('cursorpos','-j'));fd=None
  try:
   outer=next(c for c in json.loads(host('clients','-j')) if c['pid']==p.pid)
   host('repl','hl.dispatch(hl.dsp.focus({window=hl.get_window("address:'+outer['address']+'" )}))')
   host('repl','hl.dispatch(hl.dsp.cursor.move({x='+str(outer['at'][0]+min(outer['size'][0]-40,500))+',y='+str(outer['at'][1]+min(outer['size'][1]-40,400))+'}))')
   fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
   for ev in [0,1,2]:fcntl.ioctl(fd,0x40045564,ev)
   for key in list(range(1,256))+[272,274]:fcntl.ioctl(fd,0x40045565,key)
   for rel in [0,1,8]:fcntl.ioctl(fd,0x40045566,rel)
   os.write(fd,struct.pack('80sHHHHI',b'Hyprstack canvas input regression',3,1,1,1,0)+bytes(1024));fcntl.ioctl(fd,0x5501);time.sleep(.6)
   def event(t,c,v):os.write(fd,struct.pack('llHHi',0,0,t,c,v));os.write(fd,struct.pack('llHHi',0,0,0,0,0))
   event(2,0,1);time.sleep(.1);event(1,272,1);time.sleep(.06);event(1,272,0);time.sleep(.2);print('Nested pointer:',ctl('cursorpos','-j'),flush=True);event(1,29,1);time.sleep(.1);event(2,8,-1);time.sleep(.2);event(1,29,0);time.sleep(.5)
   print('After Ctrl+wheel from resting canvas:',state(),flush=True);assert state()['zoom']<1,state();assert state()['navigating'],state()
   print('PASS: real Ctrl+wheel enters zoom from resting canvas',flush=True)
   start=state()['view']
   event(1,125,1);event(1,274,1);time.sleep(.1)
   for _ in range(8):event(2,0,8);event(2,1,4);time.sleep(.03)
   event(1,274,0);event(1,125,0);time.sleep(.3)
   assert state()['view'][:2]!=start[:2],(start,state())
   print('PASS: explicit Super+middle-drag pans the camera',flush=True)
  finally:
   if fd is not None:
    try:event(1,29,0);fcntl.ioctl(fd,0x5502)
    finally:os.close(fd)
   if original.get('address'):host('repl','hl.dispatch(hl.dsp.focus({window=hl.get_window("address:'+original['address']+'" )}))')
   host('repl','hl.dispatch(hl.dsp.cursor.move({x='+str(cursor['x'])+',y='+str(cursor['y'])+'}))')
 ctl('reload');time.sleep(1)
 assert ctl('repl','return hyprstack_layouts.mode()')=='canvas'
 assert ctl('repl','return hl.get_config("plugin.hyprbars.enabled")')=='false'
 assert not ctl('configerrors'),ctl('configerrors')
 ctl('repl','return hyprstack_layouts.set_mode("scrolling")');time.sleep(.8)
 after={c['address']:c for c in json.loads(ctl('clients','-j')) if c['class']=='hyprstack-nested-test'}
 assert set(before)==set(after)
 for address,c in before.items():
  assert c['floating']==after[address]['floating'],(c,after[address])
  assert c['workspace']['id']==after[address]['workspace']['id']
  if c['floating']:
   assert all(abs(a-b)<=2 for a,b in zip(c['size'],after[address]['size'])),(c,after[address])
 print('PASS: reload keeps canvas independent; exit restores tiled/floating windows and workspaces',flush=True)
 # The shared texture dispatcher keeps one permanent patch across switches,
 # including a failed Lua operation between canvas and overview transitions.
 def renderer_state():return json.loads(ctl('repl','return hl.plugin.hyprbars.overview_scene("status")'))['textureDispatcher']
 baseline=renderer_state();assert baseline['participants']==2,baseline
 for index in range(20):
  ctl('repl','return hyprstack_layouts.set_mode("canvas")')
  ctl('repl','pcall(function() hl.plugin.hyprbars.overview_hooks(true); error("injected transition interruption") end)')
  ctl('repl','return hyprstack_layouts.set_mode("scrolling")')
  current=renderer_state();assert current['patches']==baseline['patches'],(baseline,current)
  assert current['participants']==2 and current['activePriority']==10,current
 assert not ctl('configerrors'),ctl('configerrors')
 print('PASS: 20 canvas transitions and interrupted Lua operations leave the single texture patch unchanged',flush=True)
 ctl('repl','return hyprstack_layouts.set_mode("canvas")');time.sleep(.6)
 ordered=list(after)
 def focus(address):
  ctl('repl','hl.dispatch(hl.dsp.focus({window=hl.get_window("address:'+address+'" )}))');time.sleep(.15)
 def close(address):
  ctl('repl','hl.dispatch(hl.dsp.window.close({window=hl.get_window("address:'+address+'" )}))');time.sleep(.6)
 def active():return json.loads(ctl('activewindow','-j')).get('address')
 # Deliberately use an order different from creation and spatial order.
 focus(ordered[0]);focus(ordered[3]);focus(ordered[2]);focus(ordered[1])
 close(ordered[1]);assert active()==ordered[2],(active(),ordered)
 print('PASS: closing the focused canvas window restores the most recently active window',flush=True)
 close(ordered[2]);assert active()==ordered[3],(active(),ordered)
 print('PASS: repeated closes follow activation order without recording compositor fallback focus',flush=True)
 # A background close must never move the keyboard focus or camera.
 close(ordered[0]);assert active()==ordered[3],(active(),ordered)
 close(ordered[3]);assert not active(),active()
 print('PASS: closing a background or the last canvas window preserves valid focus',flush=True)


finally:
 for app in apps:
  if app.poll() is None:app.terminate()
 if p and p.poll() is None:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 if p and p.returncode not in (0,-signal.SIGTERM):
  raise RuntimeError(f'Nested compositor exited with {p.returncode}, including during cleanup')
