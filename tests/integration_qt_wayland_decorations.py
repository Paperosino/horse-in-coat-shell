#!/usr/bin/env python3
"""Real CSD/frameless OpenGL transitions on a private headless Weston in the VM.

Never connects to the real session bus or restarts the desktop. The diagnostic
Weston debug/capture interface is confined to a private mode0700 runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import time


def stop(process):
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def receive(process, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert process.poll() is None, 'OpenGL probe exited before reporting a frame'
        ready, _, _ = select.select([process.stdout], [], [], min(.2, deadline-time.monotonic()))
        if ready:
            line = process.stdout.readline()
            if line.startswith('{'):
                return json.loads(line)
            if not line:
                raise AssertionError('OpenGL probe closed its output')
    raise TimeoutError('OpenGL probe did not finish its frame sequence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-runtime', type=Path, default=Path('/usr/share/hics/qs'))
    parser.add_argument('--candidate-runtime', required=True, type=Path)
    parser.add_argument('--reference-runtime', type=Path, help='Unmodified runtime for supported static decorated/frameless reference frames')
    parser.add_argument('--probe-binary', required=True, type=Path)
    parser.add_argument('--threaded-quick', action='store_true', help='Require Qt Quick rendering on its render thread')
    parser.add_argument('--scale-factor', type=float, choices=(1., 1.25, 2.), default=1.)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--disposable-cachyos-vm', required=True, action='store_true')
    args = parser.parse_args()
    assert os.getuid() == 1000 and Path('/etc/hostname').read_text().strip() == 'hics-test'
    assert subprocess.check_output(['systemd-detect-virt'], text=True).strip() in ('kvm', 'qemu')
    if args.output.exists():
        parser.error('Use a fresh evidence directory')
    root = args.output.resolve()
    root.mkdir(mode=0o700)
    runtime = root / 'run'
    runtime.mkdir(mode=0o700)
    (root / 'weston.ini').write_text('[shell]\npanel-position=none\nbackground-color=0xff1d1d2e\nlocking=false\nanimation=none\nstartup-animation=none\nfocus-animation=none\n')
    env = dict(PATH=os.environ['PATH'], LANG='C.UTF-8', HOME=str(root),
               XDG_CONFIG_HOME=str(root/'config'), XDG_RUNTIME_DIR=str(runtime),
               WAYLAND_DISPLAY='hics-csd-test', QT_SCALE_FACTOR=str(args.scale_factor), QSG_RENDER_LOOP='threaded', DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'absent-bus'),
               DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'absent-system-bus'))
    record = {'probeSha256': sha(args.probe_binary), 'cases': [], 'status': 'running',
              'scaleFactor': args.scale_factor, 'threadedQuickRequired': args.threaded_quick,
              'scope': 'Private Weston software EGL; actual composited CSD and content, not every GPU or input button'}
    def save():
        (root/'result.json').write_text(json.dumps(record, indent=2)+'\n')
    save()
    server = None
    client = None
    try:
        with (root/'weston.log').open('w') as log:
            server = subprocess.Popen(['weston', '--backend=headless', '--renderer=gl', '--width=640', '--height=480',
                                       '--socket=hics-csd-test', '--idle-time=0', '--debug', '--config='+str(root/'weston.ini')],
                                      env=env, stdout=log, stderr=log)
            deadline = time.monotonic()+12
            while not (runtime/'hics-csd-test').exists():
                assert server.poll() is None, 'Private Weston startup failed'
                assert time.monotonic() < deadline, 'Private Wayland socket did not become ready'
                time.sleep(.05)
            variants = [('baseline', args.baseline_runtime, False), ('candidate', args.candidate_runtime, False)]
            if args.reference_runtime:
                variants = [('reference-frameless', args.reference_runtime, False),
                            ('reference-csd', args.reference_runtime, True)] + variants
            for label, qt, initially_decorated in variants:
                plugin = (qt/'lib/qt6/plugins/wayland-graphics-integration-client/libqt-plugin-wayland-egl.so').resolve(strict=True)
                wayland = (qt/'lib/libQt6WaylandClient.so.6').resolve(strict=True)
                for api, expected_type in [('gl', 1), ('gles', 2)]:
                    case = root/(label+'-'+api)
                    case.mkdir(mode=0o700)
                    qenv = dict(env, LD_LIBRARY_PATH=str(qt/'lib'), QT_QPA_PLATFORM='wayland',
                                QT_QPA_PLATFORMTHEME='', QT_PLUGIN_PATH=str(qt/'lib/qt6/plugins'))
                    entry = {'label': label, 'api': api, 'pluginSha256': sha(plugin),
                             'waylandClientSha256': sha(wayland), 'frames': []}
                    record['cases'].append(entry)
                    with (case/'client.log').open('w') as client_log:
                        command = [str(args.probe_binary), api, str(case)]
                        if initially_decorated:
                            command.append('decorated')
                        client = subprocess.Popen(command, env=qenv,
                                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=client_log,
                                                  text=True, bufsize=1)
                        phases = [(0, None, initially_decorated)] if label.startswith('reference-') else [
                            (0, None, False), (1, 'decorate', True), (2, 'frameless', False), (3, 'decorate', True)]
                        for phase, command, decorated in phases:
                            if command:
                                client.stdin.write(command+'\n')
                                client.stdin.flush()
                            frame = receive(client)
                            entry['frames'].append(frame)
                            save()
                            assert frame['phase'] == phase and frame['frames'] == 5, frame
                            assert frame['contextValid'] and frame['glError'] == 0 and frame['renderableType'] == expected_type, frame
                            if args.threaded_quick:
                                assert frame.get('renderThreaded') is True, frame
                            assert frame['decorated'] == decorated and frame['decorationImageSaved'] == decorated, frame
                            assert frame['configuredMaximized'] and (frame['xdgWidth'], frame['xdgHeight']) == (640, 480), frame
                            assert frame['contextId'] == entry['frames'][0]['contextId'], 'The application context was recreated'
                            maps = Path('/proc/'+str(client.pid)+'/maps').read_text()
                            assert str(plugin) in maps, 'Expected EGL plugin was not mapped'
                            assert str(wayland) in maps, 'Expected Wayland client library was not mapped'
                            (case/'maps.log').write_text(maps)
                            previous = set(root.glob('wayland-screenshot-*.png'))
                            capture = subprocess.run(['weston-screenshooter'], env=env, cwd=root,
                                                     capture_output=True, text=True, timeout=10)
                            assert capture.returncode == 0, capture.stderr
                            current = set(root.glob('wayland-screenshot-*.png'))
                            fresh = current-previous
                            # Weston filenames have second resolution. Move each completed
                            # capture away before requesting another one in the same second.
                            assert len(fresh) == 1, 'Expected exactly one composited frame'
                            image = fresh.pop()
                            target = case/('screen-'+str(phase)+'.png')
                            shutil.move(image, target)
                            frame['screenSha256'] = sha(target)
                            save()
                        client.stdin.write('quit\n')
                        client.stdin.flush()
                        assert client.wait(timeout=8) == 0
                        client = None
                    save()
            from PIL import Image, ImageChops
            comparisons = []
            for api in ['gl', 'gles']:
                for phase in range(4):
                    before = Image.open(root/('baseline-'+api)/('screen-'+str(phase)+'.png')).convert('RGBA')
                    after = Image.open(root/('candidate-'+api)/('screen-'+str(phase)+'.png')).convert('RGBA')
                    assert before.size == after.size
                    difference = ImageChops.difference(before, after)
                    maximum = max(high for _, high in difference.getextrema())
                    comparisons.append({'api': api, 'phase': phase, 'maxChannelDifference': maximum})
                    assert maximum == 0, comparisons[-1]
                    if args.reference_runtime:
                        reference = root/('reference-'+('csd' if phase % 2 else 'frameless')+'-'+api)/'screen-0.png'
                        expected = Image.open(reference).convert('RGBA')
                        assert expected.size == after.size
                        delta = ImageChops.difference(expected, after)
                        maximum = max(high for _, high in delta.getextrema())
                        comparisons.append({'api': api, 'phase': phase, 'againstUnmodifiedStaticReference': True,
                                            'maxChannelDifference': maximum})
                        assert maximum == 0, comparisons[-1]
            record['comparisons'] = comparisons
            record['status'] = 'passed'
            save()
            print(json.dumps(record, indent=2))
    except BaseException:
        record['status'] = 'failed'
        save()
        raise
    finally:
        stop(client)
        stop(server)


if __name__ == '__main__':
    main()
