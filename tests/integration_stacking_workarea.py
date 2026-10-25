#!/usr/bin/env python3
"""Fullscreen -> stacking maximize with late real layer-shell reservations."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session,resize_nested_compositor
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
OUTPUT_SCALE=float(os.environ.get('HICS_TEST_OUTPUT_SCALE','1'));assert 1<=OUTPUT_SCALE<=2
with tempfile.TemporaryDirectory(prefix='hics-workarea-') as directory:
 base=Path(directory);(base/'config/hics').mkdir(parents=True);(base/'native').mkdir()
 for name in ('libhics-render-dispatch.so','hics-bars.so','libspatialoverview.so'):
  source=Path(os.environ['HICS_TEST_NATIVE_DIR'])/name if os.environ.get('HICS_TEST_NATIVE_DIR') else next(p for p in (ROOT/'build'/name,ROOT/'build/third_party/phantomat'/name) if p.exists())
  shutil.copy2(source,base/'native'/name)
 (base/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
 lua=base/'test.lua';lua.write_text('package.path='+json.dumps(str(ROOT/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\nhl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale='+str(OUTPUT_SCALE)+'})\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/animations.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
 control=base/'panels.json';control.write_text('{"edge":"bottom","depth":72,"visible":true}')
 (base/'panels.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
ShellRoot {
 id:root
 property string edge:"bottom"
 property int depth:72
 property bool shown:true
 FileView {path:"'''+str(control)+'''";watchChanges:true;onFileChanged:reload();onLoaded:{const value=JSON.parse(text());root.edge=value.edge;root.depth=value.depth;root.shown=value.visible;}}
 PanelWindow {
  anchors.left:root.edge==="left";anchors.right:root.edge==="right"
  anchors.top:root.edge==="top";anchors.bottom:root.edge==="bottom"
  implicitWidth:root.edge==="left"||root.edge==="right"?root.depth:200
  implicitHeight:root.edge==="top"||root.edge==="bottom"?root.depth:200
  exclusiveZone:root.shown?root.depth:0
  WlrLayershell.layer:WlrLayer.Top
  WlrLayershell.namespace:"hics-workarea-dock"
  WlrLayershell.keyboardFocus:WlrKeyboardFocus.None
  color:"#53507a";mask:Region{}
 }
 // A second panel ensures the compositor's combined reservation is respected.
 PanelWindow {
  anchors.top:true;anchors.left:true;anchors.right:true
  implicitHeight:36;exclusiveZone:root.shown?36:0
  WlrLayershell.layer:WlrLayer.Top
  WlrLayershell.namespace:"hics-workarea-bar"
  WlrLayershell.keyboardFocus:WlrKeyboardFocus.None
  color:"#333044";mask:Region{}
 }
}''')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),HYPRSTACK_DATA_DIR=str(base));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=None;apps=[];panel=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  for _ in range(100):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   assert compositor.poll() is None
   time.sleep(.1)
  assert instance;resize_nested_compositor(compositor.pid)
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
  def ctl(*args):
   result=subprocess.run(['hyprctl','-i',instance['instance'],*args],env=env,capture_output=True,text=True,timeout=10)
   assert result.returncode==0,result.stdout+result.stderr;return result.stdout.strip()
  def wait(check,description):
   end=time.monotonic()+6
   while time.monotonic()<end:
    if check():return
    assert compositor.poll() is None,(base/'compositor.log').read_text()[-4000:]
    time.sleep(.05)
   raise AssertionError(description)
  def monitor():return json.loads(ctl('monitors','-j'))[0]
  def reserve(edge,depth,shown):
   temp=control.with_suffix('.tmp');temp.write_text(json.dumps(dict(edge=edge,depth=depth,visible=shown)));temp.replace(control)
  def window(pid):return next((w for w in json.loads(ctl('clients','-j')) if w['pid']==pid),None)
  def command(window,body):return ctl('eval','local w=hl.get_window('+json.dumps('address:'+window['address'])+');'+body)
  def action(w,op):return ctl('eval','hyprstack_layouts.action('+json.dumps(op)+','+json.dumps(w['address'])+')')
  with (base/'panels.log').open('w') as log:panel=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'panels.qml')],env=env,stdout=log,stderr=subprocess.STDOUT)
  wait(lambda:monitor()['reserved'][3]>=70,'Panel did not reserve bottom edge')
  for klass in ('org.hics.WorkareaFixture','code'):
   app=subprocess.Popen(['kitty','--class',klass,'--title','Fullscreen work area','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);apps.append(app)
   wait(lambda:bool(window(app.pid)),'Application did not map');time.sleep(1)
   w=window(app.pid)
   action(w,'maximize-unset')
   command(w,'hl.dispatch(hl.dsp.window.resize({window=w,x=500,y=280,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=180,y=180,relative=false}));hl.dispatch(hl.dsp.focus({window=w}))');time.sleep(.5)
   action(w,'remember-stacking')
   bar=0 if klass=='code' else 32
   def fits():
    win=window(app.pid);m=monitor();left,top,right,bottom=m['reserved'];width=m['width']/m['scale'];height=m['height']/m['scale']
    expected=[m['x']+left,m['y']+top+bar,width-left-right,height-top-bottom-bar]
    actual=win['at']+win['size']
    return max(abs(a-b) for a,b in zip(actual,expected))<=1 and win['fullscreenClient']==1
   for edge,depth in (('bottom',72),('left',88),('right',64),('top',80)):
    reserve(edge,depth,True);time.sleep(.3)
    action(w,'maximize-set');wait(fits,'Initial maximize does not fit '+edge)
    command(w,'hl.dispatch(hl.dsp.window.fullscreen_state({window=w,internal=2,client=2,action="set"}))');time.sleep(.2)
    wait(lambda:window(app.pid)['fullscreen']==2,'No exclusive fullscreen')
    reserve(edge,depth,False);wait(lambda:sum(monitor()['reserved'])==0,'Reservations did not clear')
    command(w,'hl.dispatch(hl.dsp.window.fullscreen_state({window=w,internal=0,client=0,action="set"}))')
    wait(lambda:window(app.pid)['fullscreenClient']==1,'Maximize state not restored')
    # Deliberately later than fullscreen restoration, as QML/layer-shell commits are asynchronous.
    time.sleep(.3);reserve(edge,depth,True)
    wait(lambda:sum(monitor()['reserved'])>=depth,'Late dock reservation missing')
    wait(fits,'Restored maximized window overlaps late '+edge+' dock: '+str(window(app.pid))+' '+str(monitor()['reserved']))
    # Reconfigure a visible dock without touching fullscreen or monitor layout.
    reserve(edge,depth+20,True);wait(lambda:sum(monitor()['reserved'])>=depth+20,'Dock resize not committed');wait(fits,'Visible dock resize not reflected')
    action(w,'maximize-unset');wait(lambda:window(app.pid)['fullscreenClient']==0,'Cannot restore normal window')
    time.sleep(.25);normal=window(app.pid)
    assert max(abs(a-b) for a,b in zip(normal['at']+normal['size'],[180,180,500,280]))<=2,normal
    print('PASS:',klass,edge,'late reservation, resize and original geometry',flush=True)
   action(w,'maximize-set');wait(fits,'Cannot maximize before rapid transition')
   command(w,'hl.dispatch(hl.dsp.window.fullscreen_state({window=w,internal=2,client=2,action="set"}));hl.dispatch(hl.dsp.window.fullscreen_state({window=w,internal=0,client=0,action="set"}))')
   wait(fits,'Rapid fullscreen round trip lost maximize state')
   command(w,'hl.dispatch(hl.dsp.window.fullscreen_state({window=w,internal=2,client=2,action="set"}))');time.sleep(.2)
   command(w,'hl.dispatch(hl.dsp.window.fullscreen_state({window=w,internal=0,client=1,action="set"}))')
   wait(fits,'Direct fullscreen to client maximize does not fit work area')
   print('PASS:',klass,'rapid fullscreen round trip and direct maximize',flush=True)
   app.terminate();app.wait(timeout=3)
  assert not ctl('configerrors'),ctl('configerrors')
 except Exception:
  print('FAILED_WINDOW',window(app.pid) if 'app' in locals() else None,flush=True)
  for state in Path(os.environ['XDG_RUNTIME_DIR']).glob('hics-layouts-'+instance['instance']+'.json'):print('SAVED_STATE',state.read_text()[-6000:],flush=True)
  if panel:print((base/'panels.log').read_text()[-2500:])
  raise
 finally:
  for process in [panel,*apps,compositor]:
   if process and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
