"""Session-scoped Xauthority and local root ACL for Hyprland 0.56.2."""
import ctypes
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import tempfile


def prepare(data):
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    info = runtime.stat()
    if not runtime.is_absolute() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('XDG_RUNTIME_DIR must be a private directory owned by the session user')
    launcher = Path(data).resolve() / 'xwayland'
    if not os.access(launcher / 'Xwayland', os.X_OK):
        raise ValueError('HICS XWayland launcher is missing; reinstall hics')
    directory = Path(tempfile.mkdtemp(prefix='hics-xauthority-', dir=runtime))
    authority = directory / 'Xauthority'
    authority.touch(mode=0o600)
    return {'XAUTHORITY': str(authority), 'HICS_XWAYLAND_AUTHORITY': str(authority),
            'PATH': str(launcher) + os.pathsep + os.environ.get('PATH', os.defpath)}


def server_arguments(arguments):
    """Create the display cookie before exec, not after the server is ready."""
    authority = os.environ.get('HICS_XWAYLAND_AUTHORITY')
    if not authority:
        return arguments
    info = Path(authority).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError('Unsafe HICS Xauthority file')
    if not arguments or not re.fullmatch(r':[0-9]+', arguments[0]) or '-auth' in arguments:
        raise ValueError('Unexpected XWayland display or duplicate -auth')
    # Keep the cookie out of argv, logs and shell commands.
    subprocess.run(['/usr/bin/xauth', '-q', '-f', authority],
                   input=f'add {arguments[0]} MIT-MAGIC-COOKIE-1 {secrets.token_hex(16)}\n',
                   text=True, stdout=subprocess.DEVNULL, check=True, timeout=5)
    return [*arguments, '-auth', authority, '-nolisten', 'tcp']


def allow_root():
    """Equivalent to xhost +SI:localuser:root; keep access control enabled."""
    class Host(ctypes.Structure):
        _fields_ = [('family', ctypes.c_int), ('length', ctypes.c_int), ('address', ctypes.c_char_p)]
    class ServerInterpreted(ctypes.Structure):
        _fields_ = [('typelength', ctypes.c_int), ('valuelength', ctypes.c_int),
                    ('type', ctypes.c_char_p), ('value', ctypes.c_char_p)]
    x11 = ctypes.CDLL('libX11.so.6')
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XAddHost.argtypes = [ctypes.c_void_p, ctypes.POINTER(Host)]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(None)
    if not display:
        raise ValueError('Cannot connect to XWayland to authorize local root')
    try:
        address = ServerInterpreted(9, 4, b'localuser', b'root')
        host = Host(5, ctypes.sizeof(address), ctypes.cast(ctypes.pointer(address), ctypes.c_char_p))
        x11.XAddHost(display, ctypes.byref(host))
        x11.XSync(display, 0)
    finally:
        x11.XCloseDisplay(display)


if __name__ == '__main__':
    try:
        allow_root()
    except (OSError, ValueError) as error:
        raise SystemExit('hics XWayland authorization: ' + str(error))
