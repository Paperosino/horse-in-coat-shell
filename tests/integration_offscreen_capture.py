#!/usr/bin/env python3
"""Prove pending exports of offscreen Wayland and X11 windows deliver pixels."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-offscreen-capture-') as directory:
    base=Path(directory);processes=[]
    config=base/'test.lua';config.write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
    env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'))
    env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    try:
        log=(base/'compositor.log').open('w')
        compositor=subprocess.Popen(['Hyprland','--config',str(config)],env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(compositor)
        instance=None
        for _ in range(80):
            instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
            if instance:break
            time.sleep(.1)
        assert instance,'No nested compositor'
        sig=instance['instance']
        env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=sig,QT_QPA_PLATFORM='wayland')
        def ctl(*args):return subprocess.check_output(['hyprctl','-i',sig,*args],env=env,text=True,timeout=10).strip()
        def clients():return json.loads(ctl('-j','clients'))
        change=base/'change-colour'
        terminal_script=base/'terminal.py'
        terminal_script.write_text('import pathlib,sys,time\nwhile not pathlib.Path(sys.argv[1]).exists():time.sleep(.1)\nsys.stdout.write("\\033]11;#20d040\\007");sys.stdout.flush()\ntime.sleep(60)\n')
        terminal=subprocess.Popen(['kitty','--class','org.hics.OffscreenCapture','-o','background=#d02040','-o','confirm_os_window_close=0','python3',str(terminal_script),str(change)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(terminal)
        display=ctl('repl','return os.getenv("DISPLAY")').strip('"')
        x11log=(base/'x11.log').open('w')
        x11=subprocess.Popen(['python3',str(ROOT/'tests/fixtures/canvas-scroll-app.py')],env=dict(env,DISPLAY=display,QT_QPA_PLATFORM='xcb',QT_QUICK_BACKEND='software'),stdout=x11log,stderr=subprocess.STDOUT);processes.append(x11)
        for _ in range(60):
            windows=clients()
            wayland=next((c for c in windows if c['class']=='org.hics.OffscreenCapture'),None)
            legacy=next((c for c in windows if c['pid']==x11.pid),None)
            if wayland and legacy:break
            time.sleep(.1)
        assert wayland and legacy,windows
        assert legacy['xwayland'] and not wayland['xwayland']
        for window in (wayland,legacy):
            ctl('repl','hl.dispatch(hl.dsp.window.float({window=hl.get_window("address:'+window['address']+'"),action="enable"}))')
            ctl('repl','hl.dispatch(hl.dsp.window.move({window=hl.get_window("address:'+window['address']+'"),x=5000,y=200,relative=false}))')
        time.sleep(.5)
        assert all(c['at'][0]>4000 for c in clients()),clients()
        status=base/'status.json'
        qml=base/'capture.qml';qml.write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland
ShellRoot {
 id:root
 property var windows:Hyprland.toplevels.values
 property var first:windows.find(w=>w.lastIpcObject.address===FIRST)??null
 property var second:windows.find(w=>w.lastIpcObject.address===SECOND)??null
 FileView {id:status;path:STATUS;printErrors:false}
 PanelWindow {
  id:panel;anchors {bottom:true;right:true}
  implicitWidth:640;implicitHeight:200
  exclusionMode:ExclusionMode.Ignore;WlrLayershell.layer:WlrLayer.Overlay
  WlrLayershell.keyboardFocus:WlrKeyboardFocus.None;color:"#111111"
  mask:Region {width:0;height:0}
  ScreencopyView {id:left;width:300;height:180;x:10;y:10;captureSource:root.first?.wayland??null;live:true}
  ScreencopyView {id:right;width:300;height:180;x:330;y:10;captureSource:root.second?.wayland??null;live:true}
 }
 Timer {interval:100;repeat:true;running:true;onTriggered:status.setText(JSON.stringify({sourceA:!!root.first?.wayland,sourceB:!!root.second?.wayland,a:left.hasContent,b:right.hasContent,w:panel.screen.width,h:panel.screen.height}))}
}'''.replace('FIRST',json.dumps(wayland['address'])).replace('SECOND',json.dumps(legacy['address'])).replace('STATUS',json.dumps(str(status))))
        capturelog=(base/'capture.log').open('w')
        capture=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(qml)],env=env,stdout=capturelog,stderr=subprocess.STDOUT);processes.append(capture)
        def state():
            try:return json.loads(status.read_text())
            except (FileNotFoundError,json.JSONDecodeError):return {}
        def wait_for(condition,timeout=5):
            until=time.monotonic()+timeout
            while time.monotonic()<until:
                value=state()
                if condition(value):return value
                time.sleep(.1)
            raise AssertionError(state())
        wait_for(lambda s:s.get('sourceA') and s.get('sourceB'))
        time.sleep(.7)
        assert not state()['a'] and not state()['b'],('Offscreen guard was not reproduced',state())
        plugin=base/'hics-capture.so';shutil.copy2(ROOT/'build/hics-capture.so',plugin)
        assert ctl('plugin','load',str(plugin)) == 'ok'
        assert any(p['name']=='hics-capture' for p in json.loads(ctl('-j','plugin','list')))
        result=wait_for(lambda s:s.get('a') and s.get('b'))
        time.sleep(.3)
        image=base/'result.png';subprocess.run(['grim',str(image)],env=env,capture_output=True,check=True)
        from PIL import Image
        pixels=Image.open(image).convert('RGB');w,h=pixels.size
        for x,name in ((w-640+70,'Wayland'),(w-640+390,'XWayland')):
            crop=pixels.crop((x,h-150,x+180,h-50))
            coloured=sum(count for count,(r,g,b) in crop.getcolors(crop.width*crop.height) if (r>130 and g<75 and b<110) or (b>150 and r<80))
            assert coloured>2000,(name,coloured,result)
        print('PASS: native adapter releases pending Wayland and XWayland captures outside output coordinates',flush=True)
        print('PASS: both captured images contain actual application pixels',flush=True)
        change.touch()
        updated=False
        for _ in range(30):
            time.sleep(.1)
            subprocess.run(['grim',str(image)],env=env,capture_output=True,check=True)
            crop=Image.open(image).convert('RGB').crop((w-640+70,h-150,w-640+250,h-50))
            if sum(count for count,(r,g,b) in crop.getcolors(crop.width*crop.height) if g>130 and r<75 and b<110)>2000:
                updated=True
                break
        assert updated,'Live offscreen preview did not deliver changed application pixels'
        print('PASS: live preview updates after the offscreen application changes',flush=True)
        ctl('plugin','unload',str(plugin))
    except Exception:
        for file in base.glob('*.log'):print(file.name,file.read_text(errors='replace')[-5000:])
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
