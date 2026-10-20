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
