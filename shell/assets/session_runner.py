#!/usr/bin/env python3
"""Run one desktop session and clean up its processes on compositor disconnect."""
from __future__ import annotations
import fcntl
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import time


def paths():
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if not runtime or not re.fullmatch(r"[A-Za-z0-9_.-]+", signature):
        raise ValueError("Run Hyprstack in a Hyprland Wayland session")
    return Path(runtime) / ("runhics-session-" + signature), Path(runtime) / "hypr" / signature / ".socket2.sock"


def stop_child_groups(children):
    """Stop owned helpers and their descendants, preserving detached apps."""
    for child in reversed(children):
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    for child in reversed(children):
        try:
            child.wait(timeout=max(.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    # A helper can exit before its subprocesses; clean the group even when the
    # original leader is gone. execDetached/QProcess::startDetached applications
    # start a new session and are outside these owned groups.
    for child in reversed(children):
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def run_session():
    lockpath, eventpath = paths()
    from gtk_theme import restore as restore_gtk_theme
    try:
        restore_gtk_theme()
    except (OSError, ValueError, KeyError) as error:
        print("Unable to restore GTK dialog colours:", error, file=sys.stderr)
    # Appearance is a user-session preference. Preserve it across sign-ins
    # for shell-launched GTK/Qt clients as well as compositor-launched clients.
    from appearance_themes import STATE, session_environment
    if STATE.is_file():
        os.environ.update(session_environment())
        subprocess.run([sys.executable, str(Path(__file__).with_name('appearance_themes.py')), 'restore'],
                       stdout=subprocess.DEVNULL, timeout=35, check=False)
    os.environ["QT_QPA_PLATFORMTHEME"] = "qt5ct:qt6ct"
    children = []
    event = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    event.connect(str(eventpath))
    with lockpath.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            event.close()
            return 0
        lock.seek(0); lock.truncate()
        lock.write(str(os.getpid())); lock.flush()
        os.chmod(lockpath, 0o600)
        readfd, writefd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        previous_fd = signal.set_wakeup_fd(writefd)
        previous = {}
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGCHLD):
            previous[sig] = signal.signal(sig, lambda signum, frame: None)
        result = 0
        try:
            # The shell owns the themed Polkit agent; only clipboard helpers
            # need separate processes.
            if shutil.which("wl-paste") and shutil.which("cliphist"):
                for kind in ("text", "image"):
                    children.append(subprocess.Popen(["wl-paste", "--type", kind, "--watch", "cliphist", "store"], start_new_session=True))
            shell = subprocess.Popen(["runhics-shell"], start_new_session=True)
            children.append(shell)
            with selectors.DefaultSelector() as selector:
                selector.register(event, selectors.EVENT_READ)
                selector.register(readfd, selectors.EVENT_READ)
                done = False
                next_theme_sync = time.monotonic() + 30
                while not done:
                    if shell.poll() is not None:
                        result = shell.returncode
                        break
                    if time.monotonic() >= next_theme_sync:
                        from gtk_theme import sync_new_flatpaks
                        try:
                            sync_new_flatpaks()
                        except (OSError, ValueError, KeyError) as error:
                            print("Unable to sync new Flatpak themes:", error, file=sys.stderr)
                        next_theme_sync = time.monotonic() + 30
                    for key, mask in selector.select(timeout=max(0, next_theme_sync - time.monotonic())):
                        if key.fileobj is event:
                            if not event.recv(65536):
                                done = True
                        else:
                            signals = os.read(readfd, 4096)
                            if signal.SIGTERM in signals or signal.SIGINT in signals:
                                done = True
        finally:
            stop_child_groups(children)
            event.close()
            signal.set_wakeup_fd(previous_fd)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            os.close(readfd); os.close(writefd)
        return result


def stop_session(lockpath):
    if not lockpath.exists():
        return
    with lockpath.open("r") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            pid = int(lock.read())
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
            if b"session_runner.py" not in cmdline:
                raise ValueError("Unexpected session lock owner")
            os.kill(pid, signal.SIGTERM)
            for _ in range(110):
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
                except BlockingIOError:
                    time.sleep(.05)
            raise ValueError("The previous session has not stopped")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "run"
    try:
        if action not in ("run", "start", "stop", "restart"):
            raise ValueError("Use run, start, stop or restart")
        if action == "stop" and not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            runtime = os.environ.get("XDG_RUNTIME_DIR")
            if runtime:
                for lockpath in Path(runtime).glob("runhics-session-*"):
                    stop_session(lockpath)
            return 0
        lockpath, eventpath = paths()
        if action in ("stop", "restart"):
            stop_session(lockpath)
        if action == "stop": return 0
        if action == "start":
            subprocess.Popen([sys.executable, __file__, "run"], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
        return run_session()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("runhics-session: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
