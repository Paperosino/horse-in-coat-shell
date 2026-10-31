#!/usr/bin/env python3
"""Exercise native stacking focus motion in an isolated nested compositor."""
import json, os, shutil, subprocess, tempfile, time
from pathlib import Path
from integration_support import require_wayland_session, resize_nested_compositor

require_wayland_session()
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-focus-motion-') as directory:
    base = Path(directory); processes = []
    (base/'config/hics').mkdir(parents=True); (base/'data/native').mkdir(parents=True)
    (base/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
    native = Path(os.environ.get('HICS_TEST_NATIVE_DIR', ROOT/'build'))
    for name in ('libhics-render-dispatch.so', 'hics-bars.so', 'hics-motion.so'):
        shutil.copy2(native/name, base/'data/native'/name)
    config = ROOT/'shell/assets/hyprland/config'
    lua = base/'test.lua'
    lua.write_text('package.path='+json.dumps(str(config/'?.lua')+';')+'..package.path\n'
        'package.preload["scheme.current"]=function()return require("scheme.default")end\n'
        'hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n'+
        ''.join('dofile('+json.dumps(str(path))+')\n' for path in (config/'hyprland/animations.lua',config/'hyprland/gestures.lua',ROOT/'shell/assets/hyprland/layouts.lua')))
    env = dict(os.environ, AQ_BACKEND='wayland', XDG_CONFIG_HOME=str(base/'config'), HYPRSTACK_DATA_DIR=str(base/'data'), XDG_STATE_HOME=str(base/'state'), XDG_CACHE_HOME=str(base/'cache'), XDG_DATA_HOME=str(base/'user-data'))
    env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    def wait(check, what, timeout=10):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            value=check()
            if value:return value
            time.sleep(.05)
        raise AssertionError(what)
    try:
        fixtures = ROOT/'tests/fixtures'
        binary = os.environ.get('HICS_TEST_KEYBOARD_BINARY')
        if binary:
            shutil.copy2(binary, base/'keyboard')
        else:
            for flag, suffix in (('client-header', '.h'), ('private-code', '.c')):
                subprocess.run(['wayland-scanner', flag, str(fixtures/'virtual-keyboard.xml'), str(base/('virtual-keyboard'+suffix))], check=True)
            flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'wayland-client', 'xkbcommon'], text=True).split()
            subprocess.run(['cc', str(fixtures/'virtual-keyboard-stream.c'), str(base/'virtual-keyboard.c'), '-I', str(base), *flags, '-o', str(base/'keyboard')], check=True)
        with (base/'compositor.log').open('w') as log:
            compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
        processes.append(compositor)
        instance=wait(lambda:next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None),'no nested compositor')
        resize_nested_compositor(compositor.pid)
        sig=instance['instance']; appenv=dict(env, WAYLAND_DISPLAY=instance['wl_socket'], HYPRLAND_INSTANCE_SIGNATURE=sig)
        def ctl(*args):return subprocess.check_output(['hyprctl','-i',sig,*args],text=True,timeout=10).strip()
        assert ctl('plugin','load',str(base/'data/native/hics-motion.so'))=='ok'
        apps=[]
        for n in range(2):
            app=subprocess.Popen(['kitty','--class','org.hics.FocusFixture'+str(n),'-o','confirm_os_window_close=0','python3','-u','-c', 'import os,tty; tty.setraw(0); open('+repr(str(base/'keys'))+',"ab",buffering=0).write(os.read(0,1)); import time; time.sleep(120)'],env=appenv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            apps.append(app); processes.append(app)
            wait(lambda: any(w['pid']==app.pid for w in json.loads(ctl('-j','clients'))),'window did not map')
        def window(n):return next(w for w in json.loads(ctl('-j','clients')) if w['pid']==apps[n].pid)
        for n in range(2):
            address=window(n)['address']
            ctl('repl','local w=hl.get_window("address:'+address+'");hl.dispatch(hl.dsp.window.resize({window=w,x=600,y=420,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x='+str(180+n*100)+',y='+str(180+n*70)+',relative=false}))')
        time.sleep(.7)
        def focus(n):ctl('repl','hl.dispatch(hl.dsp.focus({window=hl.get_window("address:'+window(n)['address']+'") }))')
        def state(n):
            w=window(n); identity=format(w['stableId'],'x') if isinstance(w.get('stableId'),int) else w.get('stableId')
            raw=ctl('repl','local s=hl.plugin.hics_motion.focus_animation('+json.dumps(w['address'])+','+json.dumps(identity)+',"state");return require("utils.json").encode(s or {})')
            result=json.loads(raw);return json.loads(result) if isinstance(result,str) else result
        keyboard=subprocess.Popen([str(base/'keyboard')],env=appenv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1);processes.append(keyboard)
        assert keyboard.stdout.readline().strip()=='ready'
        for profile in ('expressive','standard','heavy','jelly'):
            ctl('repl','hyprstack_layouts.configure({stackFocusMotion='+json.dumps(profile)+'})')
            focus(1); time.sleep(.1); before=window(0); focus(0); time.sleep(.08)
            current=state(0); outgoing=state(1)
            assert current.get('scale',1)>1 and current.get('paints',0)>0, (profile,current)
            assert outgoing.get('scale',1)<1 and outgoing.get('paints',0)>0, (profile,outgoing)
            after=window(0); assert before['at']==after['at'] and before['size']==after['size'], (before,after)
            wait(lambda:not state(0) and not state(1),'focus transformers did not clean up',3)
            print('PASS: '+profile+' renders and preserves client geometry',flush=True)
        focus(1);time.sleep(.1);focus(0)
        for state_value in (1,0):
            keyboard.stdin.write(f'key 30 {state_value}\n');keyboard.stdin.flush();assert keyboard.stdout.readline().strip()=='ok'
        wait(lambda:(base/'keys').exists() and (base/'keys').read_bytes()==b'a', 'keyboard input lost during focus animation')
        print('PASS: keyboard input reaches focused client during motion',flush=True)
        address=window(0)['address']
        ctl('repl','hyprstack_layouts.action("minimize",'+json.dumps(address)+')')
        wait(lambda:window(0)['workspace']['name'].startswith('special:hyprstack-minimized-'),'minimize failed')
        ctl('repl','hyprstack_layouts.action("restore",'+json.dumps(address)+')')
        wait(lambda:not window(0)['workspace']['name'].startswith('special:hyprstack-minimized-'),'restore failed')
        print('PASS: minimize and restore after focus motion',flush=True)
        ctl('repl','hyprstack_layouts.configure({stackFocusMotion="off"})')
        focus(1);focus(0);time.sleep(.1);assert not state(0),state(0)
        ctl('repl','hyprstack_layouts.configure({stackFocusMotion="expressive"})')
        (base/'config/hics/shell.json').write_text('{"appearance":{"reducedMotion":true}}')
        focus(1);focus(0);time.sleep(.1);assert not state(0),state(0)
        print('PASS: reduced motion switches immediately',flush=True)
        (base/'config/hics/shell.json').write_text('{}')
        focus(1);focus(0);apps[0].terminate();apps[0].wait(timeout=5)
        time.sleep(1); assert compositor.poll() is None, 'compositor crashed when animated window closed'
        assert not ctl('configerrors'),ctl('configerrors')
        print('PASS: closing an animating window leaves compositor running',flush=True)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()
