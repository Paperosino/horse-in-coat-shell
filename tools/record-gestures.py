#!/usr/bin/env python3
"""Record real Hyprstack responses to emulated trackpad events in a private session.

Requires installed Hyprstack QML modules, foot, wf-recorder and a native plugin
built from this checkout. No kernel input devices or host windows are recorded.
  dbus-run-session -- python3 tools/record-gestures.py --plugin /path/to/hyprstack-bars.so
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def window(index):
    pages = [
        ("ЗАМЕТКИ", "#01", "Планы на сегодня", ["Подготовить материалы", "Разобрать заметки", "Закончить наброски"]),
        ("ПРОЕКТ", "#02", "Рабочий проект", ["Макет интерфейса", "Цвета и типографика", "Следующая итерация"]),
        ("ПАЛИТРА", "#03", "Kanagawa", ["Crystal blue", "Spring green", "Stone white"]),
        ("ВТОРОЙ СТОЛ", "#04", "Чтение", ["Собрать ссылки", "Записать новые идеи", "Вернуться к задачам"]),
    ]
    name, number, title, lines = pages[index]
    accents = ["111;178;212", "169;174;209", "152;187;108", "230;195;132"]
    accent = "\033[38;2;" + accents[index] + "m"
    print("\033[2J\033[H\033[?25l", end="")
    print("\n\n  " + accent + name + " " * 7 + number + "\033[0m")
    print("\n  " + "─" * 32)
    print("\n\n  " + accent + title + "\033[0m\n\n")
    for line in lines:
        print("  · " + line + "\n\n")
    print("\n  " + accent + "●  ●  ●  ●  ●  ●  ●  ●" + "\033[0m\n")
    sys.stdout.flush()
    time.sleep(180)


def main(args):
    base = args.work_dir or Path(tempfile.mkdtemp(prefix="hs-v-"))
    base.mkdir(parents=True, exist_ok=True)
    if (base / "capture.mkv").exists():
        raise FileExistsError("Refusing to overwrite an existing capture")
    home, runtime, shell = base / "home", base / "r", base / "shell"
    runtime.mkdir(mode=0o700)
    config = home / ".config"
    shutil.copytree(ROOT / "shell/assets/hyprland/config", config / "hypr")
    shutil.copytree(ROOT / "distribution/defaults/hyprstack", config / "hyprstack")
    (config / "hyprstack/hypr-user.lua").write_text(
        "dofile(" + json.dumps(str(ROOT / "shell/assets/hyprland/layouts.lua")) + ")\n"
        'hl.config({input={follow_mouse=0},misc={disable_autoreload=true,mouse_move_focuses_monitor=false}})\n')
    (config / "hyprstack/shell.json").write_text('{"general":{"apps":{"terminal":["foot"]}}}')
    sys.path.insert(0, str(ROOT / "shell/assets"))
    import theme_manager
    scheme = next(s for s in theme_manager.builtins() if "kanagawa" in s["id"])
    variant = next(v for v in scheme["variants"] if v["mode"] == "dark")
    palette = home / ".local/state/hyprstack/scheme.json"
    palette.parent.mkdir(parents=True)
    palette.write_text(json.dumps(dict(name=scheme["id"], flavour=variant["flavour"], mode="dark",
        variant="tonalspot", colours=variant["colours"])))
    entry = base / "hyprland.lua"
    entry.write_text('package.path=package.path..";' + str(config / "hypr/?.lua") + '"\n'
        'local on=hl.on; hl.on=function(name,fn) if name~="hyprland.start" then return on(name,fn) end end\n'
        "dofile(" + json.dumps(str(config / "hypr/hyprland.lua")) + ")\nhl.on=on\n")
    shell.mkdir()
    for name in ("assets", "components", "modules", "services", "utils", "shell.qml"):
        (shell / name).symlink_to(ROOT / "shell" / name)
    parent = Path(os.environ["WAYLAND_DISPLAY"])
    if not parent.is_absolute():
        parent = Path(os.environ["XDG_RUNTIME_DIR"]) / parent
    data = args.prefix.resolve() / "share/hyprstack"
    trace = base / "gesture.json"
    trace.write_text('{"phase":"idle","fingers":0,"x":0,"y":0,"label":"Жесты тачпада","emulated":true}')
    env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(runtime), XDG_CONFIG_HOME=str(config),
        XDG_DATA_HOME=str(home / ".local/share"), XDG_STATE_HOME=str(home / ".local/state"),
        XDG_CACHE_HOME=str(home / ".cache"), WAYLAND_DISPLAY=str(parent), AQ_DRM_DEVICES="/dev/null",
        LIBGL_ALWAYS_SOFTWARE="1", QT_QPA_PLATFORM="wayland", QML_IMPORT_PATH=str(data / "qml"),
        QML2_IMPORT_PATH=str(data / "qml"), HYPRSTACK_DATA_DIR=str(data), HYPRSTACK_LIB_DIR=str(data / "lib"),
        HYPRSTACK_SHELL_DIR=str(shell), HYPRSTACK_NESTED="1", HYPRSTACK_TITLEBAR_PLUGIN=str(args.plugin.resolve()),
        HYPRSTACK_GESTURE_TRACE=str(trace))
    env["QS_NO_RELOAD_POPUP"] = "1"
    for key in ("DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"):
        env.pop(key, None)
    processes, logs, timeline = [], [], []

    def spawn(name, command):
        log = (base / (name + ".log")).open("w")
        logs.append(log)
        process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
        processes.append(process)
        return process

    def run(command):
        p = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
        assert p.returncode == 0, (command, p.stdout, p.stderr)
        return p.stdout.strip()

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

    fixture = base / "gesture-input.so"
    flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "hyprland", "lua5.4"], text=True))
    subprocess.run(["c++", "-std=c++23", "-shared", "-fPIC", "-O1", "-fno-gnu-unique", *flags,
        str(ROOT / "tests/gesture-input.cpp"), "-o", str(fixture)], check=True)
    try:
        compositor = spawn("compositor", ["Hyprland", "-c", str(entry)])
        sock = until(lambda: next((runtime / "hypr").glob("*/.socket.sock"), None), "compositor")
        env["HYPRLAND_INSTANCE_SIGNATURE"] = sock.parent.name
        env["WAYLAND_DISPLAY"] = str(until(lambda: next((p for p in runtime.glob("wayland-*") if not p.name.endswith(".lock")), None), "display"))
        for device in json.loads(run(["hyprctl", "-j", "devices"])).get("mice", []):
            evaluate("hl.device({name=" + json.dumps(device["name"]) + ",enabled=false})")
        run(["hyprctl", "plugin", "load", str(fixture)])
        # Size only the newly created nested-compositor window on the host.
        # NVIDIA GBM headless buffers are unavailable on some recording hosts.
        def host_window():
            p = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True, text=True, timeout=10)
            return next((c for c in json.loads(p.stdout or "[]") if c["pid"] == compositor.pid), None)
        outer = until(host_window, "nested window")
        address = json.dumps("address:" + outer["address"])
        subprocess.run(["hyprctl", "eval", 'hl.dispatch(hl.dsp.window.float({window=' + address + ',action="enable"})); '
            'hl.dispatch(hl.dsp.window.resize({window=' + address + ',x=1280,y=800,relative=false}))'], check=True, capture_output=True, text=True)
        time.sleep(.5)
        output = json.loads(run(["hyprctl", "-j", "monitors"]))[0]["name"]
        env["HYPRSTACK_DEMO_OUTPUT"] = output
        evaluate('hl.monitor({output=' + json.dumps(output) + ',mode="1280x800@60",position="auto",scale=1})')
        evaluate('hyprstack_layouts.focus(1,' + json.dumps(output) + ')')
        workspace = state()["workspace"]
        spawn("shell", ["qs", "-p", str(shell), "--no-color"])
        until(lambda: subprocess.run(["qs", "-p", str(shell), "ipc", "show"], env=env, capture_output=True).returncode == 0, "shell")
        for drawer in ("utilities", "osd", "dashboard", "launcher", "sidebar", "session"):
            if run(["qs", "-p", str(shell), "ipc", "call", "drawers", "isOpen", drawer]) == "true":
                run(["qs", "-p", str(shell), "ipc", "call", "drawers", "toggle", drawer])
        foot_config = base / "foot.ini"
        foot_config.write_text('[main]\nfont=Noto Sans Mono:size=13\npad=18x18\n[colors-dark]\nbackground=1f1f28\nforeground=dcd7ba\n')
        titles = ["Заметки", "Проект", "Палитра", "Чтение"]
        for index, title in enumerate(titles):
            spawn("window-" + str(index), ["foot", "--config=" + str(foot_config), "--app-id=gesture-demo",
                "--title=" + title, "python3", str(Path(__file__).resolve()), "--window", str(index)])
            until(lambda: title in state()["windows"], "demo window")
        clients = json.loads(run(["hyprctl", "-j", "clients"]))
        first = next(c for c in clients if c["title"] == titles[0])
        last = next(c for c in clients if c["title"] == titles[3])
        evaluate('hl.dispatch(hl.dsp.window.move({window=' + json.dumps("address:" + last["address"]) + ',workspace=' + str(workspace + 1) + ',follow=false}))')
        evaluate('hl.dispatch(hl.dsp.focus({window=' + json.dumps("address:" + first["address"]) + '}))')
        viz = ROOT / "tools/touchpad-visualizer.qml"
        spawn("visualizer", ["qs", "-p", str(viz), "--no-color"])
        until(lambda: subprocess.run(["qs", "-p", str(viz), "ipc", "call", "touchpad", "ready"], env=env, capture_output=True).returncode == 0, "visualizer")
        assert not run(["hyprctl", "configerrors"]), run(["hyprctl", "configerrors"])
        run(["hyprctl", "dismissnotify", "-1"])
        run(["qs", "-p", str(shell), "ipc", "call", "notifs", "clear"])
        time.sleep(6)
        run(["grim", "-o", output, str(base / "preview.png")])
        if args.preview_only:
            print("Preview:", base / "preview.png", flush=True)
            return
        recording = spawn("recorder", ["wf-recorder", "-o", output, "--no-dmabuf", "-D",
            "-c", "libx264", "-x", "yuv420p", "-p", "crf=18", "-p", "preset=veryfast", "-f", str(base / "capture.mkv")])
        until(lambda: (base / "capture.mkv").exists(), "recorder")
        started = time.monotonic()
        time.sleep(1)
        actions = [
            (3, -460, 0, 1.2, "Плавная прокрутка колонок", False),
            (3, 340, 0, 1.2, "Свайп в обратную сторону", False),
            (3, -240, 0, 1, "Отмена жеста · возврат", True),
            (3, 0, -340, 1.1, "Рабочие столы по вертикали", False),
            (3, 0, 340, 1.1, "Возвращаемся на первый стол", False),
            (4, 0, -140, .8, "Четыре пальца · открыть обзор", False),
            (3, -120, 0, .7, "Выбор окна в обзоре", False),
            (3, 0, -120, .7, "Выбор рабочего пространства", False),
            (4, 0, 140, .8, "Четыре пальца · закрыть обзор", False),
        ]
        for fingers, x, y, duration, label, cancelled in actions:
            before = state()
            timeline.append({"at": round(time.monotonic() - started, 3), "label": label, "fingers": fingers,
                "x": x, "y": y, "duration": duration, "cancelled": cancelled})
            evaluate("hl.plugin.gesture_input.replay(" + ",".join(json.dumps(v, ensure_ascii=False)
                for v in (fingers, x, y, duration, str(trace), label, cancelled)) + ")")
            until(lambda: not state()["replaying"], label)
            time.sleep(.8)
            after = state()
            if cancelled:
                assert abs(before["tape"] - after["tape"]) < .001, label
            elif fingers == 3 and y == -340:
                assert after["workspace"] == workspace + 1, after
            elif fingers == 3 and y == 340:
                assert after["workspace"] == workspace, after
            print("Recorded:", label, flush=True)
        time.sleep(.8)
        recording.send_signal(signal.SIGINT)
        assert recording.wait(timeout=15) == 0
        (base / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n")
        print("Capture:", base / "capture.mkv", flush=True)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait()
        for log in logs:
            log.close()
        print("Artifacts:", base, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, choices=range(4))
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local")
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args()
    if args.window is not None:
        window(args.window)
    elif args.plugin is None:
        parser.error("--plugin is required for recording")
    else:
        main(args)
