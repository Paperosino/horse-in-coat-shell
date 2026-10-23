#!/usr/bin/env python3
"""Applications must survive gio exit and keep stdout/stderr writable."""
import json
import signal
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-launch-lifetime-') as directory:
    base = Path(directory)
    apps = base / 'data/applications'
    apps.mkdir(parents=True)
    marker = base / 'completed'
    fixture = base / 'writer.py'
    fixture.write_text('import pathlib,sys,time,os\npathlib.Path(sys.argv[1]+".pid").write_text(str(os.getpid()))\npathlib.Path(sys.argv[1]+".env").write_text(os.environ.get("LD_LIBRARY_PATH","absent"))\ntime.sleep(.5)\nprint("late stdout",flush=True)\nprint("late stderr",file=sys.stderr,flush=True)\ntime.sleep(.5)\npathlib.Path(sys.argv[1]).write_text(str(pathlib.Path.cwd()))\n')
    (apps / 'org.hics.LaunchLifetime.desktop').write_text('[Desktop Entry]\nType=Application\nName=Launch lifetime fixture\nTerminal=false\nPath='+str(base)+'\nExec=/usr/bin/python3 '+str(fixture)+' '+str(marker)+'\n')
    qml = base / 'test.qml'
    qml.write_text('''import QtQuick
import Quickshell
import Hyprstack.Services
ShellRoot {
 Timer {interval:100;running:true;onTriggered:{const app=ApplicationCatalogue.byId("org.hics.LaunchLifetime");if(!app)throw new Error("Missing launch fixture");app.execute()}}
 Timer {interval:700;running:true;onTriggered:{console.warn("LAUNCH_ERROR",ApplicationCatalogue.error);Qt.quit()}}
}''')
    imports = os.environ.get('HICS_LAUNCH_TEST_IMPORTS', str(ROOT / 'build/qml'))
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_DATA_HOME=str(base / 'data'), XDG_STATE_HOME=str(base / 'state'), XDG_CONFIG_HOME=str(base / 'config'), QML_IMPORT_PATH=imports, QML2_IMPORT_PATH=imports)
    env['LD_LIBRARY_PATH']='/usr/share/hics/qs/lib'
    env.pop('WAYLAND_DISPLAY', None)
    env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    process = subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs', '-p', str(qml)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    output,errors=process.communicate(timeout=10)
    assert process.returncode == 0, output+errors
    pid=int(Path(str(marker)+'.pid').read_text())
    assert os.getpgid(pid) != process.pid, 'GIO application inherited the shell process group'
    try: os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError: pass
    deadline=time.monotonic()+4
    while not marker.exists() and time.monotonic()<deadline:time.sleep(.03)
    assert marker.exists(), ('Application died after shell exit',output,errors)
    assert Path(str(marker)+'.env').read_text() == 'absent', 'Bundled Qt leaked into the application'
    assert marker.read_text() == str(base), 'Desktop working directory was lost'
    log = base / 'state/hics/applications/org.hics.LaunchLifetime.log'
    assert 'late stdout' in log.read_text() and 'late stderr' in log.read_text(), 'Application output was lost'
    print('PASS: application survives shell exit and process-group termination, with writable output streams')
    print('PASS: desktop working directory is preserved')
