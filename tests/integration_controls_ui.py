#!/usr/bin/env python3
"""Construct shortcut help and switch layouts in an isolated nested session."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from integration_support import require_wayland_session

require_wayland_session()
repo = Path(__file__).resolve().parents[1]
base = Path(tempfile.mkdtemp(prefix="hyprstack-controls-ui-"))
shell = base / "shell"
shutil.copytree(repo / "shell", shell, ignore=shutil.ignore_patterns("plugin", "extras", "__pycache__"))
(base / "native").mkdir()
for name, source in (("hics-bars.so", repo / "build/hics-bars.so"),
        ("libspatialoverview.so", repo / "build/third_party/phantomat/libspatialoverview.so")):
    shutil.copy2(source, base / "native" / name)
(base / "config/hics").mkdir(parents=True)
(base / "config/hics/layouts.json").write_text('{"mode":"scrolling"}')
config = repo / "shell/assets/hyprland/config"
(base / "test.lua").write_text("package.path = " + json.dumps(str(config / "?.lua") + ";") + " .. package.path\n"
    + 'package.preload["scheme.current"] = function() return require("scheme.default") end\n'
    + 'hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n'
    + "dofile(" + json.dumps(str(config / "hyprland/animations.lua")) + ")\n"
    + "dofile(" + json.dumps(str(config / "hyprland/gestures.lua")) + ")\n"
    + "dofile(" + json.dumps(str(repo / "shell/assets/hyprland/layouts.lua")) + ")\n")
(shell / "shell.qml").write_text('''import QtQuick
import Quickshell
import qs.modules
import qs.services
ShellRoot {
 ShortcutHelp { id: help }
 property int phase: 0
 Timer {
  interval: 600; running: true; repeat: true
  onTriggered: {
   if (phase === 0) { help.toggle(); console.log("CONTROLS_HELP_OPEN"); phase=1; }
   else if (phase === 1) { LayoutModes.select("canvas"); phase=2; }
   else if (phase === 2 && !LayoutModes.busy && LayoutModes.mode === "canvas") {
    console.log("CONTROLS_CANVAS_SELECTED"); LayoutModes.select("scrolling"); phase=3;
   } else if (phase === 3 && !LayoutModes.busy && LayoutModes.mode === "scrolling") {
    console.log("CONTROLS_SCROLLING_SELECTED"); help.opened=false; phase=4;
   } else if (phase === 4) { console.log("CONTROLS_UI_OK"); Qt.quit(); }
  }
 }
 Timer { interval: 15000; running:true; onTriggered: {console.error("CONTROLS_TIMEOUT");Qt.quit();} }
}''')
env = dict(os.environ, AQ_BACKEND="wayland", HYPRSTACK_NESTED="1", HYPRSTACK_DATA_DIR=str(base),
    HYPRSTACK_SHELL_DIR=str(shell), XDG_CONFIG_HOME=str(base / "config"),
    XDG_STATE_HOME=str(base / "state"), XDG_DATA_HOME=str(base / "data"))
env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
env.pop("HYPRSTACK_TITLEBAR_PLUGIN", None)
nested = child = None
try:
    with (base / "compositor.log").open("w") as log:
        nested = subprocess.Popen(["Hyprland", "--config", str(base / "test.lua")], env=env, stdout=log, stderr=subprocess.STDOUT)
    instance = None
    for _ in range(80):
        if nested.poll() is not None:
            raise RuntimeError("Nested compositor exited during startup")
        values = subprocess.check_output(["hyprctl", "instances", "-j"], text=True).strip()
        instances = [] if values in ("", "]") else json.loads(values)
        instance = next((item for item in instances if item["pid"] == nested.pid), None)
        if instance:
            break
        time.sleep(.1)
    assert instance, "Nested compositor did not start"
    time.sleep(1)
    subprocess.run(["hyprctl", "-i", instance["instance"], "plugin", "load", str(base / "native/libspatialoverview.so")], check=True)
    appenv = dict(env, QT_QPA_PLATFORM="wayland", WAYLAND_DISPLAY=instance["wl_socket"],
        HYPRLAND_INSTANCE_SIGNATURE=instance["instance"], QML_IMPORT_PATH=str(repo / "build/qml"),
        QML2_IMPORT_PATH=str(repo / "build/qml"), LD_LIBRARY_PATH="/usr/share/hics/qs/lib")
    with (base / "shell.log").open("w") as log:
        child = subprocess.Popen(["/usr/share/hics/qs/bin/hics-qs", "-p", str(shell)], env=appenv, stdout=log, stderr=subprocess.STDOUT)
        result = child.wait(timeout=22)
    output = (base / "shell.log").read_text()
    print(output[-7000:])
    assert result == 0 and "CONTROLS_UI_OK" in output, "Shortcut help or layout switching failed"
    assert not any(error in output for error in ("ERROR:", "TypeError:", "ReferenceError:", "Unable to assign", "CONTROLS_TIMEOUT")), "QML runtime errors"
    print("PASS: shortcut help constructs and follows canvas/scrolling mode changes")
finally:
    if child and child.poll() is None:
        child.terminate(); child.wait(timeout=5)
    if nested and nested.poll() is None:
        nested.terminate(); nested.wait(timeout=5)
    print("UI test logs:", base)
    if nested and nested.returncode not in (0, -15):
        raise RuntimeError(f"Nested compositor exited with {nested.returncode}")
