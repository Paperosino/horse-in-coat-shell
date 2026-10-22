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
    (base/'config/hics').mkdir(parents=True)
    (base/'config/hics/dock.json').write_text(json.dumps(dict(enabled=True, position='bottom', iconSize=44)))
    (base/'config/hics/shell.json').write_text(json.dumps({'dashboard':{'enabled':False},'utilities':{'enabled':False}}))
    (base/'config/hics/workspace.json').write_text(json.dumps({'clipboard': {'enabled':False}}))
    state = base/'pointer-state.json'
    control = base/'control.txt';control.write_text('')
    (shell/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import qs.services
import qs.modules.drawers as Drawers
ShellRoot {
 id:root
 Drawers.ContentWindow {id:win;screen:Quickshell.screens[0]}
 Component.onCompleted:{ShellState.shellRoot=root;GlobalConfig.dashboard.enabled=false;GlobalConfig.utilities.enabled=false;}
 function find(item,name,result) {
  if(item.objectName===name && item.visible)result.push(item);
  for(const child of item.children??[])find(child,name,result);
 }
 function box(item) {const p=item.mapToItem(win.contentItem,0,0);return {x:p.x,y:p.y,w:item.width,h:item.height,text:item.text??""};}
 FileView {id:status;path:STATE;printErrors:false}
 FileView {path:CONTROL;watchChanges:true;printErrors:false;onFileChanged:reload();onLoaded:if(text().startsWith("clipboard"))win.screenState.clipboard=true}
 Timer {interval:100;running:true;repeat:true;onTriggered:{
  const dock=ShellState.componentsFor(win.screen)?.panels?.dock;
  if(!dock)return;
  let buttons=[],titles=[],clocks=[],captures=[];root.find(dock.previewSurface,"dockWindowCapture",captures);root.find(win.contentItem,"taskbarClock",clocks);root.find(dock,"dockTaskButton",buttons);root.find(dock,"dockWindowTitle",titles);
  status.setText(JSON.stringify({screenSize:{w:win.width,h:win.height},dockWidth:dock.width,wavePosition:dock.wavePosition,hoverAmount:dock.hoverAmount,membraneCenter:dock.membraneCenter,membraneRadius:dock.membraneRadius,clipboard:win.screenState.clipboard,clipboardBox:root.box(ShellState.componentsFor(win.screen).panels.clipboard),open:dock.menuOpen,warm:dock.previewWarm,hover:!!dock.hoveredWindow,preview:dock.previewSurface.visible,
   captureGeometry:captures[0]?root.box(captures[0]):null,hasContent:captures[0]?.hasContent??false,sourceSize:captures[0]?.sourceSize??null,source:!!dock.previewWindow?.wayland,previewTitle:dock.previewWindow?.title??"",clocks:clocks.map(c=>root.box(c)),previewBox:root.box(dock.previewSurface),menu:root.box(dock.menuSurface),
   buttons:buttons.map(b=>Object.assign(root.box(b),{wave:b.wave,visual:root.box(b.visual)})),titles:titles.map(t=>root.box(t))}));
 }}
}'''.replace('STATE',json.dumps(str(state))).replace('CONTROL',json.dumps(str(control))))
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
        terminal=subprocess.Popen(['kitty','--class','org.hics.DockPointerFixture','--title','Dock preview fixture','-o','background=#d02040','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(terminal)
        terminal2=subprocess.Popen(['kitty','--class','org.hics.DockPointerFixture','--title','Dock preview fixture B','-o','background=#d02040','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(terminal2)
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
        wait_for(lambda s:len(s.get('buttons',[]))==1)
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
        time.sleep(.65)
        raised=read()
        assert raised['hoverAmount']>.8,('Dock hover field never activated',raised)
        assert raised['buttons'][0]['visual']['y'] < raised['buttons'][0]['y']-15,('Icon did not lift',raised)
        assert abs(raised['dockWidth']-base_width)<1,'Hover changed dock width'
        image=base/'membrane.png';subprocess.run(['grim',str(image)],env=env,check=True,capture_output=True)
        shutil.copy2(image,'/tmp/hics-dock-membrane.png')
        send('move',100,300);time.sleep(.8)
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
        snapshot=wait_for(lambda s:s.get('preview'),3)
        assert snapshot['source'],'Preview has no toplevel capture source'
        snapshot=wait_for(lambda s:s.get('hasContent'),4)
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
        for side in ('top','left','right','bottom'):
            (base/'config/hics/dock.json').write_text(json.dumps(dict(enabled=True,position=side,iconSize=44)))
            send('move',100,300);time.sleep(1)
            button=read()['buttons'][0]
            send('move',button['x']+button['w']/2,button['y']+button['h']/2);time.sleep(.7)
            current=read();button=current['buttons'][0];visual=button['visual']
            delta=(visual['x']-button['x']) if side in ('left','right') else (visual['y']-button['y'])
            assert current['hoverAmount']>.8 and (delta>15 if side in ('left','top') else delta< -15),(side,current)
        print('PASS: the liquid wave follows all four dock positions towards the work area',flush=True)
        (base/'config/hics/dock.json').write_text(json.dumps(dict(enabled=True,position='bottom',iconSize=44,animations=False)))
        time.sleep(.7);current=read();assert all(abs(b['visual']['y']-b['y'])<.5 for b in current['buttons']),current
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
