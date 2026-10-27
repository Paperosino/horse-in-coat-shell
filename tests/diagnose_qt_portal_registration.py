#!/usr/bin/env python3
"""Audit Qt's host-portal registration on a private bus, without HICS services.

This is a diagnostic, not a passing regression for an unfixed dependency.
Reports an already running portal, D-Bus activation and owner restart. Exit 2
means duplicate registration or missing re-registration was observed. No real portal or user settings are used.
Requires matching Qt development/private headers, dbus-python and PyGObject.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

PROBE = r'''
#include <QGuiApplication>
#include <QTimer>
#include <QtGui/private/qdesktopunixservices_p.h>
int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    QGuiApplication::setDesktopFileName("org.hics.PortalFixture");
    QDesktopUnixServices services;
    QTimer::singleShot(2000, &app, &QCoreApplication::quit);
    return app.exec();
}
'''


def mock(trace, ready):
    import dbus
    import dbus.service
    import dbus.mainloop.glib
    from gi.repository import GLib
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = dbus.service.BusName('org.freedesktop.portal.Desktop', bus)

    class Portal(dbus.service.Object):
        seen = set()

        @dbus.service.method('org.freedesktop.DBus.Properties',
                             in_signature='ss', out_signature='v')
        def Get(self, interface, key):
            return dbus.UInt32(2)

        @dbus.service.method('org.freedesktop.host.portal.Registry',
                             in_signature='sa{sv}', sender_keyword='sender')
        def Register(self, app, options, sender=None):
            duplicate = sender in self.seen
            with trace.open('a') as stream:
                stream.write(json.dumps({'sender': sender, 'app': str(app), 'serverPid': os.getpid(),
                                         'duplicate': duplicate}) + '\n')
            if duplicate:
                raise dbus.exceptions.DBusException(
                    'Connection already associated with an application ID',
                    name='org.freedesktop.portal.Error.Failed')
            self.seen.add(sender)

    portal = Portal(bus, '/org/freedesktop/portal/desktop')
    ready.write_text('ready')
    GLib.MainLoop().run()


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def run_case(base, probe, active, runtime, restart=False):
    base.mkdir()
    services = base / 'services'
    services.mkdir()
    trace, ready = base / 'calls.jsonl', base / 'ready'
    command = [sys.executable, str(Path(__file__).resolve()), '--mock', str(trace), str(ready)]
    # D-Bus Exec quoting follows desktop Exec syntax, not shell evaluation.
    escaped = ' '.join('"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
                       for value in command)
    (services / 'org.freedesktop.portal.Desktop.service').write_text(
        '[D-BUS Service]\nName=org.freedesktop.portal.Desktop\nExec=' + escaped + '\n')
    config = base / 'bus.conf'
    config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' + str(base) +
                     '</listen><servicedir>' + str(services) + '</servicedir>'
                     '<policy context="default"><allow send_destination="*"/>'
                     '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    server = None
    with (base / 'bus.log').open('w') as log:
        bus = subprocess.Popen(['dbus-daemon', '--nofork', '--print-address=1',
                                '--config-file=' + str(config)],
                               stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            address = bus.stdout.readline().strip()
            assert address, 'Private bus did not start'
            env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=address,
                       DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(base / 'absent'),
                       QT_QPA_PLATFORM='offscreen', XDG_CURRENT_DESKTOP='hics',
                       QT_FORCE_STDERR_LOGGING='1', HOME=str(base),
                       XDG_CONFIG_HOME=str(base / 'config'),
                       XDG_CACHE_HOME=str(base / 'cache'), XDG_DATA_HOME=str(base / 'data'))
            if runtime:
                env['LD_LIBRARY_PATH'] = str(runtime / 'lib')
                env['QT_PLUGIN_PATH'] = str(runtime / 'lib/qt6/plugins')
            if active:
                server = subprocess.Popen(command, env=env, stdout=log, stderr=log)
                deadline = time.monotonic() + 5
                while not ready.exists():
                    assert server.poll() is None and time.monotonic() < deadline, 'Mock did not start'
                    time.sleep(.02)
            if restart:
                client = subprocess.Popen([str(probe)], env=env, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, text=True)
                try:
                    deadline = time.monotonic() + 1.2
                    while not trace.exists():
                        assert client.poll() is None and time.monotonic() < deadline, 'No initial registration'
                        time.sleep(.01)
                    # Allow the successful asynchronous reply to reach Qt before
                    # replacing the mock owner. Same bus and same client survive.
                    time.sleep(.15)
                    assert client.poll() is None
                    stop(server)
                    ready.unlink()
                    server = subprocess.Popen(command, env=env, stdout=log, stderr=log)
                    deadline = time.monotonic() + 1
                    while not ready.exists():
                        assert server.poll() is None and time.monotonic() < deadline, 'Replacement mock did not start'
                        time.sleep(.01)
                    stdout, stderr = client.communicate(timeout=6)
                    result = subprocess.CompletedProcess([str(probe)], client.returncode, stdout, stderr)
                finally:
                    stop(client)
            else:
                result = subprocess.run([str(probe)], env=env, capture_output=True,
                                        text=True, timeout=8)
            assert result.returncode == 0, result.stderr
            calls = [json.loads(line) for line in trace.read_text().splitlines()]
            assert calls and calls[0]['app'] == 'org.hics.PortalFixture', calls
            assert not calls[0]['duplicate'], calls
            return {'portalInitiallyActive': active, 'portalRestarted': restart,
                    'missingReregistration': restart and not any(call['serverPid'] == server.pid for call in calls),
                    'calls': calls, 'stderr': result.stderr,
                    'duplicate': any(call['duplicate'] for call in calls)}
        finally:
            stop(server)
            stop(bus)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--mock':
        mock(Path(sys.argv[2]), Path(sys.argv[3]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, help='Optional bundled qs directory (same Qt ABI)')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh evidence path')
    with tempfile.TemporaryDirectory(prefix='hics-portal-audit-') as directory:
        base = Path(directory)
        source, probe = base / 'probe.cpp', base / 'probe'
        source.write_text(PROBE)
        headers = Path(subprocess.check_output(['qmake6', '-query', 'QT_INSTALL_HEADERS'], text=True).strip())
        version = subprocess.check_output(['qmake6', '-query', 'QT_VERSION'], text=True).strip()
        includes = []
        for module in ('QtGui', 'QtCore'):
            root = headers / module / version
            includes.extend(['-I' + str(root), '-I' + str(root / module)])
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Gui', 'Qt6DBus'], text=True))
        subprocess.run(['c++', '-fPIC', '-std=c++20', str(source), *includes, *flags,
                        '-o', str(probe)], check=True, capture_output=True, text=True, timeout=30)
        cases = [run_case(base / name, probe, active, args.runtime)
                 for name, active in [('active', True), ('activated', False)]]
        cases.append(run_case(base / 'restarted', probe, True, args.runtime, restart=True))
        report = {'qtHeadersVersion': version, 'runtime': str(args.runtime) if args.runtime else 'system',
                  'scope': 'Real Qt services, mock portal registry, private D-Bus; not all portal functions',
                  'cases': cases}
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 2 if any(case['duplicate'] or case['missingReregistration'] for case in cases) else 0


if __name__ == '__main__':
    sys.exit(main())
