#!/usr/bin/env python3
"""Exercise an Electron editable field in an isolated nested XWayland session.

The probe sends real virtual pointer/keyboard events to the nested compositor.
It never reads the user's clipboard: the Electron process creates an in-memory
image on its own private X server before the paste test.
"""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import time

from integration_support import require_wayland_session, resize_nested_compositor

require_wayland_session()
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures'


def wait_for(predicate, description, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError('Timed out waiting for ' + description)


with tempfile.TemporaryDirectory(prefix='hics-electron-input-') as directory:
    base = Path(directory)
    (base / 'config/hics').mkdir(parents=True)
    (base / 'config/hics/layouts.json').write_text('{"mode":"stacking"}')
    native = base / 'native'
    native.mkdir()
    source_native = Path(os.environ.get('HICS_TEST_NATIVE_DIR', '/usr/share/hics/native'))
    for name in ('libhics-render-dispatch.so', 'hics-bars.so', 'libspatialoverview.so'):
        shutil.copy2(source_native / name, native / name)
    lua = base / 'test.lua'
    lua.write_text('package.path=' + json.dumps(str(ROOT / 'shell/assets/hyprland/config/?.lua') + ';') + '..package.path\n'
                   'package.preload["scheme.current"]=function()return require("scheme.default")end\n'
                   'hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n'
                   'dofile(' + json.dumps(str(ROOT / 'shell/assets/hyprland/config/hyprland/animations.lua')) + ')\n'
                   'dofile(' + json.dumps(str(ROOT / 'shell/assets/hyprland/config/hyprland/gestures.lua')) + ')\n'
                   'dofile(' + json.dumps(str(ROOT / 'shell/assets/hyprland/layouts.lua')) + ')\n')
    for protocol, stem in [('wlr-virtual-pointer-unstable-v1.xml', 'virtual-pointer'),
                           ('virtual-keyboard.xml', 'virtual-keyboard')]:
        for mode, ext in [('client-header', '.h'), ('private-code', '.c')]:
            subprocess.run(['wayland-scanner', mode, str(FIXTURES / protocol), str(base / (stem + ext))], check=True)
    for fixture, protocol, binary, packages in [
        ('virtual-pointer.c', 'virtual-pointer.c', 'pointer', ['wayland-client']),
        ('virtual-keyboard-stream.c', 'virtual-keyboard.c', 'keyboard', ['wayland-client', 'xkbcommon']),
    ]:
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', *packages], text=True))
        source = FIXTURES / fixture
        if binary == 'keyboard':
            # Virtual keyboards must send modifier state explicitly, unlike a
            # physical keyboard. Keep the shared fixture's normal behavior.
            source = base/'keyboard.c'
            source.write_text((FIXTURES / fixture).read_text().replace(
                'wl_display_roundtrip(display);puts("ok");fflush(stdout);',
                'if(key==29)zwp_virtual_keyboard_v1_modifiers(keyboard,state?4:0,0,0,0);'
                'wl_display_roundtrip(display);puts("ok");fflush(stdout);'))
        subprocess.run(['cc', str(source), str(base / protocol), '-I' + str(base), *flags, '-o', str(base / binary)], check=True)
    app = base / 'app'
    app.mkdir()
    (app / 'package.json').write_text('{"name":"hics-input-probe","version":"1.0.0","main":"main.js"}')
    (app / 'main.js').write_text('''
const {app, BrowserWindow, clipboard, nativeImage} = require('electron');
const fs = require('fs');
let win;
console.log('probe main loaded');
app.commandLine.appendSwitch('ozone-platform', 'x11');
app.whenReady().then(() => {
  console.log('probe app ready');
  win = new BrowserWindow({width: 700, height: 500, show: true, webPreferences:{nodeIntegration: true, contextIsolation: false}});
  console.log('probe window created');
  win.on('show', () => console.log('probe window shown'));
  win.loadFile('index.html');
  win.webContents.once('did-finish-load', () => {
    clipboard.writeImage(nativeImage.createFromBitmap(Buffer.from([0, 0, 255, 255]), {width:1, height:1}));
    if (clipboard.readImage().isEmpty()) throw new Error('Test image not available');
    console.log('probe page loaded');
  });
});
''')
    (app / 'index.html').write_text('''<!doctype html><meta charset="utf-8"><style>body{margin:0} #edit{margin:50px;width:450px;height:200px;border:2px solid black}</style>
<div id="edit" contenteditable="true"></div><script>
const fs = require('fs'), p = process.env.HICS_INPUT_LOG;
for (const name of ['focus','keydown','input','paste']) edit.addEventListener(name, e => {
 fs.appendFileSync(p, JSON.stringify({type:name,key:e.key || '', text:edit.innerText, image:e.clipboardData ? Array.from(e.clipboardData.types).includes('Files') : false})+'\\n');
});
</script>''')
    env = dict(os.environ, AQ_BACKEND='wayland', XDG_CONFIG_HOME=str(base/'config'), XDG_DATA_HOME=str(base/'data'),
               XDG_STATE_HOME=str(base/'state'), XDG_CACHE_HOME=str(base/'cache'), HYPRSTACK_DATA_DIR=str(base),
               HICS_INPUT_LOG=str(base/'events'), HYPRSTACK_POINTER_WIDTH='1280', HYPRSTACK_POINTER_HEIGHT='900', LIBGL_ALWAYS_SOFTWARE='1')
    env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    env.pop('ELECTRON_RUN_AS_NODE', None)
    processes = []
    log = (base/'compositor.log').open('w')
    app_log = (base/'electron.log').open('w')
    try:
        bus_config = base/'bus.conf'
        bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(base)+'</listen>'
                              '<policy context="default"><allow send_destination="*"/>'
                              '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus = subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(bus_config)],
                               stdout=subprocess.PIPE, text=True)
        processes.append(bus)
        env['DBUS_SESSION_BUS_ADDRESS'] = bus.stdout.readline().strip()
        assert env['DBUS_SESSION_BUS_ADDRESS'], 'Private D-Bus failed to start'
        compositor = subprocess.Popen(['Hyprland', '--config', str(lua)], env=env, stdout=log, stderr=subprocess.STDOUT)
        processes.append(compositor)
        def instance():
            return next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid), None)
        nested = wait_for(instance, 'nested compositor')
        env.update(WAYLAND_DISPLAY=nested['wl_socket'], HYPRLAND_INSTANCE_SIGNATURE=nested['instance'])
        resize_nested_compositor(compositor.pid)
        def ctl(*args):
            result = subprocess.run(['hyprctl', '-i', nested['instance'], *args], env=env, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        def xdisplay():
            children = subprocess.run(['ps','--ppid',str(compositor.pid),'-o','args='],capture_output=True,text=True).stdout
            match = re.search(r'Xwayland\s+(:\d+)',children)
            return match.group(1) if match else None
        env['DISPLAY'] = wait_for(xdisplay, 'nested XWayland')
        electron = subprocess.Popen(['/usr/lib/electron42/electron', '--no-sandbox', '--ozone-platform=x11', str(app)], env=env, cwd=app, stdout=app_log, stderr=subprocess.STDOUT)
        processes.append(electron)
        def client():
            return next((w for w in json.loads(ctl('-j','clients')) if w['pid']==electron.pid and w['mapped']),None)
        try:
            window = wait_for(client, 'Electron window')
        except AssertionError:
            app_log.flush()
            log.flush()
            tree = subprocess.run(['xprop','-root','_NET_CLIENT_LIST','_NET_ACTIVE_WINDOW'],env=env,capture_output=True,text=True).stdout
            raise AssertionError('Electron failed to map: '+(base/'electron.log').read_text()[-3000:]
                                 +'; status='+str(electron.poll())+'; DISPLAY='+env['DISPLAY']
                                 +'; X11='+tree+'; clients='+ctl('-j','clients')+'; compositor='+(base/'compositor.log').read_text()[-1000:])
        assert window['xwayland'], window
        def page_ready():
            app_log.flush()
            return 'probe page loaded' in (base/'electron.log').read_text()
        wait_for(page_ready, 'Electron page load')
        pointer = subprocess.Popen([str(base/'pointer')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        keyboard = subprocess.Popen([str(base/'keyboard')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
        processes.extend([pointer,keyboard])
        for process in (pointer,keyboard): assert process.stdout.readline().strip() == 'ready'
        def send(process, command):
            process.stdin.write(command+'\n'); process.stdin.flush()
            assert process.stdout.readline().strip() == 'ok'
            time.sleep(.1)
        def key(code):
            send(keyboard, f'key {code} 1'); send(keyboard, f'key {code} 0')
        # Click the editable area and type before touching the clipboard.
        x, y = window['at']; send(pointer, f'move {x+100} {y+130}')
        send(pointer, 'button 272 1'); send(pointer, 'button 272 0')
        key(30)
        def events():
            return [json.loads(line) for line in (base/'events').read_text().splitlines()] if (base/'events').exists() else []
        try:
            wait_for(lambda: any(e['type']=='input' and e['text']=='a' for e in events()), 'first typed character before paste')
        except AssertionError:
            app_log.flush()
            raise AssertionError('Before paste: events='+repr(events())+'; window='+repr(client())
                                 +'; Electron='+(base/'electron.log').read_text()[-2000:])
        # Exercise the same stacking path as the dock, including the hidden
        # workspace and the first physical key after restoring the window.
        address = json.dumps(window['address'])
        stable = json.dumps(window['stableId'])
        ctl('eval', f'hyprstack_layouts.action("minimize",{address},{stable})')
        wait_for(lambda: client() and client()['workspace']['name'].startswith('special:'), 'minimized workspace')
        delay = float(os.environ.get('HICS_TEST_IDLE_SECONDS', '2'))
        assert 0 <= delay <= 1800, 'Invalid isolated idle interval'
        time.sleep(delay)
        ctl('eval', f'hyprstack_layouts.action("dock-activate",{address},{stable})')
        restored = wait_for(lambda: (w if (w := client()) and w['visible'] and not w['workspace']['name'].startswith('special:') else None), 'restored window')
        x, y = restored['at']
        send(pointer, f'move {x+100} {y+130}')
        send(pointer, 'button 272 1'); send(pointer, 'button 272 0')
        key(46)
        wait_for(lambda: any(e['type']=='input' and 'c' in e['text'] for e in events()), 'first key after stacking restore')
        print(f'PASS: Electron XWayland accepts input after stacking minimize and {delay:g}s idle')
        # Paste only the probe's private image, then verify another key.
        send(keyboard,'key 29 1'); key(47); send(keyboard,'key 29 0')
        try:
            wait_for(lambda: any(e['type']=='paste' and e['image'] for e in events()), 'image paste')
        except AssertionError:
            raise AssertionError('Image paste not observed: '+repr(events()))
        key(48)
        wait_for(lambda: any(e['type']=='input' and 'b' in e['text'] for e in events()), 'typed character after paste')
        print('PASS: Electron XWayland editable accepts input before and after image paste')
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
        log.close(); app_log.close()
