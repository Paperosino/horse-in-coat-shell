#!/usr/bin/env python3
"""Real desktop icons, watcher idleness and file safety in isolated HOME/session."""
import ast,json,os,shlex,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session,resize_nested_compositor
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-desktop-icons-') as directory:
 base=Path(directory);home=base/'home';desktop=home/'Desktop';desktop.mkdir(parents=True)
 config=base/'config';config.mkdir();(config/'user-dirs.dirs').write_text('XDG_DESKTOP_DIR="'+str(desktop)+'"\n')
 (desktop/'Документ $(touch INJECTED).txt').write_text('original')
 (desktop/'Folder').mkdir();(desktop/'Folder/inside.txt').write_text('nested')
 (desktop/'.private').write_text('hidden')
 (desktop/'untrusted.desktop').write_text('[Desktop Entry]\nType=Application\nName=Unsafe\nExec=touch '+str(base/'MUST_NOT_RUN')+'\n')
 (desktop/'trusted.desktop').write_text('[Desktop Entry]\nType=Application\nName=Trusted fixture\nIcon=utilities-terminal\nExec=true\n');(desktop/'trusted.desktop').chmod(0o700)
 outside=home/'outside.txt';outside.write_text('keep');(desktop/'link').symlink_to(outside)
 shutil.copytree(ROOT/'shell',base/'shell',ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 qml='''//@ pragma IconTheme Adwaita
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Hyprstack.Config
import Hyprstack.Services
import qs.modules.background
import qs.services
import qs.components.containers
ShellRoot {
 id:root
 property int changes:0
 property string previous:""
 FileView {id:status;path:STATUS;printErrors:false}
 FileView {id:command;path:COMMAND;watchChanges:true;printErrors:false;onFileChanged:reload();onLoaded:{const text=command.text();if(text===root.previous)return;root.previous=text;let request;try{request=JSON.parse(text)}catch(e){return}
  if(request.op==="hidden")GlobalConfig.background.desktopIcons.showHidden=request.value;
  if(request.op==="active")GlobalConfig.background.desktopIcons.enabled=request.value;
  if(request.op==="place")DesktopFiles.place("WAYLAND-1",request.url,3,2);
  if(request.op==="copy")DesktopFiles.copy(request.urls,request.cut??false);
  if(request.op==="open")DesktopFiles.open(request.url);
  if(request.op==="paste")DesktopIcons.paste();
  if(request.op==="menu")icons.openMenu(100,100);
  if(request.op==="full"){win.visible=false;GlobalConfig.background.wallpaperEnabled=false;full.active=true;}
 }}
 LazyLoader {id:full;active:false;component:Background {}}
 Connections {target:DesktopFiles;function onChanged(){root.changes++}}
 Component.onCompleted:GlobalConfig.background.desktopIcons.enabled=true
 StyledWindow {
  id:win;name:"desktop-icons-test";screen:Quickshell.screens[0];anchors.top:true;anchors.bottom:true;anchors.left:true;anchors.right:true
  WlrLayershell.namespace:"hics-desktop";WlrLayershell.layer:WlrLayer.Background;WlrLayershell.keyboardFocus:WlrKeyboardFocus.OnDemand
  color:"#202438"
  DesktopFileView {id:icons;anchors.fill:parent;anchors.margins:24;screen:win.screen}
 }
 Timer {interval:80;running:true;repeat:true;onTriggered:status.setText(JSON.stringify({changes:root.changes,entries:DesktopFiles.entries,positions:DesktopFiles.positions,error:DesktopFiles.error||DesktopIcons.error,active:DesktopFiles.active,loading:DesktopFiles.loading,selected:icons.selected,menu:icons.contextMenuOpen,editor:icons.editorOpen,cellWidth:icons.cellWidth,cellHeight:icons.cellHeight,placements:icons.placements,clipboard:DesktopFiles.clipboardFiles()}))}
}'''.replace('STATUS',json.dumps(str(base/'status.json'))).replace('COMMAND',json.dumps(str(base/'command.json')))
 (base/'shell/shell.qml').write_text(qml);(base/'command.json').write_text('{}')
 (base/'test.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
 canvas=bool(os.environ.get('HICS_TEST_DESKTOP_CANVAS'))
 if canvas:
  (base/'native').mkdir();(config/'hics').mkdir(exist_ok=True);(config/'hics/layouts.json').write_text('{"mode":"stacking"}')
  for name in ('libhics-render-dispatch.so','hics-bars.so','libspatialoverview.so'):
   source=next(p for p in (ROOT/'build'/name,ROOT/'build/third_party/phantomat'/name) if p.exists());shutil.copy2(source,base/'native'/name)
  with (base/'test.lua').open('a') as file:
   file.write('package.path='+json.dumps(str(ROOT/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/animations.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
 env=dict(os.environ,HOME=str(home),AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(config),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),HYPRSTACK_DATA_DIR=str(base))
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=daemon=shell=pointer=client=None
 bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True)
 env.update(DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip(),DBUS_SYSTEM_BUS_ADDRESS='unix:path=/nonexistent/hics-private-system')
 def state():
  try:return json.loads((base/'status.json').read_text())
  except (FileNotFoundError,json.JSONDecodeError):return {}
 def wait(check,seconds=8):
  until=time.monotonic()+seconds
  while time.monotonic()<until:
   value=state()
   if check(value):return value
   if shell and shell.poll() is not None:break
   time.sleep(.06)
  raise AssertionError((state(),(base/'shell.log').read_text()[-9000:]))
 def command(**args):
  path=base/'command.json';replacement=base/'command.next';replacement.write_text(json.dumps(args));replacement.replace(path);time.sleep(.2)
 def call(method,*args):
  output=subprocess.check_output(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.'+method,*args],env=env,text=True,stderr=subprocess.DEVNULL)
  return json.loads(ast.literal_eval(output)[0])
 def job(**args):
  started=call('Start','integration.desktop',json.dumps(args))
  for _ in range(150):
   result=call('Result',started['id'])
   if result.get('finished'):return result
   time.sleep(.03)
  raise AssertionError(started)
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'test.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance;resize_nested_compositor(compositor.pid)
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland')
  with (base/'daemon.log').open('w') as log:daemon=subprocess.Popen([str(ROOT/'build/native/desktop/hics-desktopd')],env=env,stdout=log,stderr=subprocess.STDOUT)
  with (base/'shell.log').open('w') as log:shell=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'shell')],env=env,stdout=log,stderr=subprocess.STDOUT)
  value=wait(lambda s:len(s.get('entries',[]))==5 and not s.get('loading'))
  assert not value['error'],value
  names=[e['name'] for e in value['entries']];assert 'Trusted fixture' in names and 'untrusted.desktop' in names,names
  # Changes made by any file manager are observed without polling.
  (desktop/'external.txt').write_text('external');wait(lambda s:any(e['name']=='external.txt' for e in s.get('entries',[])))
  baseline=state()['changes'];time.sleep(.8);assert state()['changes']==baseline,'Desktop keeps polling while idle'
  command(op='hidden',value=True);wait(lambda s:any(e['name']=='.private' for e in s.get('entries',[])))
  url=(desktop/'external.txt').as_uri();command(op='place',url=url);wait(lambda s:s.get('positions',{}).get('WAYLAND-1',{}).get('external.txt')==[3,2])
  command(op='copy',urls=[url],cut=True);value=wait(lambda s:s.get('clipboard',{}).get('cut'));assert value['clipboard']['sources']==[str(desktop/'external.txt')]
  command(op='open',url=(desktop/'untrusted.desktop').as_uri());wait(lambda s:'not trusted' in s.get('error',''));assert not (base/'MUST_NOT_RUN').exists()
  assert not job(action='mkdir',name='Новая папка')['error'];assert (desktop/'Новая папка').is_dir()
  assert job(action='mkdir',name='../escape')['error'];assert not (home/'escape').exists()
  assert not job(action='rename',path=str(desktop/'external.txt'),name='renamed.txt')['error'];assert (desktop/'renamed.txt').read_text()=='external'
  assert job(action='rename',path=str(desktop/'renamed.txt'),name='Документ $(touch INJECTED).txt')['error'];assert (desktop/'Документ $(touch INJECTED).txt').read_text()=='original'
  assert job(action='trash',sources=[str(outside)])['error'];assert outside.exists()
  assert not job(action='trash',sources=[str(desktop/'link')])['error'];assert outside.read_text()=='keep'
  source=home/'move.txt';source.write_text('moved');assert not job(action='move',sources=[str(source)])['error'];assert not source.exists() and (desktop/'move.txt').read_text()=='moved'
  source.write_text('new');assert job(action='move',sources=[str(source)])['error'];assert source.read_text()=='new' and (desktop/'move.txt').read_text()=='moved'
  incoming=home/'Incoming folder';incoming.mkdir();(incoming/'nested.txt').write_text('copied through shared worker')
  command(op='copy',urls=[incoming.as_uri()],cut=False);command(op='paste')
  wait(lambda s:(desktop/'Incoming folder/nested.txt').exists())
  assert (desktop/'Incoming folder/nested.txt').read_text()=='copied through shared worker'
  assert any(job['operation']=='transfer.copy' and job['phase']=='completed' for job in call('Status')['jobs'])
  if canvas:
   subprocess.run(['hyprctl','-i',instance['instance'],'plugin','load',str(base/'native/libspatialoverview.so')],env=env,check=True,capture_output=True);time.sleep(.6)
   client=subprocess.Popen(['kitty','--class','org.hics.DesktopCanvasFixture','-o','confirm_os_window_close=0','sleep','300'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   time.sleep(.6)
   for script in ('hyprstack_layouts.set_mode("canvas")','hyprstack_layouts.canvas_action("viewport 8000 6000")'):
    subprocess.run(['hyprctl','-i',instance['instance'],'repl',script],env=env,check=True,capture_output=True);time.sleep(.5)
  # Native pointer: select, open the desktop menu, dismiss by clicking outside.
  fixtures=ROOT/'tests/fixtures'
  subprocess.run(['wayland-scanner','client-header',str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/'virtual-pointer.h')],check=True)
  subprocess.run(['wayland-scanner','private-code',str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/'virtual-pointer-protocol.c')],check=True)
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
  subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(base/'virtual-pointer-protocol.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
  env.update(HYPRSTACK_POINTER_WIDTH='1280',HYPRSTACK_POINTER_HEIGHT='900')
  pointer=subprocess.Popen([str(base/'pointer')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1);assert pointer.stdout.readline().strip()=='ready'
  def send(text):
   pointer.stdin.write(text+'\n');pointer.stdin.flush();assert pointer.stdout.readline().strip()=='ok';time.sleep(.1)
  send('move 70 70');send('button 272 1');send('button 272 0');wait(lambda s:len(s.get('selected',[]))==1)
  send('button 273 1');send('button 273 0');wait(lambda s:s.get('menu'))
  subprocess.run(['grim','-o','WAYLAND-1',str(base/'preview.png')],env=env,check=True,capture_output=True,timeout=6);shutil.copy2(base/'preview.png','/tmp/hics-desktop-icons-preview.png')
  send('move 1100 700');send('button 272 1');send('button 272 0');wait(lambda s:not s.get('menu'))
  if not canvas:
   send('move 70 70');send('button 273 1');send('button 273 0');wait(lambda s:s.get('menu'))
   client=subprocess.Popen(['kitty','--class','org.hics.DesktopFocusFixture','-o','confirm_os_window_close=0','sleep','300'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   for _ in range(80):
    own=next((w for w in json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'clients','-j'])) if w['pid']==client.pid),None)
    if own:break
    time.sleep(.05)
   assert own
   send(f'move {own["at"][0]+own["size"][0]//2} {own["at"][1]+own["size"][1]//2}');send('button 272 1');send('button 272 0')
   wait(lambda s:not s.get('menu'))
   client.terminate();client.wait(timeout=5);client=None;time.sleep(.3)
  send('move 70 70');send('button 272 1')
  for point in (90,140,200,280,350):send(f'move {point} {point}')
  send('button 272 0');wait(lambda s:any(pos==[3,3] for pos in s.get('positions',{}).get('WAYLAND-1',{}).values()))
  command(op='active',value=False);wait(lambda s:s.get('active') is False and not s.get('entries'))
  baseline=state()['changes'];(desktop/'while-disabled.txt').write_text('quiet');time.sleep(.7);assert state()['changes']==baseline,'Disabled icons still monitor files'
  command(op='active',value=True);wait(lambda s:any(e['name']=='while-disabled.txt' for e in s.get('entries',[])))
  assert 'external.txt' not in state()['positions'].get('WAYLAND-1',{}),'Removed desktop entry left a stale placement'
  command(op='active',value=False);command(op='full');time.sleep(.5);command(op='active',value=True);time.sleep(.5)
  layers=subprocess.check_output(['hyprctl','-i',instance['instance'],'layers','-j'],env=env,text=True)
  assert 'hyprstack-background' in layers,layers
  # A mapped parent may stop frame callbacks while occluded; do not block QA.
  try:subprocess.run(['grim','-o','WAYLAND-1','/tmp/hics-desktop-icons-full-background.png'],env=env,check=True,capture_output=True,timeout=4)
  except subprocess.TimeoutExpired:pass
  output=(base/'shell.log').read_text();assert not any(s in output for s in ('TypeError:','ReferenceError:','Binding loop','Cannot assign','Unable to assign','Failed to load configuration')),output[-9000:]
  print('PASS: desktop files, idle watcher, hidden items, native menu dismissal, clipboard, launcher trust, safe rename/trash/move and opt-out')
 finally:
  for process in (pointer,client,shell,daemon,compositor,bus):
   if process and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=6)
    except subprocess.TimeoutExpired:process.kill();process.wait()
  for name in ('shell.log','daemon.log','compositor.log'):
   if (base/name).exists():shutil.copy2(base/name,'/tmp/hics-desktop-icons-'+name)
