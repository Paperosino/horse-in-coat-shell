#!/usr/bin/env python3
"""Profile real SettingsWindow lifetimes in an isolated process inside the VM.

Uses private HOME/XDG/D-Bus/audio, installed read-only QML/runtime, and real
parent Wayland rendering. Does not attach to/restart the desktop or touch its
settings. Heaptrack records from process start; optional ASan module overlay
is test-only. This is lifecycle/render coverage, not all settings actions.
"""
import argparse
import json
import hashlib
import os
from pathlib import Path
import socket
import signal
import subprocess
import tempfile
import time

QML = '''import QtQuick
import Quickshell
import qs.modules.nexus
ShellRoot {
 id:root
 property var current:null
 property int index:0
 property int phase:0
 property int waits:0
 property bool grabbed:false
 property var pages:["network","audio","storage","clipboard","display","configuration-history"]
 Component {id:factory;SettingsWindow {}}
 function find(item,name) {
  if(item.objectName===name)return item;
  for(const child of item.children??[]){const result=find(child,name);if(result)return result;}
  return null;
 }
 Timer {
  interval:200;repeat:true;running:true
  onTriggered:{
   if(root.phase===0){
    if(root.index>=CYCLES){console.log("PROFILE_COMPLETE",root.index);Qt.quit();return;}
    root.current=factory.createObject(root,{pageId:root.pages[root.index%root.pages.length],visible:true});
    if(!root.current){console.error("PROFILE_FAIL create");Qt.exit(1);return;}
    root.phase=1;root.waits=0;root.grabbed=false;
   }else if(root.phase===1){
    const container=root.find(root.current.contentItem,"PageContainer");
    if(!container || !container.children.length){if(++root.waits>50){console.error("PROFILE_FAIL page");Qt.exit(1);}return;}
    root.phase=2;
    if(!container.grabToImage(result=>{root.grabbed=true;})){
     console.error("PROFILE_FAIL grab");Qt.exit(1);
    }
   }else if(root.phase===2){
    if(!root.grabbed){if(++root.waits>50){console.error("PROFILE_FAIL frame");Qt.exit(1);}return;}
    root.current.destroy();root.current=null;root.index++;root.phase=0;
    console.log("PROFILE_CYCLE",root.index);
   }
  }
 }
}
'''


