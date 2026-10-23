#!/usr/bin/env python3
"""Install the system helper from a staged user build into root-owned paths.

The desktop updater stays unprivileged. Only this explicit installation step
runs with sudo; the service never executes a binary in the user's home.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def deployment(prefix):
    prefix = Path(prefix)
    for name in ('hics-systemd', 'hics-systemctl', 'hics-memory'):
        yield Path('/usr/local/bin') / name, (prefix / 'bin' / name).read_bytes(), 0o755
    unit = (ROOT / 'distribution/systemd/system/hics-system.service').read_text().replace('/usr/bin/hics-systemd', '/usr/local/bin/hics-systemd')
    activation = (ROOT / 'distribution/dbus/org.hics.System1.service').read_text().replace('/usr/bin/hics-systemd', '/usr/local/bin/hics-systemd')
    yield Path('/etc/systemd/system/hics-system.service'), unit.encode(), 0o644
    memory_unit = (ROOT / 'distribution/systemd/system/hics-memory.service').read_text().replace('/usr/bin/hics-memory', '/usr/local/bin/hics-memory')
    yield Path('/etc/systemd/system/hics-memory.service'), memory_unit.encode(), 0o644
    yield Path('/usr/local/share/dbus-1/system-services/org.hics.System1.service'), activation.encode(), 0o644
    yield Path('/etc/dbus-1/system.d/org.hics.System1.conf'), (ROOT / 'distribution/dbus/org.hics.System1.conf').read_bytes(), 0o644
    yield Path('/usr/share/polkit-1/actions/org.hics.system.policy'), (ROOT / 'distribution/polkit/org.hics.system.policy').read_bytes(), 0o644


def install(prefix):
    if os.geteuid() != 0:
        raise ValueError('Run this step with sudo')
    files = list(deployment(prefix))  # Validate every source before writing.
    for destination, content, mode in files:
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        for parent in (destination.parent, *destination.parent.parents):
            st = parent.stat()
            if parent.is_symlink() or st.st_uid != 0 or st.st_mode & 0o022:
                raise ValueError('System installation directory is not secure: ' + str(parent))
        fd, temporary = tempfile.mkstemp(prefix='.hyprstack-', dir=destination.parent)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(content); out.flush(); os.fsync(out.fileno())
                os.fchown(out.fileno(), 0, 0); os.fchmod(out.fileno(), mode)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    Path('/etc/hics').mkdir(parents=True, exist_ok=True)
    Path('/etc/systemd/zram-generator.conf.d').mkdir(parents=True, exist_ok=True)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'reload', 'dbus.service'], check=True)
    subprocess.run(['systemctl', 'enable', 'hics-system.service'], check=True)
    subprocess.run(['systemctl', 'restart', 'hics-system.service'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'hics-memory.service'], check=True)
    print('System helper installed, enabled and started.')


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Usage: sudo python3 distribution/install_system_helper.py STAGED_PREFIX')
        install(sys.argv[1])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('System helper installation failed:', error, file=sys.stderr)
        sys.exit(1)
