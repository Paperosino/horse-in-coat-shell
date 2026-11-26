"""Reconcile portal owners after importing the current compositor environment."""
import json
import os
from pathlib import Path
import subprocess


def refresh_unit(unit, keys, recover_failed=False):
    reply = subprocess.run(["systemctl", "--user", "show", unit,
                            "--property=MainPID", "--property=ActiveState"], check=True,
                           capture_output=True, text=True, timeout=5)
    state = dict(line.split("=", 1) for line in reply.stdout.splitlines() if "=" in line)
    pid = int(state.get("MainPID", "0"))
    stale = False
    if pid > 0:
        try:
            values = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        except FileNotFoundError:
            return
        environment = dict(value.split(b"=", 1) for value in values if b"=" in value)
        stale = any(environment.get(key.encode()) != os.environ[key].encode()
                    for key in keys if key in os.environ)
    failed = recover_failed and state.get("ActiveState") == "failed"
    if not stale and not failed:
        return  # Preserve matching owners and lazy activation of inactive units.
    if recover_failed:
        # Socket existence alone is not readiness. Confirm the current compositor
        # answers with configured outputs before recovering its portal backend.
        reply = subprocess.run(["hyprctl", "-j", "monitors"], check=True,
                               capture_output=True, text=True, timeout=5)
        if not any(m.get("width", 0) > 0 for m in json.loads(reply.stdout)):
            raise RuntimeError("Cannot recover portal before compositor outputs are ready")
        subprocess.run(["systemctl", "--user", "reset-failed", unit], check=True, timeout=5)
    subprocess.run(["systemctl", "--user", "restart" if failed else "try-restart", unit],
                   check=True, timeout=30)


def refresh():
    session = ("WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE")
    refresh_unit("xdg-desktop-portal-hyprland.service", session, recover_failed=True)
    refresh_unit("xdg-desktop-portal.service", ("XDG_CURRENT_DESKTOP", *session))


if __name__ == "__main__":
    refresh()
