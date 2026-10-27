#!/usr/bin/env python3
"""Run one desktop session and clean up its processes on compositor disconnect."""
from __future__ import annotations
import fcntl
import json
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
    return Path(runtime) / ("hics-session-" + signature), Path(runtime) / "hypr" / signature / ".socket2.sock"


def stop_child_groups(children, session_disconnected=False):
    """Stop shell leaders on reload; groups belong to the entire login session."""
    for child in reversed(children):
        try:
            if session_disconnected:
                os.killpg(child.pid, signal.SIGTERM)
            elif child.poll() is None:
                child.terminate()
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    for child in reversed(children):
        try:
            child.wait(timeout=max(.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for child in reversed(children):
        try:
            if session_disconnected:
                os.killpg(child.pid, signal.SIGKILL)
            elif child.poll() is None:
                child.kill()
        except ProcessLookupError:
            pass
        child.wait()


def load_capture_plugin(name="hics-capture"):
    data = Path(os.environ.get("HICS_DATA_DIR", os.environ.get("HYPRSTACK_DATA_DIR", "/usr/share/hics")))
    plugin = data / ("native/" + name + ".so")
    if not plugin.is_file() or not shutil.which("hyprctl"):
        return
    try:
        listed = subprocess.run(["hyprctl", "-j", "plugin", "list"], capture_output=True, text=True, timeout=5, check=True)
        if any(item.get("name") == name for item in json.loads(listed.stdout)):
            return
        result = subprocess.run(["hyprctl", "plugin", "load", str(plugin)], capture_output=True, text=True, timeout=10)
        if result.returncode or result.stdout.strip() != "ok":
            print("Unable to load " + name + ":", result.stdout.strip(), result.stderr.strip(), file=sys.stderr)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("Unable to load " + name + ":", error, file=sys.stderr)


def prepare_session():
    """Independent recovery/accessibility jobs overlap palette preparation.

    All jobs finish before QML starts; rollback protection is never deferred.
    Each child has its own deadline and cannot survive a failed preflight.
    """
    from appearance_themes import STATE, session_environment
    jobs = [("accessibility", "accessibility_manager.py", "startup", 20),
            ("display protection", "display_profiles.py", "status", 20),
            ("configuration recovery", "configuration_manager.py", "status", 20)]
    if STATE.is_file():
        os.environ.update(session_environment())
        jobs.append(("appearance", "appearance_themes.py", "restore", 35))
    pending = []
    try:
        for label, script, operation, timeout in jobs:
            try:
                child = subprocess.Popen([sys.executable, str(Path(__file__).with_name(script)), operation],
                                         stdout=subprocess.DEVNULL, start_new_session=True)
                pending.append((label, child, time.monotonic() + timeout))
            except OSError as error:
                print("Unable to initialize " + label + ":", error, file=sys.stderr)
        from gtk_theme import restore as restore_gtk_theme
        try:
            restore_gtk_theme()
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            print("Unable to restore GTK dialog colours:", error, file=sys.stderr)
        for label, child, deadline in pending:
            try:
                result = child.wait(timeout=max(.01, deadline - time.monotonic()))
                if result:
                    print("Unable to initialize " + label + ": exit", result, file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("Unable to initialize " + label + ": timed out", file=sys.stderr)
    finally:
        for _, child, _ in pending:
            if child.poll() is None:
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            child.wait()
    os.environ["QT_QPA_PLATFORMTHEME"] = "hics"
    os.environ["QT_QUICK_CONTROLS_CONF"] = str(Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"hics/qtquickcontrols2.conf")


def session_wait_timeout(safe_mode, theme_at, capture_at, health_at, now):
    # Recovery mode has no background theme/capture/health jobs. Wake only on
    # compositor events, termination or SIGCHLD, even after days of uptime.
    if safe_mode: return None
    return max(0, min(theme_at, capture_at, health_at if health_at is not None else theme_at) - now)


def run_session():
    started = time.monotonic()
    lockpath, eventpath = paths()
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
        transition = 0
        session_disconnected = False
        try:
            import shell_recovery
            safe_mode = shell_recovery.begin()
            if safe_mode:
                os.environ['HICS_SAFE_MODE'] = '1'
                os.environ['QT_QPA_PLATFORMTHEME'] = ''
                os.environ['QT_QUICK_CONTROLS_CONF'] = ''
                os.environ['QT_QUICK_CONTROLS_STYLE'] = 'Basic'
                recovery_data=Path(os.environ.get('HICS_DATA_DIR',os.environ.get('HYPRSTACK_DATA_DIR','/usr/share/hics')))
                os.environ['FONTCONFIG_FILE']=str(recovery_data/'shell/recovery/fonts.conf')
            else:
                prepare_session()
            try: startup_candidate = None if safe_mode else shell_recovery.candidate()
            except (OSError,ValueError): startup_candidate = None
            print(f"hics startup: preparation {time.monotonic()-started:.3f}s", flush=True)
            # The native shell service owns clipboard capture and its privacy policy.
            from extension_recovery import begin as begin_extensions, finish as finish_extensions
            begin_extensions()
            shell = subprocess.Popen(["hics-shell"], start_new_session=True)
            children.append(shell)
            with selectors.DefaultSelector() as selector:
                selector.register(event, selectors.EVENT_READ)
                selector.register(readfd, selectors.EVENT_READ)
                done = False
                next_theme_sync = time.monotonic() + (86400 if safe_mode else 30)
                capture_load_at = time.monotonic() + 3
                capture_loaded = safe_mode
                health_at = time.monotonic() + 30 if startup_candidate is not None else None
                while not done:
                    if shell.poll() is not None:
                        result = shell.returncode
                        if result in (75,76):
                            transition=result
                            try:record=shell_recovery.read(shell_recovery.RECORD)
                            except ValueError:record={}
                            record.update(requested=result==75,active=False,failures=[])
                            from feature_common import atomic_json
                            atomic_json(shell_recovery.RECORD,record,private=True)
                            result=0
                        break
                    if health_at is not None and time.monotonic() >= health_at:
                        health_at = None
                        data = Path(os.environ.get('HICS_DATA_DIR', os.environ.get('HYPRSTACK_DATA_DIR','/usr/share/hics')))
                        try:
                            reply = subprocess.run([str(data/'qs/bin/hics-qs'),'ipc','-p',os.environ.get('HICS_SHELL_DIR',os.environ.get('HYPRSTACK_SHELL_DIR',str(data/'shell'))),'call','sessionHealth','ready'],capture_output=True,text=True,timeout=2)
                            if reply.returncode == 0 and reply.stdout.strip() == 'true': shell_recovery.healthy(startup_candidate)
                        except (OSError,ValueError,subprocess.SubprocessError) as error:
                            print('Unable to record startup checkpoint:',error,file=sys.stderr)
                    if not capture_loaded and time.monotonic() >= capture_load_at:
                        load_capture_plugin()
                        load_capture_plugin("hics-motion")
                        capture_loaded = True
                    if not safe_mode and time.monotonic() >= next_theme_sync:
                        from gtk_theme import sync_new_flatpaks
                        try:
                            sync_new_flatpaks()
                        except (OSError, ValueError, KeyError) as error:
                            print("Unable to sync new Flatpak themes:", error, file=sys.stderr)
                        next_theme_sync = time.monotonic() + 30
                    for key, mask in selector.select(timeout=session_wait_timeout(safe_mode, next_theme_sync, capture_load_at if not capture_loaded else next_theme_sync, health_at, time.monotonic())):
                        if key.fileobj is event:
                            if not event.recv(65536):
                                session_disconnected = True
                                done = True
                        else:
                            signals = os.read(readfd, 4096)
                            if signal.SIGTERM in signals or signal.SIGINT in signals:
                                done = True
        except BaseException:
            result=1
            raise
        finally:
            stop_child_groups(children, session_disconnected)
            if 'shell_recovery' in locals():
                try: shell_recovery.finish(result)
                except (OSError,ValueError) as error: print('Unable to record shell exit:',error,file=sys.stderr)
            if "finish_extensions" in locals():
                finish_extensions(result)
            if session_disconnected and shutil.which("hics-workspace"):
                subprocess.run(["hics-workspace","cleanup"],timeout=5,check=False)
            event.close()
            signal.set_wakeup_fd(previous_fd)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            os.close(readfd); os.close(writefd)
        return transition or result


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
                for lockpath in Path(runtime).glob("hics-session-*"):
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
        environment_keys=('HICS_SAFE_MODE','FONTCONFIG_FILE','QT_QUICK_CONTROLS_STYLE',
                          'QT_QPA_PLATFORMTHEME','QT_QUICK_CONTROLS_CONF')
        original_environment={key:os.environ.get(key) for key in environment_keys}
        while True:
            result=run_session()
            if result not in (75,76):return result
            # begin() reads the committed mode. Do not carry safe-only toolkit
            # environment into a normal startup in this same runner process.
            for key,value in original_environment.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("hics-session: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
