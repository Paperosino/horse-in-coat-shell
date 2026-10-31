#!/usr/bin/env python3
"""Real pointer events against the production drawer, mask and dock delegates."""
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
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-dock-pointer-') as directory:
    base = Path(directory)
    shell = base/'shell'
    shutil.copytree(ROOT/'shell', shell, ignore=shutil.ignore_patterns('plugin', 'extras', '__pycache__'))
    dock_source=shell/'modules/dock/DockContent.qml'
    probe=dock_source.read_text().replace('id: root','id: root\n    property int testCreated: 0\n    property int testClicks: 0\n    property string testKey: ""\n    property int testPresses: 0\n    property int testCancels: 0\n    property bool testDropHover: false',1)
    probe=probe.replace('!root.draggedKey ? 1 : 0','!root.draggedKey && !root.testDropHover ? 1 : 0')
    probe=probe.replace('function activate(button: int): void {','function activate(button: int): void { root.testClicks++;root.testKey=task.modelData;',1)
    probe=probe.replace('onPressed: event => { pressPoint','onPressed: event => { root.testPresses++; pressPoint',1)
    probe=probe.replace('onCanceled: root.cancelDrag()','onCanceled: { root.testCancels++; root.cancelDrag(); }',1)
    probe=probe.replace('required property string modelData','required property string modelData\n                        property int testIdentity:0',1)
    probe=probe.replace('Component.onCompleted: Qt.callLater(()=>{previousMinimized=', 'Component.onCompleted: {root.testCreated++;testIdentity=root.testCreated;Qt.callLater(()=>{previousMinimized=',1)
    probe=probe.replace('motionReady=true;})','motionReady=true;});}',1)
    dock_source.write_text(probe)
    (base/'config/hics').mkdir(parents=True)
    (base/'config/hics/dock.json').write_text(json.dumps(dict(enabled=True, position='bottom', iconSize=44)))
    (base/'config/hics/shell.json').write_text(json.dumps({'dashboard':{'enabled':False},'utilities':{'enabled':False}}))
    (base/'config/hics/workspace.json').write_text(json.dumps({'clipboard': {'enabled':False}}))
    entries=base/'data/applications';entries.mkdir(parents=True)
    (entries/'fixture-dock.desktop').write_text('[Desktop Entry]\nType=Application\nName=Fixture dock application\nExec=kitty\nIcon=utilities-terminal\nStartupWMClass=org.hics.DockPointerFixture\n')
    state = base/'pointer-state.json'
    control = base/'control.txt';control.write_text('')
    badge_flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus'],text=True))
    subprocess.run(['c++','-std=c++20','-fPIC',str(ROOT/'tests/fixtures/badge-emitter.cpp'),*badge_flags,'-o',str(base/'badge-emitter')],check=True)
    (shell/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import qs.services
import qs.modules.drawers as Drawers
ShellRoot {
 id:root
 Drawers.ContentWindow {id:win;targetScreen:Quickshell.screens[0]}
 Component.onCompleted:{ShellState.shellRoot=root;GlobalConfig.dashboard.enabled=false;GlobalConfig.utilities.enabled=false;}
 function find(item,name,result) {
  if(item.objectName===name && item.visible)result.push(item);
  for(const child of item.children??[])find(child,name,result);
 }
 function visualInfo(button) {
  const badge=button.visual.children.find(c=>c.objectName==="dockNotificationBadge");
  const label=badge?.children.find(c=>c.objectName==="dockBadgeLabel");
  const icon=button.visual.children.find(c=>c.objectName==="dockApplicationIcon");
  return {badgeHeight:badge?.height??0,badgePoints:label?.font.pointSize??0,rasterExtent:icon?.rasterExtent??0};
 }
 function box(item) {const p=item.mapToItem(win.contentItem,0,0);return {x:p.x,y:p.y,w:item.width,h:item.height,text:item.text??""};}
 FileView {id:status;path:STATE;printErrors:false}
 FileView {path:CONTROL;watchChanges:true;printErrors:false;onFileChanged:reload();onLoaded:{
  if(text()==="badges")badgeEmitter.running=true;
  if(text()==="badge-history")badgeNotification.running=true;
  if(text()==="badge-read")Notifs.markAllRead();
  if(text().startsWith("clipboard"))win.screenState.clipboard=true;
  const dock=ShellState.componentsFor(win.screen)?.panels?.dock;
  if(dock && text()==="cold")dock.testDropHover=true;
  if(dock && text()==="warm")dock.testDropHover=false;
 }}
 Process {id:badgeEmitter;command:[BADGE_EMITTER]}
 Process {id:badgeNotification;command:["notify-send","-a","Fixture dock application","-h","string:desktop-entry:fixture-dock","Badge integration fixture"]}
 Timer {interval:16;running:true;repeat:true;onTriggered:{
  const dock=ShellState.componentsFor(win.screen)?.panels?.dock;
  if(!dock)return;
  let buttons=[],appsButtons=[],titles=[],clocks=[],captures=[];root.find(dock,"dockAppsButton",appsButtons);root.find(dock.previewSurface,"dockWindowCapture",captures);root.find(win.contentItem,"taskbarClock",clocks);root.find(dock,"dockTaskButton",buttons);root.find(dock,"dockWindowTitle",titles);
  status.setText(JSON.stringify({screenSize:{w:win.width,h:win.height},key:dock.testKey,clicks:dock.testClicks,presses:dock.testPresses,cancels:dock.testCancels,dockWidth:dock.width,wavePosition:dock.wavePosition,hoverAmount:dock.hoverAmount,dockBox:root.box(dock),membraneShapes:dock.membraneShapes,membraneBounds:dock.membraneBounds,clipboard:win.screenState.clipboard,clipboardBox:root.box(ShellState.componentsFor(win.screen).panels.clipboard),listOpen:dock.listOpen,open:dock.menuOpen,warm:dock.previewWarm,hover:!!dock.hoveredWindow,preview:dock.previewSurface.visible,
   captureGeometry:captures[0]?root.box(captures[0]):null,hasContent:captures[0]?.hasContent??false,sourceSize:captures[0]?.sourceSize??null,source:!!dock.previewWindow?.wayland,previewReveal:dock.previewSurface.reveal,previewTitle:dock.previewWindow?.title??"",clocks:clocks.map(c=>root.box(c)),previewBox:root.box(dock.previewSurface),menu:root.box(dock.menuSurface),
   appsButtons:appsButtons.map(b=>Object.assign(root.box(b),{wave:b.wave,scale:b.visualScale,center:b.visual.mapToItem(win.contentItem,b.width/2,b.height/2),visual:root.box(b.visual)})),
   buttons:buttons.map(b=>Object.assign(root.box(b),{visualInfo:root.visualInfo(b),badgeCount:b.badgeCount,key:b.modelData,identity:b.testIdentity,windowCount:b.windows.length,wave:b.wave,scale:b.visualScale,center:b.visual.mapToItem(win.contentItem,b.width/2,b.height/2),visual:root.box(b.visual)})),titles:titles.map(t=>root.box(t))}));
 }}
}'''.replace('STATE',json.dumps(str(state))).replace('CONTROL',json.dumps(str(control))).replace('BADGE_EMITTER',json.dumps(str(base/'badge-emitter'))))
    fixtures = ROOT/'tests/fixtures'
    for flag,name in [('client-header','virtual-pointer.h'),('private-code','virtual-pointer-protocol.c')]:
        subprocess.run(['wayland-scanner',flag,str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/name)],check=True)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
    subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(base/'virtual-pointer-protocol.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
    config=base/'test.lua'
    config.write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
    env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'))
    env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    processes=[];pointer=None
    try:
        compositor_log=(base/'compositor.log').open('w')
        compositor=subprocess.Popen(['Hyprland','--config',str(config)],env=env,stdout=compositor_log,stderr=subprocess.STDOUT);processes.append(compositor)
        instance=None
        for _ in range(80):
            instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
            if instance:break
            time.sleep(.1)
        assert instance,'Nested compositor did not start'
        env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland',QSG_RHI_BACKEND='opengl',HYPRSTACK_POINTER_WIDTH='1280',HYPRSTACK_POINTER_HEIGHT='900')
        env.pop('QT_QUICK_BACKEND',None)
        terminal=subprocess.Popen(['kitty','--class','org.hics.DockPointerFixture','--title','Dock preview fixture','-o','background=#d02040','-o','confirm_os_window_close=0','sleep','600'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(terminal)
        terminal2=subprocess.Popen(['kitty','--class','org.hics.DockPointerFixture','--title','Dock preview fixture B','-o','background=#d02040','-o','confirm_os_window_close=0','sleep','600'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(terminal2)
        time.sleep(1)
        runner=base/'run.py';runner.write_text('import os,sys\nos.environ["DBUS_SYSTEM_BUS_ADDRESS"]=os.environ["DBUS_SESSION_BUS_ADDRESS"]\nos.execvp(sys.argv[1],sys.argv[1:])\n')
        shell_log=(base/'shell.log').open('w')
        shell_process=subprocess.Popen(['dbus-run-session','--','python3',str(runner),os.environ.get('HICS_DOCK_TEST_QS','/usr/share/hics/qs/bin/hics-qs'),'-p',str(shell)],env=env,stdout=shell_log,stderr=subprocess.STDOUT);processes.append(shell_process)
        def read():
            try:return json.loads(state.read_text())
            except (FileNotFoundError,json.JSONDecodeError):return {}
        def wait_for(check,timeout=8):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                value=read()
                if check(value):return value
                if shell_process.poll() is not None:raise AssertionError((base/'shell.log').read_text()[-6000:])
                time.sleep(.1)
            raise AssertionError(('Pointer condition timed out',read(),(base/'shell.log').read_text()[-3000:]))
        def pinned_lifecycle():
            pinned=next(button for button in read()['buttons'] if button['key']=='fixture-dock')
            (base/'config/hics/taskbar.json').write_text(json.dumps({'pinned':['fixture-dock'],'order':[]}))
            time.sleep(.3)
            terminal.kill();terminal2.kill();terminal.wait();terminal2.wait()
            print('Lifecycle clients after kill:',[(w.get('class'),w.get('pid')) for w in json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'clients','-j']))],flush=True)
            closed=wait_for(lambda s:any(b['key']=='fixture-dock' and b['windowCount']==0 for b in s.get('buttons',[])))
            icon=next(b for b in closed['buttons'] if b['key']=='fixture-dock')
            assert icon['identity']==pinned['identity'],'Closing an app replaced its pinned dock delegate'
            restarted=subprocess.Popen(['kitty','--class','org.hics.DockPointerFixture','-o','confirm_os_window_close=0','sleep','60'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(restarted)
            reopened=wait_for(lambda s:any(b['key']=='fixture-dock' and b['windowCount']==1 for b in s.get('buttons',[])))
            assert next(b for b in reopened['buttons'] if b['key']=='fixture-dock')['identity']==pinned['identity'],'Reopening an app replaced its pinned dock delegate'
            print('PASS: pinned app keeps one dock delegate through close and reopen',flush=True)
        wait_for(lambda s:len(s.get('buttons',[]))==1)
        # Flatpak music players commonly live in a special workspace. Their
        # unpinned running windows must remain visible and grouped in the dock.
        for process in (terminal,terminal2):
            windows=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'clients','-j']))
            window=next(w for w in windows if w['pid']==process.pid)
            script='local w=hl.get_window('+json.dumps('address:'+window['address'])+');hl.dispatch(hl.dsp.window.move({window=w,workspace="special:music",follow=false}))'
            subprocess.run(['hyprctl','-i',instance['instance'],'eval',script],check=True,capture_output=True)
        wait_for(lambda s:any(b.get('key')=='fixture-dock' and b.get('windowCount')==2 for b in s.get('buttons',[])))
        for process in (terminal,terminal2):
            windows=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'clients','-j']))
            window=next(w for w in windows if w['pid']==process.pid)
            assert window['workspace']['name']=='special:music',window
            script='local w=hl.get_window('+json.dumps('address:'+window['address'])+');hl.dispatch(hl.dsp.window.move({window=w,workspace="1",follow=false}))'
            subprocess.run(['hyprctl','-i',instance['instance'],'eval',script],check=True,capture_output=True)
        wait_for(lambda s:any(b.get('key')=='fixture-dock' and b.get('windowCount')==2 for b in s.get('buttons',[])))
        print('PASS: unpinned special-workspace windows remain grouped in dock',flush=True)
        control.write_text('badge-history')
        wait_for(lambda s:any(b.get('badgeCount')==1 for b in s.get('buttons',[])))
        control.write_text('badges')
        wait_for(lambda s:any(b.get('badgeCount')==12 for b in s.get('buttons',[])))
        wait_for(lambda s:any(b.get('badgeCount')==120 for b in s.get('buttons',[])))
        subprocess.run(['grim',str(Path('/tmp/hics-dock-badges.png'))],env=env,check=True,capture_output=True)
        wait_for(lambda s:any(b.get('badgeCount')==0 for b in s.get('buttons',[])))
        wait_for(lambda s:any(b.get('badgeCount')==1 for b in s.get('buttons',[])))
        control.write_text('badge-read')
        wait_for(lambda s:all(b.get('badgeCount')==0 for b in s.get('buttons',[])))
        print('PASS: application counts override history, hide explicitly, and clear on sender exit; reading history clears fallback',flush=True)
        if os.environ.get('HICS_DOCK_LIFECYCLE_ONLY'):
            pinned_lifecycle();raise SystemExit(0)
        measured=[]
        for size in (32,44,64):
            prefs=json.loads((base/'config/hics/dock.json').read_text());prefs['iconSize']=size
            (base/'config/hics/dock.json').write_text(json.dumps(prefs))
            value=wait_for(lambda s:bool(s.get('buttons')) and abs(s['buttons'][0]['w']-size)<.1)
            measured.append(value['buttons'][0]['visualInfo'])
        assert abs(measured[2]['badgeHeight']/measured[0]['badgeHeight']-2)<.01,measured
        assert abs(measured[2]['badgePoints']/measured[0]['badgePoints']-2)<.01,measured
        prefs['iconSize']=44;(base/'config/hics/dock.json').write_text(json.dumps(prefs))
        wait_for(lambda s:abs(s['buttons'][0]['w']-44)<.1)
        print('PASS: badge geometry and fractional text scale with dock icon size',flush=True)
        time.sleep(1.5)
        snapshot=read()
        pointer_env=dict(env,HYPRSTACK_POINTER_WIDTH=str(snapshot['screenSize']['w']),HYPRSTACK_POINTER_HEIGHT=str(snapshot['screenSize']['h']))
        pointer=subprocess.Popen([str(base/'pointer')],env=pointer_env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        assert pointer.stdout.readline().strip()=='ready'
        def send(op,x,y):
            pointer.stdin.write(f'{op} {round(x)} {round(y)}\n');pointer.stdin.flush();assert pointer.stdout.readline().strip()=='ok';time.sleep(.1)
        def click(x,y,button=272):send('move',x,y);send('button',button,1);send('button',button,0)
        initial=read();button=initial['buttons'][0];base_width=initial['dockWidth']
        send('move',button['x']+button['w']/2,button['y']+button['h']/2)
        early=read()
        assert early["hoverAmount"]>.15,("Hover response delayed beyond 100 ms",early)
        assert early["buttons"][0]["wave"]>.1,("Icon response delayed beyond 100 ms",early)
        time.sleep(.55)
        raised=read()
        assert raised['hoverAmount']>.8,('Dock hover field never activated',raised)
        assert raised['buttons'][0]['visual']['y'] < raised['buttons'][0]['y']-15,('Icon did not lift',raised)
        assert raised['buttons'][0]['visualInfo']['rasterExtent']==button['visualInfo']['rasterExtent'],'Hover reloaded the icon texture'
        assert abs(raised['dockWidth']-base_width)<1,'Hover changed dock width'
        def assert_membrane(snapshot):
            for button in snapshot['buttons']+snapshot.get('appsButtons',[]):
                if button['wave']<.03:continue
                cx=button['center']['x']-snapshot['dockBox']['x']
                cy=button['center']['y']-snapshot['dockBox']['y']
                hw=button['w']*button['scale']/2
                hh=button['h']*button['scale']/2
                assert any(s['x']<=cx-hw+.1 and s['y']<=cy-hh+.1 and s['x']+s['w']>=cx+hw-.1 and s['y']+s['h']>=cy+hh-.1 for s in snapshot['membraneShapes']),('Animated icon escaped membrane',snapshot)
        assert_membrane(early)
        assert_membrane(raised)
        # Move off the icon centre: the lobe must remain centred on the icon,
        # including the spring's return after the pointer has already left.
        send('move',button['x']+button['w']*.8,button['y']+button['h']/2)
        assert_membrane(read())
        image=base/'membrane.png';subprocess.run(['grim',str(image)],env=env,check=True,capture_output=True)
        shutil.copy2(image,'/tmp/hics-dock-membrane.png')
        send('move',100,300);assert_membrane(read());time.sleep(.8)
        assert read()['hoverAmount']<.02,'Dock membrane did not settle after pointer exit'
        print('PASS: continuous hover raises the icon and membrane without changing dock width',flush=True)
        for attempt in range(2):
            control.write_text('clipboard'+str(attempt))
            snapshot=wait_for(lambda s:s.get('clipboard'))
            time.sleep(.7)
            box=read()['clipboardBox']
            click(box['x']+20,box['y']+20)
            assert read()['clipboard'],'Click inside clipboard incorrectly dismissed it'
            if attempt == 0:
                click(30,300)
            else:
                clock=read()['clocks'][0]
                click(clock['x']+clock['w']/2,clock['y']+clock['h']/2)
            wait_for(lambda s:not s.get('clipboard'))
        print('PASS: clipboard keeps inside clicks and closes on client and panel outside clicks',flush=True)
        def open_menu():
            button=read()['buttons'][0];click(button['x']+button['w']/2,button['y']+button['h']/2,273)
            wait_for(lambda s:s.get('open') and len(s.get('titles',[]))==2)
            time.sleep(.7)
            return read()
        menu=open_menu();title=menu['titles'][0];send('move',title['x']+30,title['y']+title['h']/2)
        time.sleep(.3);assert not read()['preview'],'Preview appeared before the one-second hover delay'
        snapshot=wait_for(lambda s:s.get('preview') and 0<s.get('previewReveal',0)<1,3)
        print('PASS: preview content and shared blob reveal through intermediate animation states',flush=True)
        assert snapshot['source'],'Preview has no toplevel capture source'
        snapshot=wait_for(lambda s:s.get('hasContent') and s.get('previewReveal',0)>.999,4)
        image=base/'preview.png';subprocess.run(['grim',str(image)],env=env,check=True,capture_output=True)
        from PIL import Image
        box=snapshot['captureGeometry'];crop=Image.open(image).convert('RGB').crop((round(box['x']),round(box['y']),round(box['x']+box['w']),round(box['y']+box['h'])))
        crop=crop.crop((round(crop.width*.15),round(crop.height*.15),round(crop.width*.85),round(crop.height*.85)))
        coloured=sum(count for count,(r,g,b) in crop.getcolors(crop.width*crop.height) if r>130 and g<75 and 30<b<110)
        assert coloured>1000,('Preview does not contain the real window image',coloured,snapshot)
        print('PASS: real hover opens a captured window preview after one second',flush=True)
        title=read()['titles'][1]
        send('move',title['x']+30,title['y']+title['h']/2)
        wait_for(lambda s:s.get('previewTitle')==title['text'],.7)
        print('PASS: moving to another real window title switches the preview immediately',flush=True)
        click(100,300)
        wait_for(lambda s:s.get('open') is False,3)
        print('PASS: clicking the application outside the menu dismisses the dock popup',flush=True)
        open_menu();click(12,12);wait_for(lambda s:s.get('open') is False,3)
        print('PASS: clicking shell chrome outside the menu dismisses the dock popup',flush=True)
        snapshot=open_menu();clock=snapshot['clocks'][0]
        click(clock['x']+clock['w']/2,clock['y']+clock['h']/2)
        wait_for(lambda s:s.get('open') is False,3)
        print('PASS: clicking another panel control dismisses the dock popup',flush=True)
        click(12,300) # Dismiss the clock popout before testing the top dock.
        for side in ('top','left','right','bottom'):
            (base/'config/hics/dock.json').write_text(json.dumps(dict(enabled=True,position=side,iconSize=44)))
            send('move',100,300);time.sleep(1)
            button=read()['buttons'][0]
            send('move',button['x']+button['w']/2,button['y']+button['h']/2);time.sleep(.7)
            current=read();button=current['buttons'][0];visual=button['visual']
            delta=(visual['x']-button['x']) if side in ('left','right') else (visual['y']-button['y'])
            assert_membrane(current)
            assert current['hoverAmount']>.8 and (delta>15 if side in ('left','top') else delta< -15),(side,current)
            # Click the raised half of the actual icon, beyond the old unscaled
            # lift hitbox. Its original dock slot must stay clickable as well.
            cx=button['center']['x'];cy=button['center']['y']
            offset=button['w']*button['scale']*.3
            px=cx+(offset if side=='left' else -offset if side=='right' else 0)
            py=cy+(offset if side=='top' else -offset if side=='bottom' else 0)
            prior=read();click(px,py)
            delivered=read()
            assert delivered['clicks']==prior['clicks']+1,('Left click on visible icon was lost',side,prior,delivered)
            click(px,py,273)
            wait_for(lambda s:s.get('open'),3)
            click(12,180);wait_for(lambda s:not s.get('open'),3)
            button=read()['buttons'][0]
            click(button['x']+button['w']/2,button['y']+button['h']/2,273)
            wait_for(lambda s:s.get('open'),3)
            click(12,180);wait_for(lambda s:not s.get('open'),3)
        print('PASS: all four positions accept clicks on raised icon edges and original dock slots',flush=True)
        for side in ('bottom','top','left','right'):
            for menu_position in ('start','end'):
                (base/'config/hics/dock.json').write_text(json.dumps(dict(enabled=True,position=side,iconSize=44,menuButtonPosition=menu_position)))
                send('move',100,300);time.sleep(1)
                snapshot=wait_for(lambda s:len(s.get('appsButtons',[]))==1)
                button=snapshot['appsButtons'][0]
                send('move',button['x']+button['w']/2,button['y']+button['h']/2);time.sleep(.65)
                current=read();button=current['appsButtons'][0];assert button['wave']>.8,(side,menu_position,current)
                assert_membrane(current)
                visual=button['visual'];delta=(visual['x']-button['x']) if side in ('left','right') else (visual['y']-button['y'])
                assert delta>15 if side in ('left','top') else delta< -15,(side,menu_position,current)
                offset=button['w']*button['scale']*.3
                px=button['center']['x']+(offset if side=='left' else -offset if side=='right' else 0)
                py=button['center']['y']+(offset if side=='top' else -offset if side=='bottom' else 0)
                if side=='top' and menu_position=='end':
                    send('move',px,py);send('button',272,1)
                    control.write_text('cold');wait_for(lambda s:s.get('hoverAmount',1)<.01,3)
                    send('button',272,0)
                    wait_for(lambda s:s.get('listOpen'),3)
                    control.write_text('warm')
                else:click(px,py);wait_for(lambda s:s.get('listOpen'),3)
                click(12,180);wait_for(lambda s:not s.get('listOpen'),3)
        print('PASS: apps button lifts with the membrane and accepts raised-edge clicks at both ends on all four sides',flush=True)
        (base/'config/hics/dock.json').write_text(json.dumps(dict(enabled=True,position='bottom',iconSize=44,spread=120)))
        for i in range(4):
            processes.append(subprocess.Popen(['kitty','--class',f'org.hics.MembraneFixture{i}','-o','confirm_os_window_close=0','sleep','600'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        wait_for(lambda s:len(s.get('buttons',[]))==5)
        time.sleep(.8)
        buttons=read()['buttons'];target=buttons[2]
        send('move',target['x']+target['w']/2,target['y']+target['h']/2)
        time.sleep(.4);many=read();assert_membrane(many)
        assert len(many['membraneShapes'])>=3,('Neighbouring icons have no membrane',many)
        target=many['buttons'][2]
        click(target['center']['x'],target['center']['y'])
        delivered=read()
        assert delivered['clicks']==many['clicks']+1 and delivered['key']==target['key'],('Left click on the middle raised icon missed its application',many,delivered)
        # Sample every quadrant of neighbouring icons. Dispatch must be to
        # the icon under the pointer, not the last overlapping delegate.
        for target_key in [b['key'] for b in many['buttons'][:4]]:
            for fx,fy in ((.2,.2),(.8,.2),(.2,.8),(.8,.8),(.5,.5)):
                target=next(b for b in read()['buttons'] if b['key']==target_key)
                send('move',target['x']+target['w']/2,target['y']+target['h']/2);time.sleep(.25)
                target=next(b for b in read()['buttons'] if b['key']==target_key)
                x=target['center']['x']+(fx-.5)*target['w']*target['scale']
                y=target['center']['y']+(fy-.5)*target['h']*target['scale']
                prior=read();click(x,y);delivered=read()
                assert delivered['clicks']==prior['clicks']+1 and delivered['key']==target_key,('An icon quadrant missed its task',target_key,fx,fy,prior,delivered)
        target=read()['buttons'][2]
        send('move',target['x']+target['w']/2,target['y']+target['h']/2);time.sleep(.4)
        target=read()['buttons'][2];x=target['center']['x'];y=target['center']['y']-target['w']*target['scale']*.3
        send('move',x,y);before=read()['clicks'];send('button',272,1)
        control.write_text('cold');wait_for(lambda s:s.get('hoverAmount',1)<.01,3)
        send('button',272,0)
        assert read()['clicks']==before+1,'An animation changed the hitbox while a task was pressed'
        control.write_text('warm');time.sleep(.3)
        print('PASS: neighbouring icon quadrants and held clicks survive animation changes',flush=True)
        target=buttons[3]
        send('move',target['x']+target['w']/2,target['y']+target['h']/2)
        assert_membrane(read())
        send('move',100,300);assert_membrane(read())
        print('PASS: the shared membrane contains neighbouring icons during pointer travel and spring return',flush=True)
        pinned_lifecycle()

        (base/'config/hics/dock.json').write_text(json.dumps(dict(enabled=True,position='bottom',iconSize=44,animations=False)))
        time.sleep(.7);current=read();assert all(abs(b['visual']['y']-b['y'])<.5 for b in current['buttons']+current.get('appsButtons',[])),current
        print('PASS: disabling dock animations immediately settles the membrane',flush=True)
        output=(base/'shell.log').read_text()
        assert not any(error in output for error in ('TypeError:', 'ReferenceError:', 'Unable to assign', 'Binding loop')),output[-6000:]
    except Exception:
        for log in base.glob('*.log'):print(log.name,log.read_text(errors='replace')[-6000:])
        raise
    finally:
        if pointer:
            pointer.stdin.close();pointer.wait(timeout=3)
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
