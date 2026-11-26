"""Refresh a surviving portal only when it belongs to another desktop identity."""
import os
from pathlib import Path
import subprocess


def refresh():
    expected = os.environ["XDG_CURRENT_DESKTOP"]
    reply = subprocess.run(["systemctl", "--user", "show", "xdg-desktop-portal.service",
                            "--property=MainPID", "--value"], check=True,
                           capture_output=True, text=True, timeout=5)
    pid = int(reply.stdout.strip() or "0")
    if pid <= 0:
        return  # D-Bus activation will use the environment just imported.
    try:
        environment = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    except FileNotFoundError:
        return  # It exited; its replacement inherits the new environment.
    current = next((value.split(b"=", 1)[1].decode() for value in environment
                    if value.startswith(b"XDG_CURRENT_DESKTOP=")), "")
    if current == expected:
        return
    # This is session startup, before restoring desktop applications. Shell
    # restarts with the same identity leave existing portal sessions intact.
    subprocess.run(["systemctl", "--user", "try-restart", "xdg-desktop-portal.service"],
                   check=True, timeout=30)


if __name__ == "__main__":
    refresh()
