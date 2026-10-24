"""Preflight for tests that create a nested Wayland compositor."""
import os
from pathlib import Path
import socket


def require_wayland_session():
    display = os.environ.get("WAYLAND_DISPLAY")
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not display or not runtime:
        raise SystemExit("Nested graphics tests require a running Wayland session.")
    path = Path(display) if display.startswith("/") else Path(runtime) / display
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.connect(str(path))
    except OSError as error:
        raise SystemExit(f"Cannot access parent Wayland session: {error}. No graphics tests ran.") from error


def resize_nested_compositor(pid, width=1280, height=900):
    """Resize only the test's surface; recovery-mode tiling may otherwise shrink it."""
    import json
    import subprocess
    import time
    parent=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j']))
                 if i['wl_socket']==Path(os.environ.get('WAYLAND_DISPLAY','')).name and i['pid']!=pid),None)
    if not parent:
        return
    for _ in range(60):
        clients=json.loads(subprocess.check_output(['hyprctl','-i',parent['instance'],'clients','-j']))
        own=next((w for w in clients if w['pid']==pid),None)
        if own:
            script='local w=hl.get_window('+json.dumps('address:'+own['address'])+');hl.dispatch(hl.dsp.window.float({window=w,action="enable"}));hl.dispatch(hl.dsp.window.resize({window=w,x='+str(int(width))+',y='+str(int(height))+',relative=false}))'
            subprocess.run(['hyprctl','-i',parent['instance'],'repl',script],check=True,capture_output=True,timeout=10)
            time.sleep(.4)
            return
        time.sleep(.1)
    raise AssertionError('Nested test compositor did not map a parent surface')
