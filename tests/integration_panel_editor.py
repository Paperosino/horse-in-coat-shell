#!/usr/bin/env python3
"""Real pointer drag-and-drop against the production panel layout editor."""
import json,os,shlex,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session();ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-panel-editor-') as directory:
 base=Path(directory);shell=base/'shell';shutil.copytree(ROOT/'shell',shell,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 state=base/'state.json'
 (shell/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import qs.services
import qs.modules.nexus
import qs.modules.nexus.pages
import qs.modules.extensions as Extensions
ShellRoot {
 id:root
 NexusState {id:state}
 property bool widgetsMode:false
 Extensions.PluginHost {}
 FileView {path:CONTROL;watchChanges:true;printErrors:false;onFileChanged:reload();onLoaded:if(text()==="widgets"){root.widgetsMode=true;Plugins.desktopEditing=true;}}

 FloatingWindow {id:window;title:"hics panel editor fixture";visible:true;implicitWidth:1100;implicitHeight:900
  StatusbarLayoutPage {id:page;visible:!root.widgetsMode;anchors.fill:parent;nState:state}
  Extensions.PluginDesktop {id:desktop;visible:root.widgetsMode;anchors.fill:parent;screen:Quickshell.screens[0]}
 }
 function find(item,name){if(item.objectName===name)return item;for(const child of item.children??[]){const found=find(child,name);if(found)return found;}return null;}
 function box(item){if(!item)return null;const p=item.mapToItem(window.contentItem,0,0);return {x:p.x,y:p.y,w:item.width,h:item.height};}
 FileView {id:out;path:STATE;printErrors:false}
 property bool placed:false
 Timer {interval:100;running:true;repeat:true;onTriggered:{
  const source=root.find(window.contentItem,"panelWidget-0-logo"),zone=root.find(window.contentItem,"panelZone-2");
  if(source&&zone&&!root.placed&&!page.contentLayoutSettled.running){page.flickable.contentY+=root.box(source).y-350;root.placed=true;}
  out.setText(JSON.stringify({source:root.box(source),zone:root.box(zone),left:page.leftWidgets,right:page.rightWidgets,drag:page.dragActive,widget:root.widgetsMode?root.box(root.find(desktop,"desktopWidget-isolated-counter")):null}));
 }}
}'''.replace('STATE',json.dumps(str(state))).replace('CONTROL',json.dumps(str(base/'control'))))
 fixtures=ROOT/'tests/fixtures'
 for flag,name in [('client-header','virtual-pointer.h'),('private-code','virtual-pointer.c')]:subprocess.run(['wayland-scanner',flag,str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/name)],check=True)
 flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
 subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(base/'virtual-pointer.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
 (base/'control').write_text('');(base/'config/hics').mkdir(parents=True);(base/'config/hics/plugins.json').write_text(json.dumps({'enabled':{'isolated-counter':True}}));(base/'config/hics/shell.json').write_text(json.dumps({'bar':{'entries':[{'id':i,'enabled':True} for i in ('logo','clock','spacer','activeWindow','spacer','statusIcons')]}}))
 (base/'compositor.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1100x900@60",position="0x0",scale=1})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'history'),XDG_CACHE_HOME=str(base/'cache'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=process=pointer=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'compositor.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance,'No nested compositor'
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland',QT_QUICK_BACKEND='software',QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),HYPRSTACK_POINTER_WIDTH='1100',HYPRSTACK_POINTER_HEIGHT='900')
  run=base/'runner.py';run.write_text('import os,sys\nos.environ["DBUS_SYSTEM_BUS_ADDRESS"]=os.environ["DBUS_SESSION_BUS_ADDRESS"]\nos.execvp(sys.argv[1],sys.argv[1:])\n')
  with (base/'shell.log').open('w') as log:process=subprocess.Popen(['dbus-run-session','--','python3',str(run),'quickshell','-p',str(shell)],env=env,stdout=log,stderr=subprocess.STDOUT)
  def read():
   try:return json.loads(state.read_text())
   except (OSError,ValueError):return {}
  for _ in range(100):
   data=read()
   if data.get('source') and 150<data['source']['y']<600:break
   time.sleep(.1)
  assert data.get('source'),(base/'shell.log').read_text()
  time.sleep(.7);data=read()
  monitor=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'-j','monitors']))[0]
  env.update(HYPRSTACK_POINTER_WIDTH=str(monitor['width']/monitor['scale']),HYPRSTACK_POINTER_HEIGHT=str(monitor['height']/monitor['scale']))
  pointer=subprocess.Popen([str(base/'pointer')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert pointer.stdout.readline().strip()=='ready'
  offset=next(c['at'] for c in json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'-j','clients'])) if c['title']=='hics panel editor fixture')
  def send(op,x,y):
   if op=='move':x+=offset[0];y+=offset[1]
   pointer.stdin.write(f'{op} {int(x)} {int(y)}\n');pointer.stdin.flush();assert pointer.stdout.readline().strip()=='ok';time.sleep(.05)
  source=data['source'];zone=data['zone'];x=source['x']+40;y=source['y']+15;targetX=zone['x']+zone['w']/2;targetY=zone['y']+24
  send('move',x,y);send('button',272,1)
  for i in range(1,16):send('move',x+(targetX-x)*i/15,y+(targetY-y)*i/15)
  mid=read();send('button',272,0);time.sleep(.7);data=read();data['during']=mid;data['offset']=offset;data['monitor']={k:monitor[k] for k in ('width','height','scale')}
  assert 'logo' not in data['left'] and 'logo' in data['right'],(data,(base/'shell.log').read_text())
  assert mid['drag'],mid
  (base/'control').write_text('widgets')
  for _ in range(50):
   data=read()
   if data.get('widget') and data['widget']['h']>60:break
   time.sleep(.1)
  tile=data['widget'];assert tile,tile
  def drag(x,y,dx,dy):
   send('move',x,y);send('button',272,1)
   for i in range(1,11):send('move',x+dx*i/10,y+dy*i/10)
   send('button',272,0);time.sleep(.5)
  drag(tile['x']+25,tile['y']+25,100,64)
  moved=read()['widget'];assert moved['x']>=tile['x']+64 and moved['y']>=tile['y']+32,(tile,moved)
  drag(moved['x']+moved['w']-8,moved['y']+moved['h']-8,64,48)
  resized=read()['widget'];assert resized['w']>=moved['w']+32 and resized['h']>=moved['h']+16,(moved,resized)
  prefs=json.loads((base/'config/hics/plugins.json').read_text());geometry=prefs['desktopLayout']['isolated-counter'];assert len(geometry)==1
  assert list(geometry.values())[0]['width']==resized['w']
  print('PASS: desktop widget pointer movement, corner resizing and per-monitor persistence')
  output=(base/'shell.log').read_text()
  assert not any(e in output for e in ('TypeError:','ReferenceError:','Binding loop')),output
  print('PASS: real pointer drag moves a panel widget between zones and persists its position')
 finally:
  for child in (pointer,process,compositor):
   if child and child.poll() is None:
    child.terminate()
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:child.kill();child.wait()
