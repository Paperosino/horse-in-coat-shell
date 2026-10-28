#!/usr/bin/env python3
"""Exercise an explicit portal backend on a nested Hyprland and a private bus.

The nested compositor uses the existing Wayland session as its display, while
configuration, portal services and test data are private. No input is injected.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from integration_support import require_wayland_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-binary', required=True, type=Path)
    parser.add_argument('--probe-binary', required=True, type=Path)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require_wayland_session()
    if args.output.exists():
        parser.error('Use a fresh evidence directory')
    os.umask(0o077)
    output = args.output.resolve()
    output.mkdir(parents=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='hics-nested-portal-') as directory:
        root = Path(directory)
        backend = root/'portal-backend'
        shutil.copy2(args.backend_binary, backend)
        sha = hashlib.sha256(backend.read_bytes()).hexdigest()
        (root/'hyprland.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x800@60",position="0x0",scale=1})\n')
        env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root/'config'),
                   XDG_DATA_HOME=str(root/'data'), XDG_CACHE_HOME=str(root/'cache'),
                   XDG_STATE_HOME=str(root/'state'), AQ_BACKEND='wayland',
                   DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'absent-bus'),
                   DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'absent-bus'))
        for key in ('HYPRLAND_INSTANCE_SIGNATURE','LD_LIBRARY_PATH','QT_PLUGIN_PATH'):
            env.pop(key, None)
        compositor = None
        with (output/'hyprland.log').open('w') as log:
            try:
                compositor = subprocess.Popen(['Hyprland','--config',str(root/'hyprland.lua')],
                                              env=env,stdout=log,stderr=subprocess.STDOUT)
                deadline = time.monotonic()+20
                instance = None
                while time.monotonic()<deadline:
                    assert compositor.poll() is None, 'Nested compositor exited; inspect hyprland.log'
                    instances = json.loads(subprocess.check_output(['hyprctl','instances','-j'],text=True,timeout=3))
                    instance = next((item for item in instances if item['pid']==compositor.pid),None)
                    if instance:
                        monitors = json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'monitors','-j'],text=True,timeout=3))
                        if monitors:
                            break
                    time.sleep(.1)
                else:
                    raise AssertionError('Nested compositor has no output; inspect hyprland.log')
                nested_env = dict(os.environ, WAYLAND_DISPLAY=instance['wl_socket'],
                                  HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
                command = ['python3', str(Path(__file__).with_name('integration_qt_portal_frontend.py')),
                           '--runtime',str(args.runtime.resolve()),'--probe-binary',str(args.probe_binary.resolve()),
                           '--output',str(output/'frontend.json'),'--hyprland-backend',
                           '--hyprland-backend-binary',str(backend),'--private-pipewire']
                with (output/'frontend.log').open('w') as testlog:
                    run = subprocess.run(command,env=nested_env,stdout=testlog,stderr=subprocess.STDOUT,timeout=45)
                assert run.returncode==0, 'Private portal test failed; inspect frontend.log'
                report = json.loads((output/'frontend.json').read_text())
                assert report['hyprlandBackendSha256']==sha and compositor.poll() is None
                (output/'result.json').write_text(json.dumps({'status':'passed','nestedPid':compositor.pid,
                    'backendSha256':sha,'output':monitors[0].get('name'),
                    'scope':'private portal frontend, backend and PipeWire; no capture or picker'},indent=2)+'\n')
                print((output/'result.json').read_text())
            finally:
                if compositor and compositor.poll() is None:
                    compositor.terminate()
                    try: compositor.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        compositor.kill();compositor.wait()


if __name__=='__main__':
    main()
