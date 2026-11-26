#!/usr/bin/env python3
"""Exercise actual native Qt5/6 file selection and cancellation on private data."""
import json, os, shlex, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from integration_support import require_wayland_session, resize_nested_compositor

require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shell/assets'))
from gtk_theme import apply_palette

with tempfile.TemporaryDirectory(prefix='hics-file-dialogs-') as directory:
    base=Path(directory);processes=[]
    for name in ('home','config','data','cache','state'): (base/name).mkdir()
    env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),XDG_STATE_HOME=str(base/'state'),AQ_BACKEND='wayland',GTK_A11Y='none',GSETTINGS_BACKEND='keyfile',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'))
    for key in ('HYPRLAND_INSTANCE_SIGNATURE','QT_PLUGIN_PATH','LD_LIBRARY_PATH','QT_STYLE_OVERRIDE','GTK_THEME'):env.pop(key,None)
    busconfig=base/'bus.conf';busconfig.write_text('<busconfig><type>session</type><listen>unix:path='+str(base/'bus')+'</listen><auth>EXTERNAL</auth><policy context="default"><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
    try:
        bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(busconfig)],stdout=subprocess.PIPE,text=True);processes.append(bus)
        env['DBUS_SESSION_BUS_ADDRESS']=bus.stdout.readline().strip()
        lua=base/'test.lua';lua.write_text('hl.monitor({output="WAYLAND-1",mode="1000x760@60",position="0x0",scale=1})\n')
        with (base/'compositor.log').open('w') as log:
            compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(compositor)
        for _ in range(100):
            instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
            if instance:break
            assert compositor.poll() is None,(base/'compositor.log').read_text()
            time.sleep(.05)
        assert instance,'No nested compositor'
        resize_nested_compositor(compositor.pid,1000,760)
        env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland',GDK_BACKEND='wayland')
        fixture=base/'example.txt';fixture.write_text('Private file chooser fixture')
        for version in (5,6):
            binary=base/f'probe{version}'
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',f'Qt{version}Widgets','gtk+-3.0'],text=True))
            subprocess.run(['c++','-std=c++17','-fPIC','-DQT_NO_KEYWORDS',str(ROOT/'tests/fixtures/qt-file-dialog-probe.cpp'),*flags,'-o',str(binary)],check=True)
            plugins=base/f'plugins{version}';shutil.copytree(ROOT/f'build/qt-themes/qt{version}',plugins)
            for theme in ('hics','gtk3'):
                for mode,surface in (('dark','101018'),('light','f5f5f5')):
                    colours=dict(surface=surface,onSurface='808080',surfaceContainer=surface,primary='aaccee',onPrimary='102030',outlineVariant='505060')
                    apply_palette(colours,base/'config',mode)
                    for operation in ('open','save','directory','cancel'):
                        target=base if operation=='directory' else base/'new.txt' if operation=='save' else fixture
                        extra={'HICS_TEST_CHOOSER_SCREENSHOT':f'/tmp/hics-qt{version}-{theme}-{mode}-chooser.png'} if operation=='open' else {}
                        run=subprocess.run([str(binary),str(target),operation],env=dict(env,QT_QPA_PLATFORMTHEME=theme,QT_PLUGIN_PATH=str(plugins),**extra),capture_output=True,text=True,timeout=10)
                        assert run.returncode==0,(version,theme,mode,operation,run.stdout,run.stderr)
                        assert 'NATIVE=1' in run.stdout,run.stdout
                        if theme=='hics':
                            assert 'WINDOW=#'+surface in run.stdout,(version,theme,mode,run.stdout,run.stderr)
                        assert not (base/'new.txt').exists(),'Save selection unexpectedly wrote a file'
                    print(f'PASS: Qt{version} {theme} {mode}: native open/save/folder/cancel'+(' and exact palette' if theme=='hics' else ''),flush=True)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
