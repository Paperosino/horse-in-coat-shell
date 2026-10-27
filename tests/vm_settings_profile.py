#!/usr/bin/env python3
"""Profile real SettingsWindow lifetimes in an isolated process inside the VM.

Uses private HOME/XDG/D-Bus/audio, installed read-only QML/runtime, and real
parent Wayland rendering. Does not attach to/restart the desktop or touch its
settings. Heaptrack records from process start; optional ASan module overlay
is test-only. This is lifecycle/render coverage, not all settings actions.
"""
import argparse
import json
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
    p.add_argument('--mode', choices=['normal', 'heaptrack', 'asan'], default='normal')
    p.add_argument('--asan-overlay', type=Path)
    p.add_argument('--runtime', type=Path, default=Path('/usr/share/hics/qs'))
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert os.getuid() == 1000 and Path('/etc/hostname').read_text().strip() == 'hics-test'
    assert subprocess.check_output(['systemd-detect-virt'], text=True).strip() in ('qemu', 'kvm')
    if not 1 <= a.cycles <= 500 or a.output.exists():
        p.error('Use 1..500 cycles and a fresh output path')
    if Path('/var/lib/pacman/db.lck').exists():
        p.error('Finish the package transaction before profiling immutable modules')
    if a.mode == 'asan' and not a.asan_overlay:
        p.error('An instrumented module overlay is required')
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
        for source in Path('/usr/share/hics/shell').iterdir():
            if source.name != 'shell.qml':
                (shell / source.name).symlink_to(source, target_is_directory=source.is_dir())
        (shell / 'shell.qml').write_text(QML.replace('CYCLES', str(a.cycles)))
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
                QT_PLUGIN_PATH=str(a.runtime / 'lib/qt6/plugins'), QML_IMPORT_PATH='/usr/share/hics/qml',
                QML2_IMPORT_PATH='/usr/share/hics/qml')
            for key in ('LD_PRELOAD', 'LSAN_OPTIONS', 'ASAN_OPTIONS'):
                env.pop(key, None)
            if a.mode == 'asan':
                env['LD_PRELOAD'] = '/usr/lib/libasan.so.8'
                env['ASAN_OPTIONS'] = 'detect_leaks=1:halt_on_error=1'
                env['LD_LIBRARY_PATH'] = str(a.asan_overlay / 'lib') + ':' + env['LD_LIBRARY_PATH']
                env['QML_IMPORT_PATH'] = str(a.asan_overlay / 'qml') + ':' + env['QML_IMPORT_PATH']
                env['QML2_IMPORT_PATH'] = env['QML_IMPORT_PATH']
            command = [str(a.runtime / 'bin/hics-qs'), '-p', str(shell), '--no-duplicate']
            if a.mode == 'heaptrack':
                command = ['heaptrack', '--record-only', '-o', str(a.output / 'heaptrack'), *command]
            with (a.output / 'process.log').open('w') as log:
                process = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
                asan_mapped = False
                if a.mode == 'asan':
                    deadline = time.monotonic() + 15
                    while process.poll() is None and time.monotonic() < deadline:
                        maps = Path('/proc') / str(process.pid) / 'maps'
                        loaded = maps.read_text()
                        asan_mapped = all(str(a.asan_overlay / 'lib' / name) in loaded
                            for name in ('libhyprstack-blobs.so', 'libhyprstack-components.so'))
                        if asan_mapped:
                            break
                        time.sleep(.1)
                    assert asan_mapped, 'Expected instrumented render modules were not mapped'
                process.wait(timeout=30 + a.cycles * 5)
            text = (a.output / 'process.log').read_text()
            report = {'code': process.returncode, 'cycles': a.cycles, 'mode': a.mode,
                'asanModulesMapped': asan_mapped, 'complete': 'PROFILE_COMPLETE ' + str(a.cycles) in text,
                'scope': 'Isolated real settings windows with rendered grabs; not the whole desktop or every control'}
            (a.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
            assert report['code'] == 0 and report['complete'], text[-5000:]
        finally:
            stop(process)
            stop(bus)


if __name__ == '__main__':
    main()
