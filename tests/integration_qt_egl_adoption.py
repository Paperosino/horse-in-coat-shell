#!/usr/bin/env python3
"""Validate EGL native-context ownership/sharing on a private VM compositor.

Use the ASan fixture from fixtures/qt-wayland-probes. No sanitizers or
profilers are injected into the running shell; LSan stays enabled.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from integration_qt_wayland_decorations import sha, stop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, default=Path('/usr/share/hics/qs'))
    parser.add_argument('--probe-binary', type=Path, required=True)
    parser.add_argument('--video-probe-binary', type=Path)
    parser.add_argument('--video-qml', type=Path)
    parser.add_argument('--video-file', type=Path)
    parser.add_argument('--video-cycles', type=int, default=20)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--disposable-cachyos-vm', required=True, action='store_true')
    args = parser.parse_args()
    if any((args.video_probe_binary, args.video_qml, args.video_file)) and not all((args.video_probe_binary, args.video_qml, args.video_file)):
        parser.error('Video probe, QML and local media must be provided together')
    if not 1 <= args.video_cycles <= 100:
        parser.error('Use 1..100 video cycles')
    assert os.getuid() == 1000 and Path('/etc/hostname').read_text().strip() == 'hics-test'
    assert subprocess.check_output(['systemd-detect-virt'], text=True).strip() in ('kvm', 'qemu')
    if args.output.exists():
        parser.error('Use a fresh evidence directory')
    root = args.output.resolve()
    root.mkdir(mode=0o700)
    (root/'run').mkdir(mode=0o700)
    runtime = args.runtime.resolve(strict=True)
    env = dict(PATH=os.environ['PATH'], HOME=str(root), LANG='C.UTF-8',
               XDG_RUNTIME_DIR=str(root/'run'), WAYLAND_DISPLAY='hics-egl-adoption',
               XDG_CONFIG_HOME=str(root/'config'),
               DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'absent-bus'),
               DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'absent-system-bus'))
    report = {'status': 'running', 'probeSha256': sha(args.probe_binary), 'cases': [],
              'pluginSha256': sha(runtime/'lib/qt6/plugins/wayland-graphics-integration-client/libqt-plugin-wayland-egl.so')}
    def save():
        (root/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    save()
    server = None
    try:
        with (root/'weston.log').open('w') as log:
            server = subprocess.Popen(['weston', '--backend=headless', '--renderer=gl',
                                       '--socket=hics-egl-adoption', '--idle-time=0'],
                                      env=env, stdout=log, stderr=log)
            deadline = time.monotonic()+12
            while not (root/'run/hics-egl-adoption').exists():
                assert server.poll() is None, 'Private Weston startup failed'
                assert time.monotonic() < deadline, 'Private Wayland socket not ready'
                time.sleep(.05)
            qenv = dict(env, LD_LIBRARY_PATH=str(runtime/'lib'),
                        QT_PLUGIN_PATH=str(runtime/'lib/qt6/plugins'), QT_QPA_PLATFORM='wayland',
                        QT_QPA_PLATFORMTHEME='', QML_IMPORT_PATH=str(runtime/'lib/qt6/qml'),
                        QSG_RENDER_LOOP='threaded', PIPEWIRE_REMOTE='hics-video-absent',
                        PULSE_SERVER='unix:'+str(root/'absent-pulse'), ASAN_OPTIONS='detect_leaks=1:halt_on_error=1')
            for repeat in range(3):
                for api, expected in [('gl', 1), ('gles', 2)]:
                    path = root/(api+'-'+str(repeat)+'.log')
                    with path.open('w') as output:
                        result = subprocess.run([str(args.probe_binary), api], env=qenv,
                                                stdout=output, stderr=subprocess.STDOUT, timeout=25)
                    entry = {'api': api, 'repeat': repeat, 'returncode': result.returncode}
                    report['cases'].append(entry)
                    save()
                    assert result.returncode == 0, path.read_text()[-5000:]
                    lines = [line for line in path.read_text().splitlines() if line.startswith('{')]
                    assert len(lines) == 1, path.read_text()
                    entry['result'] = json.loads(lines[0])
                    data = entry['result']
                    assert data['ownerRetained'] and data['sharing'] and data['colorful'] and data['decoratedWindow'], data
                    assert data['glError'] == 0 and data['renderableType'] == expected, data
                    assert not any(word in path.read_text() for word in ('ERROR: AddressSanitizer', 'ERROR: LeakSanitizer'))
                    save()
            if args.video_probe_binary:
                path = root/'video-output.log'
                with path.open('w') as output:
                    result = subprocess.run([str(args.video_probe_binary), str(args.video_qml),
                                             str(args.video_file), str(root), str(args.video_cycles)],
                                            env=qenv, stdout=output, stderr=subprocess.STDOUT,
                                            timeout=15+args.video_cycles*10)
                report['video'] = {'returncode': result.returncode,
                                   'probeSha256': sha(args.video_probe_binary),
                                   'qmlSha256': sha(args.video_qml), 'mediaSha256': sha(args.video_file)}
                save()
                assert result.returncode == 0, path.read_text()[-5000:]
                lines = [line for line in path.read_text().splitlines() if line.startswith('{')]
                assert len(lines) == 1, path.read_text()[-5000:]
                data = report['video']['result'] = json.loads(lines[0])
                assert data['cycles'] == args.video_cycles and data['colorful'] and not data['errors'], data
                assert len(data['samples']) == args.video_cycles, data
                assert all(frame['frames'] >= 6 and frame['colors'] >= 5 for frame in data['samples']), data
                save()
        report['status'] = 'passed'
        save()
        print(json.dumps(report, indent=2))
    except BaseException:
        report['status'] = 'failed'
        save()
        raise
    finally:
        stop(server)


if __name__ == '__main__':
    main()
