#!/usr/bin/env python3
"""Run the inhibitor prototype against GTK4 in an isolated nested compositor."""
import argparse
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from integration_support import require_wayland_session, snapshot_qml_runtime

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();require_wayland_session()
    if args.output.exists():parser.error('Use a fresh output directory')
    os.umask(0o077);args.output.mkdir(parents=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix='hlo-') as directory:
        root=Path(directory);runtime=root/'run';runtime.mkdir(mode=0o700)
        config=root/'hyprland.lua';config.write_text('hl.monitor({output="WAYLAND-1",mode="800x600@60",position="0x0",scale=1})\n')
        display=os.environ['WAYLAND_DISPLAY']
        if not display.startswith('/'):display=str(Path(os.environ['XDG_RUNTIME_DIR'])/display)
        env=dict(os.environ,HOME=str(root),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),
                 XDG_STATE_HOME=str(root/'state'),XDG_CACHE_HOME=str(root/'cache'),XDG_RUNTIME_DIR=str(runtime),
                 WAYLAND_DISPLAY=display,AQ_BACKEND='wayland',DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'no-bus'),
                 DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'no-bus'),PULSE_SERVER='unix:'+str(root/'no-pulse'),
                 GSETTINGS_BACKEND='memory')
        env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);env.pop('LD_LIBRARY_PATH',None)
        with (args.output/'hyprland.log').open('w') as log:
            compositor=subprocess.Popen(['Hyprland','--config',str(config)],env=env,stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+20
                while True:
                    assert compositor.poll() is None,'Nested compositor exited'
                    raw=subprocess.check_output(['hyprctl','instances','-j'],env=env,text=True,timeout=3)
                    try:instances=json.loads(raw)
                    except json.JSONDecodeError:instances=[]
                    item=next((x for x in instances if x['pid']==compositor.pid),None)
                    if item:
                        monitors=json.loads(subprocess.check_output(['hyprctl','-i',item['instance'],'monitors','-j'],env=env,text=True,timeout=3))
                        if monitors:break
                    assert time.monotonic()<deadline,'Nested output not ready'
                    time.sleep(.1)
                test_env=dict(env,HICS_TEST_GTK_DISPLAY=str(runtime/item['wl_socket']))
                with (args.output/'tests.log').open('w') as test_log:
                    test=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_logout_inhibit*.py','-v'],
                                        env=test_env,stdout=test_log,stderr=subprocess.STDOUT,timeout=45)
                if test.returncode:raise SystemExit('Tests failed; inspect '+str(args.output/'tests.log'))
                # Exercise the actual non-modal QML component with an isolated fixture model.
                shell=root/'shell'
                installed = os.environ.get('HICS_TEST_INSTALLED_RUNTIME') == '1'
                shell_source = Path('/usr/share/hics/shell') if installed else ROOT/'shell'
                shutil.copytree(shell_source,shell,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
                if installed:
                    shutil.copy2(ROOT/'shell/modules/session/LogoutBlockersWindow.qml',shell/'modules/session/LogoutBlockersWindow.qml')
                shutil.copy2(ROOT/'tests/fixtures/logout_dialog.qml',shell/'shell.qml')
                ui_env=dict(env,WAYLAND_DISPLAY=str(runtime/item['wl_socket']),
                            HYPRLAND_INSTANCE_SIGNATURE=item['instance'],QT_QPA_PLATFORM='wayland',
                            HICS_DIALOG_SCREENSHOT=str(args.output/'dialog.png'))
                if installed:
                    ui_env.update(QML_IMPORT_PATH='/usr/share/hics/qml',QML2_IMPORT_PATH='/usr/share/hics/qml',
                                  LD_LIBRARY_PATH='/usr/share/hics/qs/lib:/usr/share/hics/qml/Hyprstack/lib:/usr/share/hics/lib')
                else:
                    ui_env.update(snapshot_qml_runtime(ROOT,root))
                with (args.output/'dialog.log').open('w') as ui_log:
                    ui=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(shell)],env=ui_env,
                                      stdout=ui_log,stderr=subprocess.STDOUT,timeout=30)
                output=(args.output/'dialog.log').read_text()
                assert ui.returncode==0 and 'LOGOUT_DIALOG_OK' in output, output[-5000:]
                report={'status':'passed','scope':'prototype inhibitor backend, real GTK4 and XDG frontend and standalone dialog in nested compositor; no actual logout',
                        'nestedPid':compositor.pid,'output':monitors[0].get('name')}
                (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
            finally:
                if compositor.poll() is None:
                    compositor.terminate()
                    try:compositor.wait(timeout=5)
                    except subprocess.TimeoutExpired:compositor.kill();compositor.wait()

if __name__=='__main__':main()
