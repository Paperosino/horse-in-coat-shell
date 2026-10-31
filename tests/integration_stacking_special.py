#!/usr/bin/env python3
"""Special workspaces must follow stacking without exposing minimized windows."""
import json, os, shutil, subprocess, tempfile, time
from pathlib import Path
from integration_support import require_wayland_session, resize_nested_compositor

require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-special-stacking-') as directory:
    base=Path(directory); (base/'config/hics').mkdir(parents=True); (base/'native').mkdir()
    (base/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
    native=Path(os.environ.get('HICS_TEST_NATIVE_DIR','/usr/share/hics/native'))
    for name in ('libhics-render-dispatch.so','hics-bars.so','libspatialoverview.so'):
        shutil.copy2(native/name,base/'native'/name)
    lua=base/'config.lua'
    lua.write_text('package.path='+json.dumps(str(ROOT/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\n'
        'package.preload["scheme.current"]=function()return require("scheme.default")end\n'
        'hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n'+
        ''.join('dofile('+json.dumps(str(ROOT/path))+')\n' for path in (
            'shell/assets/hyprland/config/hyprland/animations.lua',
            'shell/assets/hyprland/config/hyprland/gestures.lua',
            'shell/assets/hyprland/layouts.lua')))
    config=base/'bus.conf';config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(base)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    processes=[];env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),HYPRSTACK_DATA_DIR=str(base));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    def wait(check,what):
        end=time.monotonic()+10
        while time.monotonic()<end:
            value=check()
            if value:return value
            time.sleep(.1)
        raise AssertionError(what)
    try:
        bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(config)],stdout=subprocess.PIPE,text=True);processes.append(bus);env['DBUS_SESSION_BUS_ADDRESS']=bus.stdout.readline().strip()
        with (base/'compositor.log').open('w') as log: compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
        processes.append(compositor)
        def instance():return next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
        nested=wait(instance,'nested compositor');resize_nested_compositor(compositor.pid)
        env.update(WAYLAND_DISPLAY=nested['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=nested['instance'])
        def ctl(*args):return subprocess.check_output(['hyprctl','-i',nested['instance'],*args],env=env,text=True).strip()
        def window(pid):return next((w for w in json.loads(ctl('-j','clients')) if w['pid']==pid),None)
        ctl('eval','hl.dispatch(hl.dsp.focus({workspace="special:music"}))')
        apps=[]
        for num in range(2):
            p=subprocess.Popen(['kitty','--class','org.hics.SpecialFixture'+str(num),'-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);apps.append(p);processes.append(p)
            wait(lambda:window(p.pid),'special window did not map')
        def floating():return all((w:=window(p.pid)) and w['floating'] and w['workspace']['name']=='special:music' for p in apps)
        wait(floating,'special windows remained tiled in stacking')
        print('PASS: special workspace windows float in stacking',flush=True)
        target=window(apps[0].pid)
        def action(op):ctl('eval','hyprstack_layouts.action('+json.dumps(op)+','+json.dumps(target['address'])+','+json.dumps(target['stableId'])+')')
        action('minimize')
        wait(lambda:(w:=window(apps[0].pid)) and w['workspace']['name'].startswith('special:hyprstack-minimized-'),'special window did not minimize')
        action('dock-activate')
        wait(floating,'minimized special window did not return to its own workspace')
        print('PASS: special workspace window minimizes and restores in place',flush=True)
        ctl('eval','hyprstack_layouts.set_mode("scrolling")')
        wait(lambda:all((w:=window(p.pid)) and not w['floating'] and w['workspace']['name']=='special:music' for p in apps),'special windows did not return to scrolling')
        ctl('eval','hyprstack_layouts.set_mode("stacking")')
        wait(floating,'special windows did not return to stacking')
        print('PASS: special workspace follows mode transitions',flush=True)
        ctl('eval','hl.dispatch(hl.dsp.workspace.toggle_special("music"))')
        def special_open():return bool(json.loads(ctl('-j','monitors'))[0]['specialWorkspace']['name'])
        wait(lambda:not special_open(),'special workspace did not close')
        ctl('eval','hyprstack_layouts.set_mode("scrolling")')
        assert not special_open(),'switching to scrolling reopened a hidden special workspace'
        ctl('eval','hyprstack_layouts.set_mode("stacking")')
        assert not special_open(),'switching to stacking reopened a hidden special workspace'
        print('PASS: layout changes do not reveal hidden special workspace',flush=True)
        ctl('reload')
        time.sleep(.5)
        assert not special_open(),'reload reopened a hidden special workspace'
        ctl('eval','hl.dispatch(hl.dsp.workspace.toggle_special("music"))')
        wait(floating,'reload left special windows tiled')
        print('PASS: reload preserves the special workspace and stacking state',flush=True)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
