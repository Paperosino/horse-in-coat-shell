#!/usr/bin/env python3
"""Check the installed GTK portal's logout inhibition without touching real buses.

The GTK backend is connected to the existing Wayland display but creates no
window. Its user/system buses and HOME/XDG paths are private and have no D-Bus
activation directories. The result is diagnostic, not an end-to-end logout.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from integration_support import require_wayland_session


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output file')
    require_wayland_session()
    with tempfile.TemporaryDirectory(prefix='hics-inhibit-audit-') as directory:
        root=Path(directory);runtime=root/'run';runtime.mkdir(mode=0o700)
        config=root/'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(root)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(config)],stdout=subprocess.PIPE,text=True)
        backend=None
        try:
            address=bus.stdout.readline().strip();assert address
            display=os.environ['WAYLAND_DISPLAY']
            if not display.startswith('/'):
                display=str(Path(os.environ['XDG_RUNTIME_DIR'])/display)
            env=dict(os.environ,HOME=str(root),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),
                     XDG_CACHE_HOME=str(root/'cache'),XDG_STATE_HOME=str(root/'state'),XDG_RUNTIME_DIR=str(runtime),
                     XDG_DATA_DIRS='/usr/local/share:/usr/share',WAYLAND_DISPLAY=display,
                     DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address,GSETTINGS_BACKEND='memory',
                     PULSE_SERVER='unix:'+str(root/'no-pulse'))
            env.pop('LD_LIBRARY_PATH',None)
            backend=subprocess.Popen(['/usr/lib/xdg-desktop-portal-gtk'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            deadline=time.monotonic()+10
            while True:
                probe=subprocess.run(['gdbus','introspect','--session','--dest','org.freedesktop.impl.portal.desktop.gtk',
                    '--object-path','/org/freedesktop/portal/desktop'],env=env,capture_output=True,text=True,timeout=3)
                if probe.returncode==0:break
                assert backend.poll() is None and time.monotonic()<deadline,'GTK backend did not start'
                time.sleep(.05)
            result=subprocess.run(['gdbus','call','--session','--dest','org.freedesktop.impl.portal.desktop.gtk',
                '--object-path','/org/freedesktop/portal/desktop','--method','org.freedesktop.impl.portal.Inhibit.Inhibit',
                '/org/freedesktop/portal/desktop/request/1_123/hics_test','org.hics.LogoutProbe','','1',
                "{'reason': <'Unsaved test work'>}"],env=env,capture_output=True,text=True,timeout=5)
            report={'scope':'GTK portal backend, private bus without GNOME session manager; no real applications or logout',
                    'returnCode':result.returncode,'reply':result.stdout.strip(),'error':result.stderr.strip()}
            args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
        finally:
            if backend and backend.poll() is None:
                backend.terminate();backend.wait(timeout=5)
            bus.terminate();bus.wait(timeout=5)

if __name__=='__main__':main()
