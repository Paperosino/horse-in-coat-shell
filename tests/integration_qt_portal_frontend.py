#!/usr/bin/env python3
"""Exercise Qt registration against the real portal frontend on a private bus.

No user portal is restarted and no permission dialog is requested. This verifies
Registry ordering and metadata resolution, not every portal backend operation.
"""
import argparse
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
    a = p.parse_args()
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
        frontend = None
        try:
            address = bus.stdout.readline().strip()
            assert address
            env = dict(os.environ, HOME=str(root), XDG_RUNTIME_DIR=str(root / 'run'),
                       XDG_DATA_HOME=str(root / 'data'), XDG_CONFIG_HOME=str(root / 'config'),
                       XDG_CACHE_HOME=str(root / 'cache'), XDG_CURRENT_DESKTOP='hics',
                       DBUS_SESSION_BUS_ADDRESS=address, DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'absent'),
                       LD_LIBRARY_PATH=str(a.runtime / 'lib'),
                       QT_PLUGIN_PATH=str(a.runtime / 'lib/qt6/plugins'), QT_QPA_PLATFORM='offscreen',
                       QT_LOGGING_RULES='qt.qpa.services.debug=true', QT_FORCE_STDERR_LOGGING='1',
                       HICS_QT_REQUIRED_PREFIX=str(a.runtime))
            with (root / 'portal.log').open('w') as log:
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
            report = {'status': 'passed', 'scope': 'Real frontend Registry, private bus, three Qt services; no backend dialogs',
                      'qt': result.stderr, 'portal': (root / 'portal.log').read_text()}
            a.output.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
        finally:
            stop(frontend)
            stop(bus)


if __name__ == '__main__':
    main()
