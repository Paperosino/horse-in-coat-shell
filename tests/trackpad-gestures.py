#!/usr/bin/env python3
"""Exercise trackpad navigation in a private nested Hyprland and Quickshell.

Run inside a Wayland session, with installed Hyprstack QML modules:
  dbus-run-session -- python3 tests/trackpad-gestures.py --plugin /path/to/hyprstack-bars.so
Events enter InputManager through a test plugin; no physical input is injected.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main(prefix, plugin):
    base = Path(tempfile.mkdtemp(prefix="hs-g-"))
    home, runtime, shell = base / "home", base / "r", base / "shell"
    runtime.mkdir(mode=0o700)
    config = home / ".config"
    shutil.copytree(ROOT / "shell/assets/hyprland/config", config / "hypr")
    shutil.copytree(ROOT / "distribution/defaults/hyprstack", config / "hyprstack")
    (config / "hyprstack/hypr-user.lua").write_text(
        "dofile(" + json.dumps(str(ROOT / "shell/assets/hyprland/layouts.lua")) + ")\n"
        'hl.monitor({output="",mode="1280x800@60",position="auto",scale=1})\n'
        'hl.config({input={follow_mouse=0},misc={disable_autoreload=true,mouse_move_focuses_monitor=false}})\n')
    entry = base / "hyprland.lua"
    entry.write_text(
        'package.path=package.path..";' + str(config / "hypr/?.lua") + '"\n'
        'local on=hl.on; hl.on=function(name,callback) if name~="hyprland.start" then return on(name,callback) end end\n'
        "dofile(" + json.dumps(str(config / "hypr/hyprland.lua")) + ")\nhl.on=on\n")
    shell.mkdir()
    for name in ("assets", "components", "modules", "services", "utils", "shell.qml"):
        (shell / name).symlink_to(ROOT / "shell" / name)
    parent = Path(os.environ["WAYLAND_DISPLAY"])
    if not parent.is_absolute():
        parent = Path(os.environ["XDG_RUNTIME_DIR"]) / parent
    data = prefix.resolve() / "share/hyprstack"
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(config), XDG_RUNTIME_DIR=str(runtime),
        XDG_DATA_HOME=str(home / ".local/share"), XDG_STATE_HOME=str(home / ".local/state"),
        XDG_CACHE_HOME=str(home / ".cache"), WAYLAND_DISPLAY=str(parent), AQ_DRM_DEVICES="/dev/null",
        AQ_WAYLAND_NUM_OUTPUTS="2", LIBGL_ALWAYS_SOFTWARE="1", QT_QPA_PLATFORM="wayland",
        QML_IMPORT_PATH=str(data / "qml"), QML2_IMPORT_PATH=str(data / "qml"),
        HYPRSTACK_DATA_DIR=str(data), HYPRSTACK_LIB_DIR=str(data / "lib"),
        HYPRSTACK_SHELL_DIR=str(shell), HYPRSTACK_NESTED="1", HYPRSTACK_TITLEBAR_PLUGIN=str(plugin.resolve()))
    for key in ("DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"):
        env.pop(key, None)
    processes, logs = [], []

    def spawn(name, command):
        log = (base / (name + ".log")).open("w")
        logs.append(log)
        process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        processes.append(process)
        return process

    def run(command):
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, (command, result.stdout, result.stderr)
        return result.stdout.strip()

    def until(check, label, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if value := check():
                return value
            time.sleep(.04)
        raise AssertionError("Timeout: " + label)

    def evaluate(code):
        assert run(["hyprctl", "eval", code]) == "ok", code

    def state():
        return json.loads(run(["hyprctl", "repl", "return hl.plugin.gesture_input.state() "]))

    def overview():
        return json.loads(run(["qs", "-p", str(shell), "ipc", "call", "overview", "state"]))

    def send(phase, fingers=3, x=0, y=0, cancelled=False):
        evaluate("hl.plugin.gesture_input.send(" + ",".join(map(json.dumps, (phase, fingers, x, y, cancelled))) + ")")
        time.sleep(.05)

    def swipe(fingers, x, y, cancelled=False, steps=5):
        send("begin", fingers)
        for _ in range(steps):
            send("update", fingers, x, y)
        send("end", fingers, cancelled=cancelled)

    def settle():
        time.sleep(.45)

    fixture = base / "gesture-input.so"
    flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "hyprland", "lua5.4"], text=True))
    subprocess.run(["c++", "-std=c++23", "-shared", "-fPIC", "-O1", "-fno-gnu-unique", *flags,
        str(ROOT / "tests/gesture-input.cpp"), "-o", str(fixture)], check=True)
    try:
        spawn("compositor", ["Hyprland", "-c", str(entry)])
        socket = until(lambda: next((runtime / "hypr").glob("*/.socket.sock"), None), "compositor socket")
        env["HYPRLAND_INSTANCE_SIGNATURE"] = socket.parent.name
        env["WAYLAND_DISPLAY"] = str(until(lambda: next((p for p in runtime.glob("wayland-*") if not p.name.endswith(".lock")), None), "display"))
        for device in json.loads(run(["hyprctl", "-j", "devices"])).get("mice", []):
            evaluate("hl.device({name=" + json.dumps(device["name"]) + ",enabled=false})")
        run(["hyprctl", "plugin", "load", str(fixture)])
        assert not run(["hyprctl", "configerrors"]), run(["hyprctl", "configerrors"])
        run(["hyprctl", "output", "create", "headless"])
        until(lambda: len(json.loads(run(["hyprctl", "-j", "monitors"]))) == 2, "second monitor")
        spawn("shell", ["qs", "-p", str(shell), "--no-color"])
        until(lambda: subprocess.run(["qs", "-p", str(shell), "ipc", "show"], env=env, capture_output=True).returncode == 0, "shell")
        monitors = json.loads(run(["hyprctl", "-j", "monitors"]))
        assert len(monitors) == 2, monitors
        monitor, other = monitors
        evaluate("hyprstack_layouts.focus(1," + json.dumps(monitor["name"]) + ")")
        first_workspace = state()["workspace"]
        other_workspace = other["activeWorkspace"]["id"]
        for index in range(4):
            title = "Gesture fixture " + str(index)
            spawn("window-" + str(index), ["foot", "--app-id=gesture-fixture", "--title=" + title, "sh", "-c", "sleep 300"])
            until(lambda: title in state()["windows"], title)
        clients = json.loads(run(["hyprctl", "-j", "clients"]))
        first = next(c for c in clients if c["title"] == "Gesture fixture 0")
        last = next(c for c in clients if c["title"] == "Gesture fixture 3")
        evaluate('hl.dispatch(hl.dsp.window.move({window=' + json.dumps("address:" + last["address"]) + ',workspace=' + str(first_workspace + 1) + ',follow=false}))')
        evaluate('hl.dispatch(hl.dsp.focus({window=' + json.dumps("address:" + first["address"]) + '}))')
        settle()
        before = state()
        cursor = run(["hyprctl", "-j", "cursorpos"])
        send("begin")
        previous = before
        for delta in (-45, -45, -45, 30):
            send("update", x=delta)
            current = state()
            for title, window in current["windows"].items():
                if window["workspace"] != first_workspace:
                    continue
                assert abs(window["position"][0] - window["goal"][0]) < 1, current
                assert abs(window["position"][0] - previous["windows"][title]["position"][0] - delta) < 2, (delta, current, previous)
            previous = current
        time.sleep(.15)
        assert abs(state()["tape"] - previous["tape"]) < .001
        send("end", cancelled=True)
        settle()
        assert abs(state()["tape"] - before["tape"]) < .001, (before, state())
        swipe(3, -55, 0, steps=7)
        settle()
        assert json.loads(run(["hyprctl", "-j", "activewindow"]))["address"] != first["address"]
        assert run(["hyprctl", "-j", "cursorpos"]) == cursor, "Gesture warped the pointer"
        print("PASS continuous horizontal movement, reversal, cancellation, release snapping and fixed pointer", flush=True)

        send("begin")
        for _ in range(4):
            send("update", y=-50)
        current = state()
        assert current["workspace"] == first_workspace, current
        rows = current["workspaces"]
        assert -600 < rows[str(first_workspace)]["y"] < -100, current
        assert abs(rows[str(first_workspace + 1)]["y"] - rows[str(first_workspace)]["y"] - monitor["height"]) < 1, current
        frozen = rows[str(first_workspace)]["y"]
        time.sleep(.15)
        assert abs(state()["workspaces"][str(first_workspace)]["y"] - frozen) < 1
        send("update", y=60)
        assert state()["workspaces"][str(first_workspace)]["y"] > frozen + 30
        send("end", cancelled=True)
        settle()
        assert state()["workspace"] == first_workspace
        assert abs(state()["workspaces"][str(first_workspace)]["y"]) < 1
        swipe(3, 0, -60)
        settle()
        assert state()["workspace"] == first_workspace + 1, state()
        swipe(3, 0, 60)
        settle()
        assert state()["workspace"] == first_workspace, state()
        evaluate("hyprstack_layouts.focus(10," + json.dumps(monitor["name"]) + ")")
        settle()
        swipe(3, 0, -100)
        settle()
        assert state()["workspace"] == first_workspace + 9, state()
        assert next(m for m in json.loads(run(["hyprctl", "-j", "monitors"])) if m["name"] == other["name"])["activeWorkspace"]["id"] == other_workspace
        evaluate("hyprstack_layouts.focus(1," + json.dumps(monitor["name"]) + ")")
        settle()
        swipe(3, 0, 100)
        settle()
        assert state()["workspace"] == first_workspace, state()
        print("PASS continuous vertical movement, fixed row spacing, reversal, cancellation and monitor boundaries", flush=True)

        swipe(4, 0, -2)
        assert not overview()["active"]
        swipe(4, 0, -20, cancelled=True)
        assert not overview()["active"]
        swipe(4, 0, -20)
        until(lambda: overview()["active"] and overview()["renderer"]["active"], "overview opens")
        swipe(4, 0, -20)
        assert overview()["active"], "Opening gesture toggled overview off"
        desktop = state()
        swipe(3, -25, 0)
        assert abs(state()["tape"] - desktop["tape"]) < .001, "Overview scrolled the desktop"
        swipe(3, 0, -25)
        selected_workspace = overview()["workspace"]
        assert state()["workspace"] == desktop["workspace"], "Overview switched the hidden desktop"
        swipe(4, 0, 20, cancelled=True)
        assert overview()["active"]
        swipe(4, 0, 20)
        until(lambda: not overview()["active"], "overview closes")
        settle()
        assert state()["workspace"] == selected_workspace, (selected_workspace, state())
        swipe(4, 0, 20)
        assert not overview()["active"]
        print("PASS overview open/close, short and cancelled swipes, and navigation without background movement", flush=True)

        evaluate("hyprstack_layouts.toggle()")
        settle()
        before = state()
        swipe(3, -60, 0)
        swipe(3, 0, -60)
        assert state()["workspace"] == before["workspace"]
        assert state()["windows"] == before["windows"]
        swipe(4, 0, -20)
        until(lambda: overview()["active"], "stacking overview")
        swipe(4, 0, 20)
        until(lambda: not overview()["active"], "stacking overview closes")
        evaluate("hyprstack_layouts.toggle()")
        settle()
        run(["hyprctl", "reload"])
        settle()
        assert not run(["hyprctl", "configerrors"]), run(["hyprctl", "configerrors"])
        before = state()
        swipe(3, 0, -60)
        settle()
        assert state()["workspace"] == before["workspace"] + 1, (before, state())
        print("PASS stacking mode, restored scrolling gestures and configuration reload", flush=True)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        for log in logs:
            log.close()
        print("Artifacts:", base, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local")
    parser.add_argument("--plugin", type=Path, required=True, help="Native module built from this checkout")
    args = parser.parse_args()
    main(args.prefix, args.plugin)
