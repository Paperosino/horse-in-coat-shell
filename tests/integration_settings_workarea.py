#!/usr/bin/env python3
"""Actual SettingsWindow minimum size versus real stacking work area."""
import argparse,json,os,select,shutil,socket,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session,resize_nested_compositor,snapshot_qml_runtime
args=argparse.ArgumentParser();args.add_argument('--installed-runtime',action='store_true');options=args.parse_args()
require_wayland_session();ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-settings-workarea-') as directory:
 base=Path(directory);copy=base/'shell';shutil.copytree(ROOT/'shell',copy,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 cfg=base/'config/hics';cfg.mkdir(parents=True);(cfg/'layouts.json').write_text('{"mode":"stacking"}')
 (cfg/'shell.json').write_text('{"appearance":{"reducedMotion":true}}')
 native=base/'native';native.mkdir()
 for name in ('hics-bars.so','libhics-render-dispatch.so'):
  source=Path(os.environ.get('HICS_TEST_NATIVE_DIR',ROOT/'build'))/name
  shutil.copy2(source,native/name)
 (copy/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
import qs.modules.nexus
import qs.modules
import qs.services
ShellRoot {
 function find(item,test){if(test(item))return item;for(const child of item.children??[]){const found=find(child,test);if(found)return found;}return null;}
 id:root;property int bottomDepth:96;property bool sideShown:false
 GSFLoader {}
 SettingsWindow {id:win;visible:true;pageId:"display"}
 PanelWindow {anchors.top:true;anchors.left:true;anchors.right:true;implicitHeight:44;exclusiveZone:44;WlrLayershell.namespace:"hics-workarea-test-top";WlrLayershell.keyboardFocus:WlrKeyboardFocus.None;color:"#363245"}
 PanelWindow {anchors.bottom:true;anchors.left:true;anchors.right:true;implicitHeight:root.bottomDepth;exclusiveZone:root.bottomDepth;WlrLayershell.namespace:"hics-workarea-test-bottom";WlrLayershell.keyboardFocus:WlrKeyboardFocus.None;color:"#363245"}
 PanelWindow {visible:root.sideShown;anchors.top:true;anchors.bottom:true;anchors.left:true;implicitWidth:160;exclusiveZone:160;WlrLayershell.namespace:"hics-workarea-test-side";WlrLayershell.keyboardFocus:WlrKeyboardFocus.None;color:"#363245"}
 IpcHandler {target:"workareaTest";function showScale():bool{const page=root.find(win.contentItem,item=>typeof item.revealSearchTarget==="function");if(!page)return false;page.nState.searchTarget="displayScale";return page.revealSearchTarget();}function viewport():string{const page=root.find(win.contentItem,item=>typeof item.revealSearchTarget==="function");const row=root.find(page,item=>item.objectName==="displayScale");const control=row.searchFocusItem;const point=control.mapToItem(page.flickable,0,0);return JSON.stringify({height:page.flickable.height,scrollable:page.flickable.contentHeight>page.flickable.height,controlY:point.y,controlHeight:control.height,rowHeight:row.height});}function capture():void{const view=win.contentItem.children.find(c=>typeof c.availableWidth==="number"&&c.nState!==undefined);view.grabToImage(image=>image.saveToFile(__CAPTURE__));}function sidePanel():void{root.sideShown=true;}function resizePanel():void{root.bottomDepth=160;}function state():string {
  const view=win.contentItem.children.find(c=>typeof c.availableWidth==="number"&&c.nState!==undefined);
  return JSON.stringify({iconsReady:Qt.fontFamilies().includes("Material Symbols Rounded"),width:win.width,height:win.height,minWidth:win.minimumSize.width,minHeight:win.minimumSize.height,availableWidth:view?.availableWidth,availableHeight:view?.availableHeight,screen:win.screen?.name,monitor:Hypr.monitors.values.find(m=>m.name===win.screen?.name)?.lastIpcObject});
 }}
}'''.replace('__CAPTURE__',json.dumps(str(base/'capture.png'))))
 lua=base/'compositor.lua';lua.write_text('package.path='+json.dumps(str(ROOT/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\nhl.monitor({output="WAYLAND-1",mode="1280x800@60",position="0x0",scale=1})\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
 buscfg=base/'bus.conf';buscfg.write_text('<busconfig><type>session</type><listen>unix:path='+str(base/'bus')+'</listen><auth>EXTERNAL</auth><policy context="default"><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
 home=base/'home';home.mkdir()
 env=dict(os.environ,HOME=str(home),AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),HYPRSTACK_DATA_DIR=str(base),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'),PIPEWIRE_REMOTE='hics-fixture-absent',PULSE_SERVER='unix:'+str(base/'absent-pulse'))
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 if options.installed_runtime:
  assert (ROOT/'shell').resolve()==Path('/usr/share/hics/shell'),'Installed test must use installed sources'
  env.update(QML_IMPORT_PATH='/usr/share/hics/qml',QML2_IMPORT_PATH='/usr/share/hics/qml',LD_LIBRARY_PATH='/usr/share/hics/qml/Hyprstack/lib:/usr/share/hics/qs/lib')
 else:env.update(snapshot_qml_runtime(ROOT,base))
 bus=compositor=shell=None
 try:
  bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(buscfg)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  assert select.select([bus.stdout],[],[],3)[0];env['DBUS_SESSION_BUS_ADDRESS']=bus.stdout.readline().strip()
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   assert compositor.poll() is None,(base/'compositor.log').read_text();time.sleep(.1)
  assert instance;resize_nested_compositor(compositor.pid,1280,800)
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland')
  def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],env=env,text=True,timeout=8).strip()
  def monitors():return json.loads(ctl('monitors','-j'))
  def window():return next((w for w in json.loads(ctl('clients','-j')) if w['pid']==shell.pid),None)
  def wait(check,description):
   end=time.monotonic()+10
   while time.monotonic()<end:
    assert compositor.poll() is None
    if shell:assert shell.poll() is None,(base/'shell.log').read_text()[-6000:]
    if check():return
    time.sleep(.1)
   raise AssertionError(description+'\nWINDOW '+str(window())+'\nMONITOR '+str(monitors())+'\nUI '+str(ui()))
  def ui():
   result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','ipc','-p',str(copy),'call','workareaTest','state'],env=env,capture_output=True,text=True,timeout=5)
   return json.loads(result.stdout) if result.returncode==0 else {'error':result.stderr}
  with (base/'shell.log').open('w') as log:shell=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(copy)],env=env,stdout=log,stderr=subprocess.STDOUT)
  wait(lambda:window() and monitors()[0]['reserved'][1]>=44 and monitors()[0]['reserved'][3]>=96,'Settings/panels did not map')
  loaded=Path(f'/proc/{shell.pid}/maps').read_text();assert str(ROOT/'build')+'/' not in loaded,'Mutable build library mapped'
  if options.installed_runtime:assert '/usr/share/hics/qml/Hyprstack/lib/libhyprstack-config.so' in loaded,'Installed QML library not loaded'
  assert not ctl('configerrors'),ctl('configerrors')
  w=window();header=float(ctl('repl','return hl.plugin.hyprbars.titlebar_height('+json.dumps(w['address'])+','+json.dumps(w['stableId'])+')'));y=monitors()[0]['reserved'][1]+header+4
  ctl('eval','local w=hl.get_window('+json.dumps('address:'+w['address'])+');hl.dispatch(hl.dsp.window.move({window=w,x=180,y='+str(y)+',relative=false}))')
  def fits():
   w=window();m=monitors()[0];left,top,right,bottom=m['reserved']
   header=float(ctl('repl','return hl.plugin.hyprbars.titlebar_height('+json.dumps(w['address'])+','+json.dumps(w['stableId'])+')'))
   return w['at'][0]>=m['x']+left-1 and w['at'][1]-header>=m['y']+top-1 and w['at'][0]+w['size'][0]<=m['x']+m['width']/m['scale']-right+1 and w['at'][1]+w['size'][1]<=m['y']+m['height']/m['scale']-bottom+1
  time.sleep(.5);assert fits(),(window(),monitors(),ui())
  ctl('eval','hl.monitor({output="WAYLAND-1",mode="1280x800@60",position="0x0",scale=1.25})')
  wait(lambda:monitors()[0]['scale']==1.25,'Scale did not apply')
  wait(fits,'Actual SettingsWindow exceeds shrunken reserved work area')
  time.sleep(2)
  assert fits(),('Settings escaped after configure settled',window(),monitors(),ui())
  state=ui();actual=window();assert abs(state['width']-actual['size'][0])<=1 and abs(state['height']-actual['size'][1])<=1,(state,actual)
  print('PASS actual SettingsWindow scale1.25:',json.dumps(ui()),flush=True)
  result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','ipc','-p',str(copy),'call','workareaTest','resizePanel'],env=env,capture_output=True,text=True,timeout=5);assert result.returncode==0,result.stderr
  wait(lambda:monitors()[0]['reserved'][3]>=160,'Panel resize did not commit')
  time.sleep(1)
  wait(fits,'Actual SettingsWindow ignores late reservation')
  state=ui();assert state['minHeight']<=640-sum(monitors()[0]['reserved'][1::2])-header,state
  print('PASS actual SettingsWindow late panel resize:',json.dumps(state),flush=True)
  result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','ipc','-p',str(copy),'call','workareaTest','sidePanel'],env=env,capture_output=True,text=True,timeout=5);assert result.returncode==0,result.stderr
  wait(lambda:monitors()[0]['reserved'][0]>=160,'Side panel did not commit');time.sleep(1)
  wait(fits,'Actual SettingsWindow ignores side reservation')
  print('PASS actual SettingsWindow side panel:',json.dumps(ui()),flush=True)
  temp=cfg/'shell.tmp';temp.write_text('{"appearance":{"reducedMotion":true,"scale":1.5}}');temp.replace(cfg/'shell.json')
  time.sleep(2);wait(fits,'Large UI scale escaped reserved work area')
  assert ui()['iconsReady'],'Production Material Symbols font did not load'
  print('PASS actual SettingsWindow large UI scale:',json.dumps(ui()),flush=True)
  def show_scale():
   result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','ipc','-p',str(copy),'call','workareaTest','showScale'],env=env,capture_output=True,text=True,timeout=5)
   return result.returncode==0 and result.stdout.strip()=='true'
  wait(show_scale,'Display scale control cannot be revealed')
  result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','ipc','-p',str(copy),'call','workareaTest','viewport'],env=env,capture_output=True,text=True,timeout=5);assert result.returncode==0,result.stderr
  viewport=json.loads(result.stdout);assert viewport['height']>=96 and viewport['scrollable'] and viewport['controlY']>=-1 and viewport['controlY']+viewport['controlHeight']<=viewport['height']+1,viewport
  print('PASS compact page retains scrollable settings and reveals scale control:',json.dumps(viewport),flush=True)
  result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','ipc','-p',str(copy),'call','workareaTest','capture'],env=env,capture_output=True,text=True,timeout=5);assert result.returncode==0,result.stderr
  wait(lambda:(base/'capture.png').exists(),'Settings capture did not finish')
  shutil.copy2(base/'capture.png',Path(os.environ.get('HICS_TEST_CAPTURE','/tmp/hics-settings-workarea.png')))
  # The observer must not republish unchanged reservations on ordinary frames.
  with socket.socket(socket.AF_UNIX) as events:
   events.connect(str(Path(os.environ['XDG_RUNTIME_DIR'])/'hypr'/instance['instance']/'.socket2.sock'));events.setblocking(False)
   time.sleep(1);data=b''
   while True:
    try:part=events.recv(65536)
    except BlockingIOError:break
    if not part:break
    data+=part
   assert b'hics_workarea>>' not in data,data
  print('PASS stable work area does not republish per frame',flush=True)
  w=window();ctl('eval','local w=hl.get_window('+json.dumps('address:'+w['address'])+');hl.dispatch(hl.dsp.window.resize({window=w,x=700,y=250,relative=false}));hl.dispatch(hl.dsp.window.close({window=w}))')
  wait(lambda:window() is None,'Settings did not close during resize')
  time.sleep(.2);assert compositor.poll() is None
  print('PASS close during resize preserves compositor',flush=True)
  output=(base/'shell.log').read_text();assert not any(text in output for text in ('TypeError','ReferenceError','Binding loop')),output[-6000:]
  assert not ctl('configerrors'),ctl('configerrors')
 except Exception:
  print((base/'compositor.log').read_text()[-12000:],flush=True)
  if (base/'shell.log').exists():Path('/tmp/hics-settings-workarea.log').write_text((base/'shell.log').read_text())
  raise
 finally:
  for process in (shell,compositor,bus):
   if process and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
