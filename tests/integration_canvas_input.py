#!/usr/bin/env python3
"""Nested Wayland application input and rendering regression. Requires Hyprland, kitty and built native modules.
Use --pointer to include real Ctrl-wheel input via /dev/uinput. Isolates all
configuration/state from the user's session and always closes its own clients.
"""
import subprocess,os,json,time,traceback,shutil,signal,re
from pathlib import Path
import tempfile,sys
from integration_support import require_wayland_session
require_wayland_session()
repo=Path(__file__).resolve().parents[1]
withoutBars=bool(os.environ.get('HYPRSTACK_TEST_WITHOUT_BARS'))
toolkit=os.environ.get('HYPRSTACK_INPUT_TOOLKIT','gtk')
if toolkit not in ('gtk','qt'):raise ValueError('HYPRSTACK_INPUT_TOOLKIT must be gtk or qt')
workspace=tempfile.TemporaryDirectory(prefix='hyprstack-canvas-test-')
base=Path(workspace.name)
(base/'config/hyprstack').mkdir(parents=True)
(base/'data/native').mkdir(parents=True)
for plugin in ['hyprstack-bars.so','libspatialoverview.so']:
 candidates=[repo/'build'/plugin,repo/'build/third_party/phantomat'/plugin,Path('/usr/share/hyprstack/native')/plugin]
 source=next((p for p in candidates if p.is_file()),None)
 if source is None:raise RuntimeError('Build native modules before running this integration test')
 # Snapshot plugins: rebuilding must never change a running test's mappings.
 shutil.copy2(source,base/'data/native'/plugin)
config=repo/'shell/assets/hyprland/config'
(base/'test.lua').write_text('package.path = '+json.dumps(str(config/'?.lua')+';')+' .. package.path\n'+
    'dofile('+json.dumps(str(config/'hyprland/animations.lua'))+')\n'+
    'package.preload["scheme.current"] = function() return require("scheme.default") end\n'+
    'hl.monitor({output="WAYLAND-1",mode="1280x720@60",position="0x0",scale=1})\n'+
    'dofile('+json.dumps(str(config/'hyprland/gestures.lua'))+')\n'+
    'dofile('+json.dumps(str(repo/'shell/assets/hyprland/layouts.lua'))+')\n')
