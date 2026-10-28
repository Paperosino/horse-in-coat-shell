#!/usr/bin/env python3
"""Exercise Qt registration against the real portal frontend on a private bus.

No user portal is restarted and no permission dialog is requested. This verifies
Registry ordering and metadata resolution, not every portal backend operation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from diagnose_qt_portal_registration import stop


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--probe-binary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--hyprland-backend', action='store_true', help='Also start a private Hyprland backend; requires parent Wayland/Hyprland environment')
    p.add_argument('--hyprland-backend-binary', type=Path, help='Use this explicit backend in the private test instead of the installed one')
    p.add_argument('--private-pipewire', action='store_true', help='Start a private PipeWire server for the private backend')
    p.add_argument('--gtk-backend', action='store_true', help='Also exercise Settings.ReadAll through an isolated real GTK backend')
    a = p.parse_args()
    if a.hyprland_backend_binary and not a.hyprland_backend:
        p.error('--hyprland-backend-binary requires --hyprland-backend')
    backend_binary = (a.hyprland_backend_binary or Path('/usr/lib/xdg-desktop-portal-hyprland')).resolve()
    if a.hyprland_backend:
        a.gtk_backend = True
        if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            p.error('Pass the disposable parent compositor signature explicitly')
    if a.gtk_backend and (not os.environ.get('WAYLAND_DISPLAY') or not os.environ.get('XDG_RUNTIME_DIR')):
        p.error('GTK backend needs the disposable parent Wayland environment')
    if a.output.exists():
        p.error('Use a fresh evidence path')
    with tempfile.TemporaryDirectory(prefix='hics-real-portal-') as directory:
        root = Path(directory)
        (root / 'run').mkdir(mode=0o700)
        apps = root / 'data/applications'
        apps.mkdir(parents=True)
        (apps / 'org.hics.PortalFixture.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=HICS portal fixture\nExec=' +
            str(a.probe_binary.resolve()) + '\nNoDisplay=true\n')
        config = root / 'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' + str(root) +
                         '</listen><policy context="default"><allow send_destination="*"/>'
                         '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus = subprocess.Popen(['dbus-daemon', '--nofork', '--print-address=1',
                                '--config-file=' + str(config)], stdout=subprocess.PIPE, text=True)
        frontend = backend = hyprland_backend = pipewire = None
        try:
            address = bus.stdout.readline().strip()
            assert address
            env = dict(os.environ, HOME=str(root), XDG_RUNTIME_DIR=str(root / 'run'),
                       XDG_DATA_HOME=str(root / 'data'), XDG_CONFIG_HOME=str(root / 'config'),
                       XDG_CACHE_HOME=str(root / 'cache'), XDG_STATE_HOME=str(root / 'state'),
                       XDG_DATA_DIRS='/usr/local/share:/usr/share', XDG_CURRENT_DESKTOP='hics',
                       DBUS_SESSION_BUS_ADDRESS=address, DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'absent'),
                       PIPEWIRE_RUNTIME_DIR=str(root / 'run'), PIPEWIRE_REMOTE='pipewire-0',
                       PULSE_SERVER='unix:' + str(root / 'absent-pulse'),
                       LD_LIBRARY_PATH=str(a.runtime / 'lib'),
                       QT_PLUGIN_PATH=str(a.runtime / 'lib/qt6/plugins'), QT_QPA_PLATFORM='offscreen',
                       QT_LOGGING_RULES='qt.qpa.services.debug=true', QT_FORCE_STDERR_LOGGING='1',
                       HICS_QT_REQUIRED_PREFIX=str(a.runtime))
            if a.gtk_backend:
                parent_display = os.environ.get('WAYLAND_DISPLAY', '')
                if not parent_display.startswith('/'):
                    parent_display = str(Path(os.environ['XDG_RUNTIME_DIR']) / parent_display)
                env['WAYLAND_DISPLAY'] = parent_display
                env['GSETTINGS_BACKEND'] = 'memory'
                portal_config = root / 'config/xdg-desktop-portal'
                portal_config.mkdir(parents=True)
                (portal_config / 'portals.conf').write_text('[preferred]\ndefault=' + ('hyprland;gtk' if a.hyprland_backend else 'gtk') + '\n')
            with (root / 'portal.log').open('w') as log:
                if a.private_pipewire:
                    pipewire = subprocess.Popen(['pipewire'], env=env, stdout=log, stderr=log)
                    deadline = time.monotonic() + 15
                    while not (root/'run/pipewire-0').exists():
                        assert pipewire.poll() is None and time.monotonic() < deadline, (root/'portal.log').read_text()
                        time.sleep(.05)
                if a.gtk_backend:
                    backend = subprocess.Popen(['/usr/lib/xdg-desktop-portal-gtk'], env=env, stdout=log, stderr=log)
                if a.hyprland_backend:
                    hyprland_backend = subprocess.Popen([str(backend_binary)], env=env, stdout=log, stderr=log)
                frontend = subprocess.Popen(['/usr/lib/xdg-desktop-portal', '--verbose'],
                                            env=env, stdout=log, stderr=log)
                deadline = time.monotonic() + 15
                while True:
                    result = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.portal.Desktop',
                        '--object-path', '/org/freedesktop/portal/desktop', '--method',
                        'org.freedesktop.DBus.Properties.Get', 'org.freedesktop.host.portal.Registry', 'version'],
                        env=env, capture_output=True, text=True, timeout=3)
                    if result.returncode == 0:
                        break
                    assert frontend.poll() is None and time.monotonic() < deadline, (root / 'portal.log').read_text()
                    time.sleep(.05)
                result = subprocess.run([str(a.probe_binary.resolve())], env=env,
                                        capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, result.stderr
                assert 'Successfully registered with host portal as' in result.stderr, result.stderr
                assert 'Failed to register with host portal' not in result.stderr, result.stderr
                assert result.stderr.count('Successfully registered with host portal as') == 1, result.stderr
                if a.gtk_backend:
                    settings = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.portal.Desktop',
                        '--object-path', '/org/freedesktop/portal/desktop', '--method',
                        'org.freedesktop.portal.Settings.ReadAll', '["org.freedesktop.appearance"]'],
                        env=env, capture_output=True, text=True, timeout=5)
                    assert settings.returncode == 0 and 'color-scheme' in settings.stdout, settings.stdout + settings.stderr
                    assert backend.poll() is None, 'GTK backend exited'
                if a.hyprland_backend:
                    assert hyprland_backend.poll() is None, 'Hyprland backend exited'
                    assert 'Providing portal org.freedesktop.portal.ScreenCast' in (root / 'portal.log').read_text()
                    if a.private_pipewire:
                        assert '[pipewire] connected' in (root / 'portal.log').read_text(), 'Backend did not connect to the private PipeWire server'
                        assert pipewire.poll() is None, 'Private PipeWire server exited'
            report = {'status': 'passed', 'scope': 'Real frontend Registry, private bus, three Qt services; no backend dialogs',
                      'gtkBackend': a.gtk_backend, 'hyprlandBackend': a.hyprland_backend, 'privatePipeWire': a.private_pipewire, 'qt': result.stderr, 'portal': (root / 'portal.log').read_text()}
            if a.hyprland_backend:
                with backend_binary.open('rb') as stream:
                    report['hyprlandBackendSha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
            a.output.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
        finally:
            stop(frontend)
            stop(backend)
            stop(hyprland_backend)
            stop(pipewire)
            stop(bus)


if __name__ == '__main__':
    main()
