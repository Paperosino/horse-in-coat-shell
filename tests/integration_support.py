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


def snapshot_qml_runtime(root, directory):
    """Copy module plugins and their shared dependencies before loading them.

    Build plugins contain absolute RUNPATHs to the build tree. Copying qmldir
    alone is insufficient; a private library path must override those RUNPATHs.
    This does not copy/override Qt or change the runtime of external apps.
    """
    import shutil
    root=Path(root);directory=Path(directory);qml=directory/'qml';libraries=directory/'qml-libs'
    shutil.copytree(root/'build/qml',qml,symlinks=False)
    libraries.mkdir()
    for source in (root/'build/shell/plugin/src/Hyprstack').rglob('libhyprstack-*.so'):
        target=libraries/source.name
        if target.exists():raise AssertionError('Ambiguous runtime library: '+source.name)
        shutil.copy2(source,target)
    shutil.copy2(root/'build/third_party/m3shapes/libm3shapes.so',libraries/'libm3shapes.so')
    return {'QML_IMPORT_PATH':str(qml),'QML2_IMPORT_PATH':str(qml),'LD_LIBRARY_PATH':str(libraries)+((':'+os.environ['LD_LIBRARY_PATH']) if os.environ.get('LD_LIBRARY_PATH') else '')}


def run_snapshot_qml(command, environment, build, timeout):
    """Communicate without pipe deadlocks; reject worktree .so mappings."""
    import subprocess
    import time
    process=subprocess.Popen(command,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.monotonic()+timeout
    try:
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise subprocess.TimeoutExpired(command,timeout)
            try:
                stdout,stderr=process.communicate(timeout=min(.2,remaining))
                return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
            except subprocess.TimeoutExpired:
                try:maps=Path('/proc')/str(process.pid)/'maps';loaded=maps.read_text()
                except FileNotFoundError:continue
                unsafe=[line for line in loaded.splitlines() if str(Path(build).resolve())+'/' in line and '.so' in line]
                if unsafe:raise AssertionError('QML test still maps mutable build libraries: '+str(unsafe))
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
