#!/usr/bin/env python3
"""Native stacking transitions preserve geometry, reach icons and reverse safely."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from integration_support import require_wayland_session
require_wayland_session()
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-dock-motion-') as directory:
    base=Path(directory);processes=[]
    (base/'config/hics').mkdir(parents=True);(base/'data/native').mkdir(parents=True)
    (base/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
    dock=base/'config/hics/dock.json';dock.write_text('{"enabled":true,"windowAnimations":true,"animationDuration":700}')
    for name in ('libhics-render-dispatch.so','hics-bars.so','hics-motion.so'):
        native=Path(os.environ.get('HICS_TEST_NATIVE_DIR',str(ROOT/'build')))
        shutil.copy2(native/name,base/'data/native'/name)
    config=ROOT/'shell/assets/hyprland/config'
    lua=base/'test.lua'
    lua.write_text('package.path='+json.dumps(str(config/'?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\ndofile('+json.dumps(str(config/'hyprland/animations.lua'))+')\nhl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\ndofile('+json.dumps(str(config/'hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
    env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),HYPRSTACK_DATA_DIR=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),XDG_DATA_HOME=str(base/'user-data'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    try:
        log=(base/'compositor.log').open('w')
        compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(compositor)
        for _ in range(80):
            instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
            if instance:break
            time.sleep(.1)
        assert instance,'No nested compositor'
        sig=instance['instance'];time.sleep(.8)
        def ctl(*args):return subprocess.check_output(['hyprctl','-i',sig,*args],text=True,timeout=10).strip()
        assert not ctl('configerrors'),ctl('configerrors')
        assert ctl('plugin','load',str(base/'data/native/hics-motion.so'))=='ok'
        appenv=dict(env,WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=sig)
        background=base/'background.qml'
        background.write_text('import Quickshell\nimport Quickshell.Wayland\nPanelWindow {anchors {top:true;bottom:true;left:true;right:true}color:"#000000";exclusionMode:ExclusionMode.Ignore;WlrLayershell.layer:WlrLayer.Background}')
        bglog=(base/'background.log').open('w')
        processes.append(subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(background)],env=appenv,stdout=bglog,stderr=subprocess.STDOUT))
        time.sleep(.6)
        app=subprocess.Popen(['kitty','--class','org.hics.MotionFixture','-o','background=#d02040','-o','confirm_os_window_close=0','sleep','120'],env=appenv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(app)
        def windows():return [w for w in json.loads(ctl('-j','clients')) if w['class']=='org.hics.MotionFixture']
        for _ in range(60):
            if windows():break
            time.sleep(.1)
        assert windows(),'No application window'
        window=windows()[0];address=window['address'];identity=format(window['stableId'],'x') if isinstance(window.get('stableId'),int) else window.get('stableId')
        # Hyprland's public JSON may expose stableId as a hex string.
        if not identity:identity=ctl('repl','return string.format("%x",hl.get_window("address:'+address+'").stable_id)').strip('"')
        ctl('repl','local w=hl.get_window("address:'+address+'");hl.dispatch(hl.dsp.window.resize({window=w,x=600,y=420,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=180,y=180,relative=false}))')
        time.sleep(.5);before=windows()[0]
        monitor=json.loads(ctl('-j','monitors'))[0]
        target_x=monitor['width']/monitor['scale']-100;target_y=monitor['height']/monitor['scale']-120
        target={'address':address,'id':identity,'x':target_x,'y':target_y,'w':44,'h':44,'barTop':870,'icon':'/usr/share/pixmaps/kitty.png'}
        for source,x in [('bar',50),('dock',target_x)]:
            target['x']=x
            ctl('repl','hyprstack_layouts.set_task_targets("WAYLAND-1",require("utils.json").decode('+json.dumps(json.dumps([target]))+'),'+json.dumps(source)+')')
        def action(op):return ctl('repl','hyprstack_layouts.action('+json.dumps(op)+','+json.dumps(address)+')')
        def state():
            raw=ctl('repl','local s=hl.plugin.hics_motion.animate_window('+json.dumps(address)+','+json.dumps(identity)+',"state");return require("utils.json").encode(s or {})')
            # repl returns a JSON string quoted as a Lua result.
            try:value=json.loads(raw)
            except json.JSONDecodeError:return {}
            return json.loads(value) if isinstance(value,str) else value
        ctl('repl','hyprstack_layouts.theme({surfaceContainerLow="#20e060",primary="#ff00ff"})')
        action('minimize');time.sleep(.15)
        middle=state();assert 0<middle.get('progress',0)<1,middle
        current=windows()[0];assert current['at']==before['at'] and current['size']==before['size'],('Client geometry changed during visual transition',before,current)
        snapshot=base/'middle.png';subprocess.run(['grim',str(snapshot)],env=appenv,capture_output=True,check=True)
        shutil.copy2(snapshot,'/tmp/hics-native-motion-middle.png')
        from PIL import Image
        frame=Image.open(snapshot).convert('RGB')
        green=sum(n for n,(r,g,b) in frame.getcolors(frame.width*frame.height) if g>150 and r<80 and 50<b<140)
        assert green>100,('Native token was not rendered',green,middle)
        time.sleep(.25);landing=state();assert landing.get('x',0)>target_x-250,('Animation missed dock and used bar target',landing)
        image=base/'transition.png';subprocess.run(['grim',str(image)],env=appenv,capture_output=True,check=True)
        from PIL import Image
        shutil.copy2(image,'/tmp/hics-native-motion.png')
        pixels=Image.open(image).convert('RGB')
        box=(max(0,int(landing['x'])),max(0,int(landing['y'])),min(pixels.width,int(landing['x']+landing['width'])),min(pixels.height,int(landing['y']+landing['height'])))
        crop=pixels.crop(box);assert crop.width>5 and crop.height>5
        assert len(crop.getcolors(crop.width*crop.height) or [])>2,('Native morph produced no rendered pixels',landing,state(),box)
        time.sleep(.35);assert windows()[0]['workspace']['name'].startswith('special:'),windows()
        action('restore');time.sleep(.15)
        restored=state();assert 0<restored.get('progress',0)<1,restored
        # The real pink client must be visible while the restore is still
        # travelling, rather than a blank token until the final 70 ms.
        time.sleep(.13)
        reveal=state();assert 0<reveal.get('progress',0)<.85,reveal
        snapshot=base/'restore.png';subprocess.run(['grim',str(snapshot)],env=appenv,capture_output=True,check=True)
        frame=Image.open(snapshot).convert('RGB')
        pink=sum(n for n,(r,g,b) in frame.getcolors(frame.width*frame.height) if r>130 and g<90 and b<130)
        assert pink>1000,('Restoring client content appeared too late',pink,reveal)
        assert reveal.get('paintCount',0)>=4,('Animation did not keep rendering frames',reveal)
        time.sleep(.65);after=windows()[0];assert after['at']==before['at'] and after['size']==before['size'],(before,after)
        print('PASS: minimize/restore uses dock priority, renders the morph and preserves real client geometry',flush=True)
        action('minimize');time.sleep(.12);interrupted=state();action('restore');time.sleep(.04);reversed_state=state()
        assert reversed_state.get('width',0)<before['size'][0],(interrupted,reversed_state)
        time.sleep(.8);assert not windows()[0]['workspace']['name'].startswith('special:')
        print('PASS: mid-flight restore reverses without hiding the application afterwards',flush=True)
        dock.write_text('{"enabled":true,"windowAnimations":false}')
        action('minimize');time.sleep(.04);assert not state(),'Disabled motion still installed a transformer'
        time.sleep(.3);action('restore');time.sleep(.1);assert not state()
        print('PASS: disabling window animations makes minimize/restore immediate',flush=True)
        dock.write_text('{"enabled":true,"windowAnimations":true}')
        (base/'config/hics/shell.json').write_text('{"appearance":{"reducedMotion":true}}')
        action('minimize');time.sleep(.04);assert not state()
        assert windows()[0]['workspace']['name'].startswith('special:')
        action('restore');time.sleep(.04);assert not state()
        print('PASS: Reduce motion disables native travel and minimizes immediately',flush=True)
        # Exercise the production dock, its real target publisher and its icon
        # impulse against the same native stacking window with actual clicks.
        (base/'config/hics/shell.json').write_text('{"appearance":{"reducedMotion":false}}')
        entries=base/'user-data/applications';entries.mkdir(parents=True)
        (entries/'org.hics.MotionFixture.desktop').write_text('[Desktop Entry]\nType=Application\nName=Motion fixture\nExec=kitty\nIcon=/usr/share/pixmaps/kitty.png\nStartupWMClass=org.hics.MotionFixture\n')
        ui=base/'ui';shutil.copytree(ROOT/'shell',ui,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
        status=base/'dock.json'
        (ui/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.components
import qs.modules.dock as Dock
ShellRoot {
 function task(item){if(item.objectName==="dockTaskButton")return item;for(const child of item.children??[]){const found=task(child);if(found)return found;}return null;}
 ScreenState {id:state;modelData:Quickshell.screens[0]}
 PanelWindow {
  id:win;anchors {top:true;bottom:true;left:true;right:true}
  color:"transparent";exclusionMode:ExclusionMode.Ignore;WlrLayershell.layer:WlrLayer.Top;WlrLayershell.keyboardFocus:WlrKeyboardFocus.None
  mask:Region{x:dock.x+Math.min(0,dock.membraneBounds.x);y:dock.y+Math.min(0,dock.membraneBounds.y);width:Math.max(dock.width,dock.membraneBounds.x+dock.membraneBounds.width)-Math.min(0,dock.membraneBounds.x);height:Math.max(dock.height,dock.membraneBounds.y+dock.membraneBounds.height)-Math.min(0,dock.membraneBounds.y)}
  Dock.DockContent {id:dock;screen:win.screen;screenState:state;panelVisible:true;width:implicitWidth;height:implicitHeight;anchors.bottom:parent.bottom;anchors.bottomMargin:20;anchors.horizontalCenter:parent.horizontalCenter}
 }
 FileView{id:output;path:STATUS;printErrors:false}
 Timer{interval:20;repeat:true;running:true;onTriggered:{const t=task(dock);if(t){const p=t.mapToItem(win.contentItem,t.width/2,t.height/2);const v=t.visual.mapToItem(win.contentItem,t.width/2,t.height/2);output.setText(JSON.stringify({x:p.x,y:p.y,vx:v.x,vy:v.y,scale:t.impulseScale,minimized:t.minimizedCount,icon:t.entry?.animationIcon()??""}));}}}
}'''.replace('STATUS',json.dumps(str(status))))
        qmlpath='/usr/share/hics/qml' if os.environ.get('HICS_TEST_INSTALLED_RUNTIME')=='1' else str(ROOT/'build/qml')
        qmlenv=dict(appenv,QML_IMPORT_PATH=qmlpath,QML2_IMPORT_PATH=qmlpath)
        if os.environ.get('HICS_TEST_INSTALLED_RUNTIME')=='1':
            qmlenv['LD_LIBRARY_PATH']='/usr/share/hics/qs/lib'
        uilog=(base/'ui.log').open('w');processes.append(subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(ui)],env=qmlenv,stdout=uilog,stderr=subprocess.STDOUT))
        def ui_state():
            try:return json.loads(status.read_text())
            except (FileNotFoundError,json.JSONDecodeError):return {}
        for _ in range(80):
            if ui_state().get('icon'):break
            time.sleep(.1)
        assert ui_state().get('icon'),(ui_state(),(base/'ui.log').read_text()[-2500:])
        assert Path(ui_state()['icon']).is_file(),'Native animation icon was not exported'
        import shlex
        fixtures=ROOT/'tests/fixtures'
        if os.environ.get('HICS_TEST_POINTER_BINARY'):
            shutil.copy2(os.environ['HICS_TEST_POINTER_BINARY'],base/'pointer')
        else:
            for flag,name in [('client-header','virtual-pointer.h'),('private-code','virtual-pointer-protocol.c')]:subprocess.run(['wayland-scanner',flag,str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/name)],check=True)
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
            subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(base/'virtual-pointer-protocol.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
        monitor=json.loads(ctl('-j','monitors'))[0]
        pointer=subprocess.Popen([str(base/'pointer')],env=dict(appenv,HYPRSTACK_POINTER_WIDTH=str(monitor['width']),HYPRSTACK_POINTER_HEIGHT=str(monitor['height'])),stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1);processes.append(pointer)
        assert pointer.stdout.readline().strip()=='ready'
        def send(op,x,y):
            pointer.stdin.write(f'{op} {round(x)} {round(y)}\n');pointer.stdin.flush();assert pointer.stdout.readline().strip()=='ok';time.sleep(.04)
        # Close a focus-less layer shell press into a real stacking task click.
        action('activate');time.sleep(.3)
        target=ui_state();send('move',target['x'],target['y']);time.sleep(.3)
        target=ui_state();assert target['vy']<target['y']-15,target
        send('move',target['vx'],target['vy']);send('button',272,1);send('button',272,0)
        samples=[]
        for _ in range(50):samples.append(ui_state());time.sleep(.02)
        assert any(s.get('minimized')==1 for s in samples),('Dock click did not minimize',samples)
        if os.environ.get('HICS_TEST_SKIP_IMPULSE') != '1':
            assert min(s.get('scale',1) for s in samples)<.94 and max(s.get('scale',1) for s in samples)>1.03,('No icon squash/rebound',samples)
        assert windows()[0]['workspace']['name'].startswith('special:')
        send('button',272,1);send('button',272,0);time.sleep(.8)
        assert not windows()[0]['workspace']['name'].startswith('special:')
        print('PASS: left click on a raised icon minimizes/restores the real window' +
              (' (icon impulse not measured)' if os.environ.get('HICS_TEST_SKIP_IMPULSE')=='1' else ' and triggers icon absorption'),flush=True)
        # Repeat through the actual dock with an unpinned application on a
        # user-facing special workspace, as used by Spotify's Flatpak entry.
        ctl('repl','hl.dispatch(hl.dsp.focus({workspace="special:music"}));local w=hl.get_window("address:'+address+'");hl.dispatch(hl.dsp.window.move({window=w,workspace="special:music",follow=false}));hl.dispatch(hl.dsp.focus({window=w}))')
        for _ in range(60):
            if windows()[0]['workspace']['name']=='special:music' and ui_state().get('icon'):break
            time.sleep(.1)
        assert windows()[0]['workspace']['name']=='special:music',windows()
        target=ui_state();send('move',target['x'],target['y'])
        for _ in range(40):
            target=ui_state()
            if target.get('vy',0)<target.get('y',0)-10:break
            time.sleep(.05)
        assert target.get('vy',0)<target.get('y',0)-10,('Dock did not receive pointer',target)
        send('move',target['vx'],target['vy']);send('button',272,1);send('button',272,0)
        time.sleep(.15);motion=state()
        assert motion and motion.get('x',-1000)>target['x']-250,('Special window used wrong animation target or did not minimize',motion,target)
        time.sleep(.8)
        assert windows()[0]['workspace']['name'].startswith('special:hyprstack-minimized-'),windows()
        send('button',272,1);send('button',272,0);time.sleep(.8)
        assert windows()[0]['workspace']['name']=='special:music',windows()
        print('PASS: special-workspace window minimizes to real dock and restores on click',flush=True)
        ctl('repl','local w=hl.get_window("address:'+address+'");hl.dispatch(hl.dsp.window.move({window=w,workspace="1",follow=false}));hl.dispatch(hl.dsp.focus({window=w}))')
        output=(base/'ui.log').read_text();assert not any(e in output for e in ('TypeError:','ReferenceError:','Binding loop')),output[-3000:]
        pointer.stdin.close();pointer.wait(timeout=3)
        ctl('reload');time.sleep(.5)
        assert not ctl('configerrors'),ctl('configerrors')
        target=ui_state();action('minimize');time.sleep(.3);reloaded=state()
        assert abs(reloaded['x']+reloaded['width']/2-target['x'])<80 and abs(reloaded['y']+reloaded['height']/2-target['y'])<80,('Dock target was lost on reload',target,reloaded)
        action('restore');time.sleep(.6)
        print('PASS: dock targets are republished after compositor config reload',flush=True)
        action('minimize');time.sleep(.05);app.terminate();app.wait(timeout=5);time.sleep(.7)
        assert not ctl('configerrors')
        print('PASS: closing an animating window cleans up its transformer and callbacks',flush=True)
        ctl('plugin','unload',str(base/'data/native/hics-motion.so'))
    except Exception:
        print((base/'compositor.log').read_text(errors='replace')[-5000:])
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
