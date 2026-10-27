#!/usr/bin/env python3
"""Exercise transient QML logging categories in a private offscreen QS process.

Always runs ASan with leak detection; does not connect to user portals, Wayland,
clipboard, audio or system D-Bus. No settings/desktop shell is loaded.
"""
import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

QML = '''import QtQuick
import Quickshell
ShellRoot {
 id:root
 property int count:0
 Component {id:category;LoggingCategory {}}
 Timer {
  interval:1;repeat:true;running:true
  onTriggered:{
   const c=category.createObject(root,{name:"quickshell.fixture.dynamic."+(root.count%8)});
   console.warn(c,"CATEGORY_LIFETIME",root.count);
   c.destroy();
   if(++root.count===200){stop();Qt.callLater(()=>{console.log("CATEGORIES_COMPLETE");Qt.quit();});}
  }
 }
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--executable', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--filter-one', action='store_true', help='Hide one transient category in sparse logs; detailed decode must retain it')
    a = p.parse_args()
    if a.output.exists():
        p.error('Use a fresh evidence path')
    with tempfile.TemporaryDirectory(prefix='hics-log-categories-') as d:
        root = Path(d)
        (root / 'run').mkdir(mode=0o700)
        (root / 'shell.qml').write_text(QML)
        config = root / 'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=' + str(root) +
            '</listen><policy context="default"><allow send_destination="*"/>'
            '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus = subprocess.Popen(['dbus-daemon', '--nofork', '--print-address=1', '--config-file=' + str(config)], stdout=subprocess.PIPE, text=True)
        try:
            address = bus.stdout.readline().strip()
            assert address
            env = dict(os.environ, HOME=str(root), XDG_RUNTIME_DIR=str(root / 'run'),
                XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'),
                XDG_STATE_HOME=str(root / 'state'), XDG_CACHE_HOME=str(root / 'cache'),
                DBUS_SESSION_BUS_ADDRESS=address, DBUS_SYSTEM_BUS_ADDRESS='unix:path=' + str(root / 'absent'),
                QT_QPA_PLATFORM='offscreen', QT_NO_XDG_DESKTOP_PORTAL='1', LANG='C.UTF-8',
                LD_LIBRARY_PATH=str(a.runtime / 'lib'), QT_PLUGIN_PATH=str(a.runtime / 'lib/qt6/plugins'),
                QML_IMPORT_PATH=str(a.runtime / 'lib/qt6/qml'), QML2_IMPORT_PATH=str(a.runtime / 'lib/qt6/qml'),
                LD_PRELOAD='/usr/lib/libasan.so.8', ASAN_OPTIONS='detect_leaks=1:halt_on_error=1')
            for key in ('LSAN_OPTIONS', 'WAYLAND_DISPLAY', 'HYPRLAND_INSTANCE_SIGNATURE'):
                env.pop(key, None)
            command = [str(a.executable or a.runtime / 'bin/hics-qs'), '-p', str(root / 'shell.qml'), '--no-duplicate']
            if a.filter_one:
                command += ['--log-rules', 'quickshell.fixture.dynamic.3.warning=false']
            result = subprocess.run(command,
                env=env, capture_output=True, text=True, timeout=30)
            text = result.stdout + result.stderr
            a.output.with_suffix('.log').write_text(text)
            decoded_count = 0
            decoded_ok = False
            files = list((root / 'run/quickshell/by-id').glob('*/log.qslog'))
            if result.returncode == 0 and len(files) == 1:
                decoded = subprocess.run([str(a.executable or a.runtime / 'bin/hics-qs'), 'log', str(files[0]), '--no-color', '--rules', '*.warning=true'],
                    env=env, capture_output=True, text=True, timeout=10)
                a.output.with_suffix('.decoded.log').write_text(decoded.stdout + decoded.stderr)
                pairs = [(int(c), int(i)) for c, i in re.findall(r'quickshell\.fixture\.dynamic\.(\d+): CATEGORY_LIFETIME (\d+)', decoded.stdout)]
                decoded_count = len(pairs)
                decoded_ok = decoded.returncode == 0 and len(pairs) == 200 and {i for c, i in pairs} == set(range(200)) and all(c == i % 8 for c, i in pairs)
            sparse_count = text.count('CATEGORY_LIFETIME')
            sparse_ok = sparse_count == (175 if a.filter_one else 200)
            report = {'code': result.returncode, 'sparseMessages': sparse_count, 'sparseFilterValid': sparse_ok, 'filterOne': a.filter_one, 'decodedMessages': decoded_count, 'decodedCategoriesAndBodiesValid': decoded_ok, 'complete': 'CATEGORIES_COMPLETE' in text,
                'asanUseAfterFree': 'heap-use-after-free' in text,
                'scope': 'Transient QML categories and asynchronous QS log pipeline; no render windows'}
            a.output.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
            return 0 if result.returncode == 0 and report['complete'] and decoded_ok and sparse_ok else 1
        finally:
            bus.terminate()
            bus.wait(timeout=5)
            bus.stdout.close()


if __name__ == '__main__':
    raise SystemExit(main())
