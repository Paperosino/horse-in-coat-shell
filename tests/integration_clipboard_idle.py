#!/usr/bin/env python3
"""Clipboard file watching must stay idle and lock contention must not stall Qt."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from PySide6.QtCore import QLockFile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-clipboard-idle-') as directory:
    base = Path(directory)
    config = base / 'config/hics'
    config.mkdir(parents=True)
    (config / 'workspace.json').write_text(json.dumps({'clipboard': {'enabled': False}}))
    history = base / 'state/hics/workspace/clipboard'
    history.mkdir(parents=True)
    index = history / 'index.json'
    index.write_text('{"entries":[]}')
    status = base / 'status.json'
    qml = base / 'test.qml'
    qml.write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Services
ShellRoot {
 id:root
 property int changes:0
 property int ticks:0
 Connections {target:ClipboardHistory;function onChanged(){root.changes++}}
 FileView {id:status;path:STATUS;printErrors:false}
 Timer {interval:40;running:true;repeat:true;onTriggered:{root.ticks++;status.setText(JSON.stringify({ticks:root.ticks,changes:root.changes,count:ClipboardHistory.entries.length,error:ClipboardHistory.error}))}}
}'''.replace('STATUS', json.dumps(str(status))))
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_CONFIG_HOME=str(base / 'config'), XDG_STATE_HOME=str(base / 'state'), XDG_DATA_HOME=str(base / 'data'), QML_IMPORT_PATH=str(ROOT / 'build/qml'), QML2_IMPORT_PATH=str(ROOT / 'build/qml'))
    env.pop('WAYLAND_DISPLAY', None)
    env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    log = (base / 'shell.log').open('w')
    process = subprocess.Popen(['quickshell', '-p', str(qml)], env=env, stdout=log, stderr=subprocess.STDOUT)
    def state():
        try: return json.loads(status.read_text())
        except (FileNotFoundError, json.JSONDecodeError): return {}
    def wait_for(condition):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            value = state()
            if condition(value): return value
            if process.poll() is not None: break
            time.sleep(.04)
        raise AssertionError((state(), (base / 'shell.log').read_text()))
    def replace_index(count):
        entries = []
        for n in range(count):
            identity = str(n + 1).zfill(64)
            (history / identity).write_text('fixture')
            entries.append({'id': identity, 'timestamp': int(time.time()), 'mime': 'text/plain', 'preview': 'fixture'})
        replacement = history / 'index.next'
        replacement.write_text(json.dumps({'entries': entries}))
        replacement.replace(index)
    try:
        wait_for(lambda s: s.get('changes', 0) > 0)
        time.sleep(.3)
        baseline = state()['changes']
        time.sleep(.75)
        assert state()['changes'] == baseline, ('Idle clipboard refresh loop', baseline, state())
        print('PASS: clipboard stays idle despite its own lock file changes', flush=True)
        lock = QLockFile(str(history / 'lock'))
        assert lock.tryLock(0)
        try:
            before = state()['ticks']
            replace_index(1)
            time.sleep(.65)
            assert state()['ticks'] - before >= 8, ('Clipboard lock blocked GUI heartbeat', before, state())
        finally:
            lock.unlock()
        wait_for(lambda s: s.get('count') == 1 and not s.get('error'))
        print('PASS: GUI remains responsive while a clipboard writer holds the lock', flush=True)
        replace_index(2)
        wait_for(lambda s: s.get('count') == 2 and not s.get('error'))
        time.sleep(.3)
        baseline = state()['changes']
        time.sleep(.6)
        assert state()['changes'] == baseline, ('Watch rearm caused refresh loop', state())
        print('PASS: repeated atomic index replacements update history and rearm the watch', flush=True)
    finally:
        process.terminate()
        process.wait(timeout=5)