env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),HYPRSTACK_DATA_DIR=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'user-data'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
if withoutBars:env['HYPRSTACK_TITLEBAR_PLUGIN']=str(base/'missing-bars.so')
(base/'config/hyprstack/layouts.json').write_text(json.dumps({'mode':'scrolling'}))
# This test injects into the nested compositor through its virtual pointer.
# It never moves the host cursor or touches files in the user's applications.
p=None;app=None;pointer=None;log=None;wallpaper=None;wallpaperLog=None;engine=None;engineLog=None
try:
 fixtures=repo/'tests/fixtures'
 subprocess.run(['wayland-scanner','client-header',str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/'virtual-pointer.h')],check=True)
 subprocess.run(['wayland-scanner','private-code',str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/'virtual-pointer-protocol.c')],check=True)
 import shlex
 flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
 subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(base/'virtual-pointer-protocol.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
 log=(base/'compositor.log').open('w');p=subprocess.Popen(['Hyprland','--config',str(base/'test.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
 instance=None
 for _ in range(80):
  if p.poll() is not None:raise RuntimeError('Nested compositor exited')
  instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==p.pid),None)
  if instance:break
  time.sleep(.1)
 assert instance
 sig=instance['instance'];time.sleep(2)
 def ctl(*args):
  r=subprocess.run(['hyprctl','-i',sig,*args],capture_output=True,text=True,timeout=10)
  if r.returncode or r.stdout.strip().startswith('error:'):raise RuntimeError(r.stdout+r.stderr)
  return r.stdout.strip()
 assert not ctl('configerrors'),ctl('configerrors')
 if withoutBars:assert 'hyprbars' not in ctl('plugin','list')
 canvas_plugin=str(base/'data/native/libspatialoverview.so')
 if 'spatialoverview' not in ctl('plugin','list'):
  ctl('plugin','load',canvas_plugin);time.sleep(1)
 monitor=json.loads(ctl('monitors','-j'))[0];width=round(monitor['width']/monitor['scale']);height=round(monitor['height']/monitor['scale'])
 appenv=dict(env,WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=sig,GSK_RENDERER=os.environ.get('HYPRSTACK_GSK_RENDERER','cairo'),HYPRSTACK_POINTER_WIDTH=str(width),HYPRSTACK_POINTER_HEIGHT=str(height))
 if os.environ.get('HYPRSTACK_SOAK'):
  appenv['HYPRSTACK_ANIMATE']='1'
  wall=base/'wall.qml';wall.write_text('''import QtQuick
import Quickshell
import Quickshell.Wayland
ShellRoot { PanelWindow { anchors {top:true;bottom:true;left:true;right:true} WlrLayershell.layer: WlrLayer.Background; WlrLayershell.namespace: "canvas-test-wallpaper"; exclusionMode: ExclusionMode.Ignore; color: "#153580"; Rectangle { anchors.fill:parent; color:"#174990"; SequentialAnimation on opacity { loops:Animation.Infinite; NumberAnimation {to:0.5;duration:600} NumberAnimation {to:1;duration:600} } } } }''')
  wallpaperLog=(base/'wall.log').open('w')
  wallpaper=subprocess.Popen(['qs','-p',str(wall)],env=appenv,stdout=wallpaperLog,stderr=subprocess.STDOUT)
  time.sleep(1)
  if os.environ.get('HYPRSTACK_ENGINE_SOURCE'):
   engineLog=(base/'engine.log').open('w')
   engine=subprocess.Popen(['linux-wallpaperengine','--screen-root','WAYLAND-1','--bg',os.environ['HYPRSTACK_ENGINE_SOURCE'],'--layer','background','--fps','30','--silent','--no-fullscreen-pause'],env=appenv,stdout=engineLog,stderr=subprocess.STDOUT)
   time.sleep(2)
   assert engine.poll() is None,'Wallpaper Engine exited during startup'
 appLog=base/'app.log';out=appLog.open('w')
 fixture='canvas-qt-input-app.py' if toolkit=='qt' else 'canvas-input-app.py'
 app=subprocess.Popen(['python3',str(fixtures/fixture)],env=appenv,stdout=out,stderr=subprocess.STDOUT)
 time.sleep(2)
 window=next(c for c in json.loads(ctl('clients','-j')) if c['pid']==app.pid);address=window['address']
 ctl('repl','return hyprstack_layouts.set_mode("canvas")');time.sleep(1)
 ctl('repl','hl.dispatch(hl.dsp.window.move({window=hl.get_window("address:'+address+'"),x=2500,y=300,relative=false}))')
 ctl('repl','hl.dispatch(hl.dsp.focus({window=hl.get_window("address:'+address+'" )}))')
 ctl('repl','return hyprstack_layouts.canvas_action("frame")');time.sleep(1)
 ctl('repl','return hyprstack_layouts.canvas_action("zoom out")');time.sleep(.6)
 ctl('repl','return hyprstack_layouts.canvas_action("viewport 2180 140")');time.sleep(.5)
 state=lambda:json.loads(ctl('spatialoverview'))['screens'][0]
 window=lambda:next(c for c in json.loads(ctl('clients','-j')) if c['address']==address)
 w=window();cam=state();print('Window and camera:',w['at'],w['size'],cam,flush=True)
 def screen(x,y):return [round((w['at'][0]+x-cam['view'][0])*cam['zoom']),round((w['at'][1]+y-cam['view'][1])*cam['zoom'])]
 source=screen(w['size'][0]*.25,w['size'][1]*.5);target=screen(w['size'][0]*.75,w['size'][1]*.5)
 assert all(1<=point[0]<width-1 and 1<=point[1]<height-1 for point in (source,target)),(source,target)
 # Check the actual pixels while zoomed, before returning to desktop input.
 from PIL import Image
 zoomed=base/'zoomed.png';subprocess.run(['grim',str(zoomed)],env=appenv,check=True,capture_output=True)
 image=Image.open(zoomed).convert('RGB')
 colours=image.getcolors(image.width*image.height)
 green=sum(count for count,(r,g,b) in colours if g>150 and r<80 and b<80)
 red=sum(count for count,(r,g,b) in colours if r>150 and g<80 and b<80)
 expected=w['size'][0]*w['size'][1]*cam['zoom']**2
 assert min(green,red)>expected*.30,(green,red,expected)
 print('PASS: zoomed preview preserves the complete offscreen client surface',flush=True)
 pointer=subprocess.Popen([str(base/'pointer')],env=appenv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
 assert pointer.stdout.readline().strip()=='ready'
 def send(op,x,y):
  pointer.stdin.write(f'{op} {x} {y}\n');pointer.stdin.flush();assert pointer.stdout.readline().strip()=='ok';time.sleep(.05)
 send('move',*source);send('button',274,1);send('button',274,0);time.sleep(.2)
 assert 'MIDDLE_PRESSED' in appLog.read_text() and 'MIDDLE_RELEASED' in appLog.read_text(),appLog.read_text()
 assert state()['view']==cam['view'],'Middle click changed camera'
 print('PASS: middle press/release reaches application at non-unit canvas zoom',flush=True)
 # Normal desktop input owns file drags; overview/navigation owns window drags.
 ctl('repl','return hyprstack_layouts.canvas_action("land")');time.sleep(.7)
 ctl('repl','return hyprstack_layouts.canvas_action("viewport 2180 140")');time.sleep(.5)
 cam=state();w=window();source=screen(w['size'][0]*.25,w['size'][1]*.5);target=screen(w['size'][0]*.75,w['size'][1]*.5)
 send('move',*source);send('button',272,1)
 for n in range(1,19):send('move',round(source[0]+(target[0]-source[0])*n/18),source[1])
 time.sleep(.3);send('button',272,0);time.sleep(.5)
 print(appLog.read_text(),flush=True)
 assert 'DROP hyprstack-test' in appLog.read_text(),appLog.read_text()
 motions=re.findall(r'^MOTION (-?\d+) (-?\d+) (\d+) (\d+)$',appLog.read_text(),re.MULTILINE)
 assert motions,'No client pointer coordinates recorded'
 assert all(-32<=int(x)<=int(w)+32 and -32<=int(y)<=int(h)+32 for x,y,w,h in motions),('Non-local pointer coordinates',motions)
 print('PASS: decorated client receives surface-local motion under a translated canvas camera',flush=True)
 assert state()['view']==cam['view'],'File DnD changed camera'
 print(f'PASS: {toolkit} file-style drag and drop reaches the target through a translated canvas camera',flush=True)
 # A window originally outside the output must retain all of its surface.
 from PIL import Image
 image=base/'canvas.png';subprocess.run(['grim',str(image)],env=appenv,check=True,capture_output=True)
 pixels=Image.open(image).convert('RGB')
 for point,channel in [(source,1),(target,0)]:
  colour=pixels.getpixel(tuple(point));assert colour[channel]>150 and colour[2]<80,(point,colour)
 before=window()['at'];time.sleep(.5)
 subprocess.run(['grim',str(image)],env=appenv,check=True,capture_output=True)
 assert window()['at']==before,'Rendering changed native window geometry'
 print('PASS: offscreen canvas surfaces are visible and rendering does not move windows',flush=True)
 if toolkit=='gtk' and os.environ.get('HYPRSTACK_TEST_WINDOW_BEHAVIOUR'):
  def wait_client(title):
   for _ in range(30):
    found=next((c for c in json.loads(ctl('clients','-j')) if c['pid']==app.pid and c['title']==title),None)
    if found:return found
    time.sleep(.1)
   raise AssertionError('Missing test client: '+title)
  os.kill(app.pid,signal.SIGUSR2);other=wait_client('Canvas overlap regression')
  ctl('repl','hl.dispatch(hl.dsp.window.move({window=hl.get_window("address:'+other['address']+'"),x=2580,y=370,relative=false}))')
  ctl('repl','return hyprstack_layouts.canvas_action("viewport 2180 140")');time.sleep(.3)
  cam=state();w=window();click=screen(30,w['size'][1]*.65)
  send('move',*click);send('button',272,1);send('button',272,0)
  owned=[c for c in json.loads(ctl('clients','-j')) if c['pid']==app.pid]
  assert owned[-1]['address']==address,('Click did not raise the covered window',owned)
  print('PASS: clicking an uncovered area raises a partially covered canvas window',flush=True)
  time.sleep(5)
  dialog_view=state()['view']
  os.kill(app.pid,signal.SIGUSR1);dialog=wait_client('Canvas transient regression');time.sleep(.3)
  dialog=wait_client('Canvas transient regression')
  assert dialog['pinned'] and dialog['floating'],dialog
  assert state()['view']==dialog_view,'A modal dialog moved the canvas camera'
  mx,my=monitor['x'],monitor['y']
  assert abs(dialog['at'][0]+dialog['size'][0]/2-(mx+width/2))<32,dialog
  assert abs(dialog['at'][1]+dialog['size'][1]/2-(my+height/2))<32,dialog
  print('PASS: a transient modal dialog is centred on screen above the translated canvas',flush=True)
  time.sleep(5)
 if os.environ.get('HYPRSTACK_SOAK'):
  import re
  for iteration in range(8):
   start=[int(n) for n in re.findall(r'FRAME (\d+)',appLog.read_text())];old=start[-1] if start else 0
   time.sleep(5)
   latest=[int(n) for n in re.findall(r'FRAME (\d+)',appLog.read_text())];new=latest[-1] if latest else 0
   assert new-old>=60,('GPU client stopped receiving frames',iteration,old,new,appLog.read_text())
   image=base/'soak.png';subprocess.run(['grim',str(image)],env=appenv,check=True,capture_output=True)
   colour=Image.open(image).convert('RGB').getpixel((40,40));assert colour[2]>30,('Wallpaper disappeared',iteration,colour)
   if engine:assert engine.poll() is None,'Wallpaper Engine exited while canvas was running'
   print('PASS: sustained GPU client and animated wallpaper',iteration,new,colour,flush=True)
   if iteration % 2:
    ctl('repl','return hyprstack_layouts.set_mode("scrolling")');time.sleep(.4)
    ctl('repl','return hyprstack_layouts.set_mode("canvas")');time.sleep(.5)
    w=window()
    offset=[round(w['at'][0]+(w['size'][0]-width)/2),round(w['at'][1]+(w['size'][1]-height)/2)]
    ctl('repl','return hyprstack_layouts.canvas_action("viewport '+str(offset[0])+' '+str(offset[1])+'")');time.sleep(.3)
    print('PASS: mode switch restores canvas without replacing the client',flush=True)

 ctl('repl','return hyprstack_layouts.set_mode("scrolling")');time.sleep(1)
 if withoutBars:
  ctl('repl','return hyprstack_layouts.set_mode("canvas")');time.sleep(.5)
  assert state(),'Standalone canvas did not reopen'
  ctl('repl','return hyprstack_layouts.set_mode("scrolling")')
  print('PASS: canvas opens and closes without loading hyprbars',flush=True)
 else:
  snap=json.loads(ctl('repl','return hyprstack_layouts.overview_snapshot("WAYLAND-1")'))
  entry=next(item for item in snap['windows'] if item['address']==address)
  rect={'x':0,'y':0,'width':entry['width'],'height':entry['height']}
  entry.update(world=rect,frame=dict(rect,x=100,y=100,width=rect['width']*.5,height=rect['height']*.5))
  scene={'monitor':'WAYLAND-1','mode':'scrolling','workspace':entry['workspace'],'originalWorkspace':entry['workspace'],'camera':{'x':100,'y':100,'zoom':.5},'originCamera':{'x':100,'y':100,'zoom':.5},'colour':[.5,.3,.8],'windows':[entry],'worldRows':[]}
  ctl('repl','hyprstack_layouts.set_overview(true);return hyprstack_layouts.overview_scene("show",'+json.dumps(json.dumps(scene))+')');time.sleep(.4)
  # Move the cursor between two empty regions: software cursors are included
  # even without grim -c, so compare positions rather than capture flags.
  # A hidden cursor inherited from a client must not survive overview ownership.
  send('move',round(width*.65),round(height*.8));time.sleep(.1)
  plain=base/'overview-no-cursor.png';cursor=base/'overview-cursor.png'
  subprocess.run(['grim',str(plain)],env=appenv,check=True,capture_output=True)
  send('move',round(width*.8),round(height*.8));time.sleep(.1)
  subprocess.run(['grim','-c',str(cursor)],env=appenv,check=True,capture_output=True)
  from PIL import ImageChops
  delta=ImageChops.difference(Image.open(plain).convert('RGB'),Image.open(cursor).convert('RGB'))
  # The parent compositor can resize this nested output while the test runs.
  cursorX,cursorY=map(int,ctl('cursorpos').split(','))
  region=(cursorX-4,cursorY-4,min(delta.width,cursorX+64),min(delta.height,cursorY+64))
  assert delta.crop(region).getbbox(),('Cursor is missing from the overview',ctl('cursorpos'),delta.getbbox(),region)
  print('PASS: overview renders its cursor even when the client hides it',flush=True)
  native=base/'native-overview.png';subprocess.run(['grim',str(native)],env=appenv,check=True,capture_output=True)
  pixels=Image.open(native).convert('RGB')
  for ratio,channel in [(.25,1),(.75,0)]:
   point=(round(100+entry['width']*.5*ratio),round(100+entry['height']*.25))
   colour=pixels.getpixel(point);assert colour[channel]>150 and colour[2]<80,(point,colour)
  ctl('repl','hyprstack_layouts.overview_scene("reset");hyprstack_layouts.set_overview(false)')
  print('PASS: shell overview uses the same complete surface mask',flush=True)
  if os.environ.get('HYPRSTACK_RELOAD_PLUGIN'):
   # Leave a closing/fading window when the plugins unload. Its decoration
   # must be destroyed before the library containing its deleter is unmapped.
   app.terminate();app.wait(timeout=3);time.sleep(.05)
   plugin=str(base/'data/native/libspatialoverview.so')
   print('Plugin unload:',ctl('plugin','unload',plugin),flush=True)
   time.sleep(.8)
   print('After unload:',ctl('-j','plugin','list'),flush=True)
   bars=str(base/'data/native/hyprstack-bars.so')
   print('Bars unload:',ctl('plugin','unload',bars),flush=True)
   print('Bars load:',ctl('plugin','load',bars),flush=True)
   print('Plugin load:',ctl('plugin','load',plugin),flush=True)
   time.sleep(.8)
   ctl('repl','return hyprstack_layouts.set_mode("canvas",true)');time.sleep(1)
   assert json.loads(ctl('spatialoverview'))['screens'],'No canvas after plugin reload'
   ctl('repl','return hyprstack_layouts.set_mode("scrolling")')
   print('PASS: plugin reload after client close preserves the running compositor',flush=True)
 assert not ctl('configerrors'),ctl('configerrors')
except Exception:
 if 'appLog' in globals() and appLog.exists():print(appLog.read_text(),flush=True)
 if (base/'wall.log').exists():print((base/'wall.log').read_text(),flush=True)
 if (base/'compositor.log').exists():print((base/'compositor.log').read_text()[-4000:],flush=True)
 raise
finally:
 if engine and engine.poll() is None:engine.terminate();engine.wait(timeout=5)
 if engineLog:engineLog.close()
 if wallpaper and wallpaper.poll() is None:wallpaper.terminate();wallpaper.wait(timeout=3)
 if wallpaperLog:wallpaperLog.close()
 if pointer:
  pointer.stdin.close();pointer.wait(timeout=3);pointer.stdout.close()
 if app and app.poll() is None:app.terminate();app.wait(timeout=3)
 if 'out' in globals():out.close()
 if p and p.poll() is None:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 if log:log.close()
 if p and p.returncode not in (0,-signal.SIGTERM):
  raise RuntimeError(f'Nested compositor exited with {p.returncode}, including during cleanup')
