#!/usr/bin/env python3
"""Native titlebar, drawer keyboard/modal input and file drag on private data."""
import json, os, shlex, shutil, subprocess, tempfile, time
from pathlib import Path
from integration_support import require_wayland_session, resize_nested_compositor, snapshot_qml_runtime

require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
QS='/usr/share/hics/qs/bin/hics-qs'
base=Path(tempfile.mkdtemp(prefix='hics-shell-interactions-'))
print('Artifacts:',base,flush=True)
processes=[]
def wait(check,description,timeout=12):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=check()
        if value:return value
        time.sleep(.04)
    raise AssertionError(description() if callable(description) else description)

try:
    shell=base/'shell';shutil.copytree(ROOT/'shell',shell,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
    if os.environ.get('HICS_TEST_TRACE_DRAG'):
        path=shell/'modules/dock/DockContent.qml';source=path.read_text()
        source=source.replace('function updatePoint(p: point): void {','function updatePoint(p: point): void { console.log("DRAG_POINT",p.x,p.y);')
        source=source.replace('if(!root||!fileDrag||!success||!fileDrag.containsDrag||fileDrag.generation!==current)return;','console.log("DRAG_CURSOR",success,text,fileDrag.generation,current);if(!root||!fileDrag||!success||!fileDrag.containsDrag||fileDrag.generation!==current)return;')
        path.write_text(source)
    for name in ('home','config/hics','data/native','user-data/applications','cache','state'):(base/name).mkdir(parents=True)
    (base/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
    (base/'config/hics/dock.json').write_text('{"enabled":true,"position":"bottom","iconSize":44}')
    (base/'config/hics/shell.json').write_text('{"bar":{"statusIcons":[{"id":"audio","enabled":true}]}}')
    for name in ('hics-bars.so','hics-motion.so','libhics-render-dispatch.so'):shutil.copy2(ROOT/'build'/name,base/'data/native'/name)
    shutil.copy2(ROOT/'build/third_party/phantomat/libspatialoverview.so',base/'data/native/libspatialoverview.so')
    (base/'user-data/applications/org.hics.Context.desktop').write_text('[Desktop Entry]\nType=Application\nName=Context fixture\nExec=kitty\nIcon=utilities-terminal\nStartupWMClass=org.hics.Context\n')
    config=ROOT/'shell/assets/hyprland/config';lua=base/'test.lua'
    lua.write_text('package.path='+json.dumps(str(config/'?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\nhl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\nhl.device({name="wl_pointer",enabled=false})\n'+''.join('dofile('+json.dumps(str(p))+')\n' for p in (config/'hyprland/animations.lua',config/'hyprland/gestures.lua',ROOT/'shell/assets/hyprland/layouts.lua')))
    busconf=base/'bus.conf';busconf.write_text('<busconfig><type>session</type><listen>unix:path='+str(base/'bus')+'</listen><auth>EXTERNAL</auth><policy context="default"><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
    env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'user-data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),HYPRSTACK_DATA_DIR=str(base/'data'),AQ_BACKEND='wayland',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'),PIPEWIRE_REMOTE='hics-interactions-absent',PULSE_SERVER='unix:'+str(base/'absent-pulse'),HICS_NO_ONBOARDING='1',GTK_A11Y='none')
    env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(busconf)],stdout=subprocess.PIPE,text=True);processes.append(bus);env['DBUS_SESSION_BUS_ADDRESS']=bus.stdout.readline().strip()
    with (base/'compositor.log').open('w') as log: compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
    processes.append(compositor)
    instance=wait(lambda:next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None),'No compositor')
    resize_nested_compositor(compositor.pid)
    env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
    def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],text=True,timeout=8).strip()
    assert ctl('plugin','load',str(base/'data/native/hics-motion.so'))=='ok'
    assert ctl('plugin','load',str(base/'data/native/libspatialoverview.so'))=='ok'
    def clients():return json.loads(ctl('-j','clients'))
    def window(process):return next((w for w in clients() if w['pid']==process.pid),None)
    def launch(command,extra=None):
        with (base/('app-'+str(len(processes))+'.log')).open('w') as log:p=subprocess.Popen(command,env=dict(env,**(extra or {})),stdout=log,stderr=subprocess.STDOUT)
        processes.append(p);wait(lambda:window(p),'Client did not map');return p
    # Real external windows, copied plugins and the production drawer root.
    a=launch(['kitty','--class','org.hics.Context','--title','Context A','-o','background=#b02020','-o','confirm_os_window_close=0','sleep','180'])
    b=launch(['kitty','--class','org.hics.ContextB','--title','Context B','-o','background=#2030b0','-o','confirm_os_window_close=0','sleep','180'])
    for p,x,y in ((a,120,180),(b,240,260)):
        ctl('repl','local w=hl.get_window('+json.dumps('address:'+window(p)['address'])+');hl.dispatch(hl.dsp.window.resize({window=w,x=500,y=340,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x='+str(x)+',y='+str(y)+',relative=false}))')
    (shell/'shell.qml').write_text('''//@ pragma AppId org.hics.Shell
import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import qs.components
import qs.services
import qs.modules.drawers as Drawers
import qs.modules.session as Session
ShellRoot {
 id:root
 property bool checkAudio:false
 FrameAnimation {running:root.checkAudio;onTriggered:{const p=ShellState.componentsFor(win.screen).panels;const a=root.box(p.osdWrapper),b=root.box(p.popoutsWrapper);if(a.w>2&&b.h>2&&a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h){console.error("AUDIO_OVERLAP",JSON.stringify(a),JSON.stringify(b));Qt.exit(9);}}}
 Drawers.ContentWindow {id:win;targetScreen:Quickshell.screens[0]}
 Drawers.Exclusions {screen:Quickshell.screens[0];bar:win.bar}
 Session.LogoutBlockersWindow {id:logout;visible:false;blockers:[{name:"Private editor",reason:"Unsaved data"}];onCancelRequested:visible=false}
 Component.onCompleted:{ShellState.shellRoot=root;GlobalConfig.utilities.enabled=false;}
 function find(item,name){if(item.objectName===name)return item;for(const child of item.children??[]){const found=find(child,name);if(found)return found;}return null;}
 function audioIcon(item){if(item.name==="audio"&&item.visible)return item;for(const child of item.children??[]){const found=audioIcon(child);if(found)return found;}return null;}
 function actions(item,result){if(item.objectName?.startsWith("windowAction_"))result.push({name:item.objectName,box:box(item)});for(const child of item.children??[])actions(child,result);}
 function box(item){if(!item)return null;const p=item.mapToItem(win.contentItem,0,0);return {x:p.x,y:p.y,w:item.width,h:item.height,visible:item.visible};}
 IpcHandler {
  target:"interactions"
  function command(value:string):void {
   const panels=ShellState.componentsFor(win.screen).panels;
   if(value==="launcher")ShellState.setLauncher(win.screenState,true);
   if(value==="grid")find(panels.dock,"dockAppsButton").activate(Qt.LeftButton);
   if(value==="close"){root.checkAudio=false;ShellState.closeDrawers();}
   if(value==="dashboard")win.screenState.dashboard=true;
   if(value==="logout")logout.visible=true;
   if(value==="session")win.screenState.session=true;
   if(value==="audio"){root.checkAudio=true;panels.popouts.currentName="audio";panels.popouts.currentCenter=win.width-100;panels.popouts.hasCurrent=true;panels.osd.show();}
  }
  function state():string {
   const p=ShellState.componentsFor(win.screen).panels,m=find(win.contentItem,"windowMenu");let menuActions=[];root.actions(m,menuActions);
   return JSON.stringify({overview:Overview.active,nativeOverview:Overview.nativeStarted,dashboard:win.screenState.dashboard,session:win.screenState.session,logout:logout.visible,
    launcher:win.screenState.launcher,listOpen:p.dock.listOpen,list:box(p.dock.listSurface),normalLauncher:p.launcher.visible,draggingFiles:p.dock.draggingFiles,fileDragTarget:p.dock.fileDragTarget,
    audioIcon:box(root.audioIcon(win.bar)),osd:box(p.osdWrapper),popout:box(p.popoutsWrapper),menu:m.visible,menuBox:box(find(m,"titlebarContextMenu")),
    actions:menuActions,buttons:p.dock.motionButtons.filter(b=>b.objectName==="dockTaskButton").map(b=>({key:b.group.key,box:box(b)}))});
  }
 }
}''')
    qsenv=dict(env,QT_QPA_PLATFORM='wayland',**snapshot_qml_runtime(ROOT,base))
    with (base/'shell.log').open('w') as log:qs=subprocess.Popen([QS,'-p',str(shell)],env=qsenv,stdout=log,stderr=subprocess.STDOUT)
    processes.append(qs)
    def ipc(method,*args):
        r=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','interactions',method,*args],env=qsenv,capture_output=True,text=True,timeout=8)
        assert r.returncode==0,r.stderr+(base/'shell.log').read_text()[-2500:]
        return r.stdout.strip()
    wait(lambda:qs.poll() is not None or 'shell.qml' in (base/'shell.log').read_text(),'No shell startup')
    time.sleep(.8)
    assert qs.poll() is None,(base/'shell.log').read_text()
    def state():return json.loads(ipc('state'))
    def command(value):ipc('command',value)
    for protocol,source,name,packages in [('wlr-virtual-pointer-unstable-v1.xml','virtual-pointer.c','pointer',['wayland-client']),('virtual-keyboard.xml','virtual-keyboard-stream.c','keyboard',['wayland-client','xkbcommon'])]:
        stem='virtual-pointer' if name=='pointer' else 'virtual-keyboard'
        for flag,suffix in [('client-header','.h'),('private-code','.c')]:subprocess.run(['wayland-scanner',flag,str(ROOT/'tests/fixtures'/protocol),str(base/(stem+suffix))],check=True)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',*packages],text=True))
        subprocess.run(['cc',str(ROOT/'tests/fixtures'/source),str(base/(stem+'.c')),'-I',str(base),*flags,'-o',str(base/name)],check=True)
    def input_process(name):
        p=subprocess.Popen([str(base/name)],env=dict(env,HYPRSTACK_POINTER_WIDTH='1280',HYPRSTACK_POINTER_HEIGHT='900'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1);processes.append(p);assert p.stdout.readline().strip()=='ready';return p
    pointer=input_process('pointer');keyboard=input_process('keyboard')
    def send(p,line):p.stdin.write(line+'\n');p.stdin.flush();assert p.stdout.readline().strip()=='ok'
    def move(x,y):send(pointer,f'move {int(x)} {int(y)}')
    def click(x,y,button=272):move(x,y);send(pointer,f'button {button} 1');send(pointer,f'button {button} 0')
    def escape():send(keyboard,'key 1 1');send(keyboard,'key 1 0')
    command('launcher');s=wait(lambda:(s:=state()) and s['listOpen'] and s['list']['h']>100 and s,'Panel did not open dock list');width=s['list']['w']
    assert not s['normalLauncher'],'Duplicate launcher is visible'
    escape();wait(lambda:not state()['launcher'],'Launcher Escape failed')
    command('grid');wait(lambda:state()['listOpen'],'Dock grid did not open');assert abs(state()['list']['w']-width)<2
    click(20,200);wait(lambda:not state()['listOpen'],'Outside list click failed')
    print('PASS: panel/dock launcher share width, origin, Escape and outside dismissal',flush=True)
    command('dashboard');wait(lambda:state()['dashboard'],'Dashboard did not open');time.sleep(.6);escape();wait(lambda:not state()['dashboard'],'Dashboard Escape failed')
    command('session');wait(lambda:state()['session'],'Session did not open');click(30,300);wait(lambda:not state()['session'],'Session outside click failed')
    def logout_ready():
        return any(layer['namespace']=='hics-logout-confirmation' for monitor in json.loads(ctl('-j','layers')).values() for layers in monitor['levels'].values() for layer in layers)
    command('logout');wait(logout_ready,'Logout did not map');click(30,300);wait(lambda:not state()['logout'],'Logout outside click failed')
    command('logout');wait(logout_ready,'Logout did not remap');escape();wait(lambda:not state()['logout'],'Logout Escape failed')
    print('PASS: dashboard Escape; overlay session/logout cancel on outside click and Escape',flush=True)
    icon=state()['audioIcon'];assert icon,'No audio status icon';move(icon['x']+icon['w']/2,icon['y']+icon['h']/2);wait(lambda:state()['popout']['h']>20,'Audio hover did not open popout');command('audio');time.sleep(.7);s=state();o,p=s['osd'],s['popout'];assert o['w']>10 and o['h']>10 and p['h']>20,(o,p)
    assert not(o['x']<p['x']+p['w'] and p['x']<o['x']+o['w'] and o['y']<p['y']+p['h'] and p['y']<o['y']+o['h']),(o,p)
    subprocess.run(['grim',str(base/'audio.png')],env=env,check=True,capture_output=True)
    command('close');print('PASS: audio popout and external OSD remain separate adjacent surfaces',flush=True)
    def settled(process):
        w=window(process)
        return json.loads(ctl('repl','return hl.plugin.hyprbars.animate_window('+json.dumps(w['address'])+','+json.dumps(w['stableId'])+',"geometry-state")'))['settled']
    def menu():
        command('close');wait(lambda:settled(a),'Geometry did not settle');w=window(a);click(w['at'][0]+100,w['at'][1]-16,273);return wait(lambda:(s:=state()) and s['menu'] and s,'Native right click did not open menu')
    s=menu();subprocess.run(['grim',str(base/'window-menu.png')],env=env,check=True,capture_output=True)
    escape();wait(lambda:not state()['menu'],'Window menu Escape failed')
    menu();click(20,600);wait(lambda:not state()['menu'],'Window menu outside click failed')
    print('PASS: native titlebar context menu opens above windows and dismisses',flush=True)
    def action(operation):
        s=menu();entry=next(row for row in s['actions'] if row['name']=='windowAction_'+operation);box=entry['box']
        click(box['x']+box['w']/2,box['y']+box['h']/2)
        wait(lambda:not state()['menu'],'Menu action did not dismiss')
    def focus(process):ctl('repl','hl.dispatch(hl.dsp.focus({window=hl.get_window('+json.dumps('address:'+window(process)['address'])+')}))')
    def active():return json.loads(ctl('-j','activewindow')).get('pid')
    original=window(a)['size'];action('size-up');wait(lambda:window(a)['size'][0]>original[0]+20,'Window size did not increase')
    action('size-reset');wait(lambda:abs(window(a)['size'][0]-original[0])<3,'Window size did not restore')
    action('center');wait(lambda:abs(window(a)['at'][0]-(1280-window(a)['size'][0])/2)<3,'Center did not apply')
    action('maximize');wait(lambda:window(a)['size'][0]>=1270,'Maximize did not apply')
    action('maximize');wait(lambda:window(a)['size'][0]<1270,'Restore did not apply')
    action('keep-above');focus(b)
    wb=window(b);click(wb['at'][0]+30,wb['at'][1]-16)
    wait(lambda:active()==b.pid,'Background window titlebar click did not focus it')
    wa,wb=window(a),window(b);px=max(wa['at'][0],wb['at'][0])+30;py=max(wa['at'][1],wb['at'][1])+30
    click(px,py);wait(lambda:active()==a.pid,'Keep above did not preserve input Z order')
    action('keep-above')
    action('fullscreen');wait(lambda:window(a)['fullscreen']==2,'Fullscreen did not apply')
    ctl('repl','hyprstack_layouts.action("fullscreen",'+json.dumps(window(a)['address'])+','+json.dumps(window(a)['stableId'])+')')
    wait(lambda:window(a)['fullscreen']==0,'Fullscreen did not restore')
    action('minimize');wait(lambda:window(a)['workspace']['name'].startswith('special:'),'Minimize did not apply')
    ctl('repl','hyprstack_layouts.action("restore",'+json.dumps(window(a)['address'])+','+json.dumps(window(a)['stableId'])+')')
    wait(lambda:not window(a)['workspace']['name'].startswith('special:'),'Restore did not apply')
    print('PASS: context actions resize/reset, center, maximize/restore, keep above, fullscreen and minimize',flush=True)
    # A real Qt data-device file drag, not a synthetic DropArea signal.
    file=base/'example.txt';file.write_text('Only a private fixture')
    source=launch(['python3',str(ROOT/'tests/fixtures/canvas-qt-input-app.py')],{'QT_QPA_PLATFORM':'wayland','HICS_TEST_FILE_DRAG':str(file)})
    w=window(source)
    ctl('repl','local w=hl.get_window('+json.dumps('address:'+w['address'])+');hl.dispatch(hl.dsp.window.resize({window=w,x=400,y=240,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=750,y=160,relative=false}))')
    wait(lambda:settled(source) and len(state()['buttons'])>=3,'Drag source did not settle')
    w=window(source);sx,sy=w['at'][0]+80,w['at'][1]+100
    target=next(b for b in state()['buttons'] if b['key']=='org.hics.Context')['box'];tx,ty=target['x']+target['w']/2,target['y']+target['h']/2
    focus(source);move(sx,sy);send(pointer,'button 272 1')
    for step in range(1,16):move(sx+(tx-sx)*step/15,sy+(ty-sy)*step/15);time.sleep(.02)
    assert active()!=a.pid,'File drag activated without its hover delay'
    wait(lambda:state()['draggingFiles'] and state()['fileDragTarget']=='org.hics.Context',lambda:'Real file drag did not enter dock: '+json.dumps(state()),4)
    wait(lambda:active()==a.pid,lambda:'Hovering a dragged file did not reveal the application: '+json.dumps(state()),4)
    send(pointer,'button 272 0')
    wait(lambda:not state()['draggingFiles'],'File drag did not finish')
    focus(source);move(sx,sy);send(pointer,'button 272 1')
    for step in range(1,16):move(sx+(tx-sx)*step/15,sy+(ty-sy)*step/15);time.sleep(.02)
    wait(lambda:state()['fileDragTarget']=='org.hics.Context','Second file drag did not enter dock')
    move(100,720);send(pointer,'button 272 0');time.sleep(1.2)
    assert active()!=a.pid,'Leaving dock did not cancel pending file activation'
    source.terminate();source.wait(timeout=5)
    print('PASS: real file drag reveals the running application after its delay',flush=True)
    action('overview');wait(lambda:state()['overview'] and state()['nativeOverview'],'Show all windows did not open native overview');escape();wait(lambda:not state()['overview'],'Overview Escape failed')
    print('PASS: context menu opens native overview; leaving a file drag cancels activation',flush=True)
    action('keep-above');action('close');wait(lambda:not window(a),'Context close did not close selected window');assert window(b),'Context close affected another application'
    assert not ctl('configerrors'),ctl('configerrors')
    errors=(base/'shell.log').read_text()
    assert not any(s in errors for s in ('TypeError:','ReferenceError:','Cannot assign to non-existent','Binding loop')),errors[-6000:]
    print('PASS: no QML construction/runtime errors',flush=True)
finally:
    for p in reversed(processes):
        if p.poll() is None:
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