def stop(process):
    if process is not None and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--disposable-cachyos-vm', action='store_true', required=True)
    p.add_argument('--cycles', type=int, default=60)
    p.add_argument('--page', choices=['network', 'audio', 'storage', 'clipboard', 'display', 'configuration-history'], help='Repeat one real page to isolate its lifetime')
    p.add_argument('--mode', choices=['normal', 'heaptrack', 'asan'], default='normal')
    p.add_argument('--asan-overlay', type=Path)
    p.add_argument('--shell-overlay', type=Path, help='Test-only QML overrides, copied into the private shell tree')
    p.add_argument('--qml-fixture', type=Path, help='Minimal Qt lifetime fixture; use PROFILE_COMPLETE and CYCLES tokens')
    p.add_argument('--extra-import', type=Path, help='Explicit test-only QML diagnostic module directory')
    p.add_argument('--runtime', type=Path, default=Path('/usr/share/hics/qs'))
    p.add_argument('--executable', type=Path, help='Immutable test QS binary; installed runtime is retained')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert os.getuid() == 1000 and Path('/etc/hostname').read_text().strip() == 'hics-test'
    assert subprocess.check_output(['systemd-detect-virt'], text=True).strip() in ('qemu', 'kvm')
    if not 1 <= a.cycles <= 500 or a.output.exists():
        p.error('Use 1..500 cycles and a fresh output path')
    if Path('/var/lib/pacman/db.lck').exists():
        p.error('Finish the package transaction before profiling immutable modules')
    if a.mode == 'asan' and not a.asan_overlay and not a.qml_fixture:
        p.error('An instrumented module overlay is required')
    overlay_manifest = {}
    if a.asan_overlay:
        a.asan_overlay = a.asan_overlay.resolve(strict=True)
        manifest_path = a.asan_overlay / 'manifest.json'
        if manifest_path.stat().st_size > 1024 * 1024: p.error('Overlay manifest is too large')
        overlay_manifest = json.loads(manifest_path.read_text())
        for name, digest in overlay_manifest.items():
            relative = Path(name)
            target = a.asan_overlay / relative
            if relative.is_absolute() or '..' in relative.parts or target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(a.asan_overlay):
                p.error('Invalid overlay file')
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                p.error('Overlay checksum mismatch: ' + name)
    a.output.mkdir(parents=True, mode=0o700)
    display = Path(os.environ['WAYLAND_DISPLAY'])
    if not display.is_absolute():
        display = Path(os.environ['XDG_RUNTIME_DIR']) / display
    with socket.socket(socket.AF_UNIX) as connection:
        connection.connect(str(display))
    with tempfile.TemporaryDirectory(prefix='hics-settings-profile-') as directory:
        root = Path(directory)
        shell = root / 'shell'
        shell.mkdir()
        def link_tree(source, destination, overlay):
            for entry in source.iterdir():
                if destination == shell and entry.name == 'shell.qml': continue
                override = overlay / entry.name if overlay else None
                target = destination / entry.name
                if override and override.is_symlink(): raise ValueError('QML overlay must contain regular files')
                if override and override.is_dir():
                    if not entry.is_dir(): raise ValueError('QML overlay directory mismatch')
                    target.mkdir()
                    link_tree(entry, target, override)
                elif override and override.is_file():
                    if entry.suffix != '.qml': raise ValueError('Only QML overrides are supported')
                    target.write_bytes(override.read_bytes())
                else: target.symlink_to(entry, target_is_directory=entry.is_dir())
        link_tree(Path('/usr/share/hics/shell'), shell, a.shell_overlay)
        fixture = a.qml_fixture.read_text() if a.qml_fixture else QML
        if a.page:
            if a.qml_fixture: p.error('--page is for the built-in settings fixture')
            fixture = fixture.replace('["network","audio","storage","clipboard","display","configuration-history"]', json.dumps([a.page]))
        (shell / 'shell.qml').write_text(fixture.replace('CYCLES', str(a.cycles)))
        (root / 'run').mkdir(mode=0o700)
        config = root / 'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' + str(root) +
            '</listen><policy context="default"><allow send_destination="*"/>'
            '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus = subprocess.Popen(['dbus-daemon', '--nofork', '--print-address=1', '--config-file=' + str(config)], stdout=subprocess.PIPE, text=True, start_new_session=True)
        process = None
        try:
            address = bus.stdout.readline().strip()
            assert address
            env = dict(os.environ, HOME=str(root), XDG_RUNTIME_DIR=str(root / 'run'),
                XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'),
                XDG_STATE_HOME=str(root / 'state'), XDG_CACHE_HOME=str(root / 'cache'),
                WAYLAND_DISPLAY=str(display), DBUS_SESSION_BUS_ADDRESS=address,
                DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'absent'), LANG='ru_RU.UTF-8',
                PIPEWIRE_REMOTE='hics-profile-absent', PULSE_SERVER='unix:' + str(root / 'absent-pulse'),
                LD_LIBRARY_PATH=str(a.runtime / 'lib') + ':/usr/share/hics/qml/Hyprstack/lib:/usr/share/hics/lib',
                QT_PLUGIN_PATH=str(a.runtime / 'lib/qt6/plugins'), QML_IMPORT_PATH='/usr/share/hics/qml:' + str(a.runtime / 'lib/qt6/qml'),
                QML2_IMPORT_PATH='/usr/share/hics/qml:' + str(a.runtime / 'lib/qt6/qml'))
            if a.extra_import:
                env['QML_IMPORT_PATH'] = str(a.extra_import) + ':' + env['QML_IMPORT_PATH']
                env['QML2_IMPORT_PATH'] = env['QML_IMPORT_PATH']
            for key in ('LD_PRELOAD', 'LSAN_OPTIONS', 'ASAN_OPTIONS'):
                env.pop(key, None)
            if a.mode == 'asan':
                env['LD_PRELOAD'] = '/usr/lib/libasan.so.8'
                env['ASAN_OPTIONS'] = 'detect_leaks=1:halt_on_error=1'
                if a.asan_overlay:
                    env['LD_LIBRARY_PATH'] = str(a.asan_overlay / 'lib') + ':' + env['LD_LIBRARY_PATH']
                    env['QML_IMPORT_PATH'] = str(a.asan_overlay / 'qml') + ':' + env['QML_IMPORT_PATH']
                    env['QML2_IMPORT_PATH'] = env['QML_IMPORT_PATH']
            executable = a.executable or a.runtime / 'bin/hics-qs'
            command = [str(executable), '-p', str(shell), '--no-duplicate']
            if a.mode == 'heaptrack':
                command = ['heaptrack', '--record-only', '-o', str(a.output / 'heaptrack'), *command]
            with (a.output / 'process.log').open('w') as log:
                process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
                asan_mapped = False
                mapped_libraries = []
                if a.mode == 'asan' and a.asan_overlay:
                    deadline = time.monotonic() + 15
                    while process.poll() is None and time.monotonic() < deadline:
                        maps = Path('/proc') / str(process.pid) / 'maps'
                        loaded = maps.read_text()
                        mapped_libraries = [name for name in overlay_manifest
                            if name.startswith('lib/') and str(a.asan_overlay / name) in loaded]
                        expected_libraries = [name for name in overlay_manifest if name.startswith('lib/')]
                        asan_mapped = bool(expected_libraries) and len(mapped_libraries) == len(expected_libraries)
                        if asan_mapped:
                            break
                        time.sleep(.1)
                    assert asan_mapped, 'Expected instrumented render modules were not mapped'
                process.wait(timeout=30 + a.cycles * 5)
            text = (a.output / 'process.log').read_text()
            report = {'executableSha256': hashlib.sha256(executable.read_bytes()).hexdigest(), 'runtime': str(a.runtime), 'code': process.returncode, 'cycles': a.cycles, 'mode': a.mode,
                'asanModulesMapped': asan_mapped, 'asanLibrariesMapped': mapped_libraries, 'asanOverlayFiles': overlay_manifest, 'complete': 'PROFILE_COMPLETE ' + str(a.cycles) in text,
                'extraImportFiles': {str(p.relative_to(a.extra_import)): hashlib.sha256(p.read_bytes()).hexdigest() for p in a.extra_import.rglob('*') if p.is_file()} if a.extra_import else {},
                'qmlOverrides': {str(p.relative_to(a.shell_overlay)): hashlib.sha256(p.read_bytes()).hexdigest() for p in a.shell_overlay.rglob('*.qml')} if a.shell_overlay else {},
                'page': a.page, 'fixtureSha256': hashlib.sha256(a.qml_fixture.read_bytes()).hexdigest() if a.qml_fixture else None,
                'scope': 'Custom isolated Qt lifetime fixture' if a.qml_fixture else 'Isolated real settings windows with rendered grabs; not the whole desktop or every control'}
            (a.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
            assert report['code'] == 0 and report['complete'], text[-5000:]
        finally:
            stop(process)
            stop(bus)


if __name__ == '__main__':
    main()
