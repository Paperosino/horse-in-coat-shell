#!/usr/bin/env python3
"""Charging or battery recovery must cancel pending critical hibernation."""
import os
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-battery-countdown-') as directory:
    base=Path(directory)
    source=(ROOT/'shell/modules/BatteryMonitor.qml').read_text()
    source='\n'.join(l for l in source.splitlines() if not l.startswith('import Hyprstack') and l!='import Quickshell.Services.UPower')
    source=source.replace('interval: 5000','interval: 100')
    (base/'BatteryMonitor.qml').write_text(source)
    fixtures={
        'UPower':'property bool onBattery:true; property QtObject displayDevice:QtObject {property bool ready:true;property real percentage:0.5}',
        'GlobalConfig':'property var general:({battery:{warnLevels:{values:[]},criticalLevel:5}});property var utilities:({toasts:{chargingChanged:false}})',
        'Toaster':'function toast(a,b,c,d){}',
        'Tr':'function tr(s){return s} function trMarked(s){return s}',
        'Toast':'readonly property int error:1',
        'SessionManager':'property int calls:0;function hibernate(){calls++}',
    }
    source=(base/'BatteryMonitor.qml').read_text().replace('Toast.Error','Toast.error').replace('Toast.Warning','Toast.error')
    (base/'BatteryMonitor.qml').write_text(source)
    for name,body in fixtures.items():
        (base/(name+'.qml')).write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton {'+body+'}')
    (base/'shell.qml').write_text('''import QtQuick
import Quickshell
ShellRoot {
 BatteryMonitor {id:battery}
 property int phase:0
 Timer {interval:180;running:true;repeat:true;onTriggered:{
  if(phase===0){UPower.displayDevice.percentage=0.01;UPower.onBattery=false}
  else if(phase===1){if(SessionManager.calls!==0)throw new Error("Hibernated while charging");UPower.onBattery=true;UPower.displayDevice.percentage=0.7}
  else if(phase===2){if(SessionManager.calls!==0)throw new Error("Hibernated after recovery");UPower.displayDevice.percentage=0.01}
  else if(phase===3){if(SessionManager.calls!==1)throw new Error("Critical hibernation lost");console.log("BATTERY_COUNTDOWN_OK");Qt.quit()}
  phase++
 }}
 Timer {interval:2500;running:true;onTriggered:Qt.exit(1)}
}''')
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen')
    env.pop('WAYLAND_DISPLAY',None);env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    run=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(base)],env=env,capture_output=True,text=True,timeout=4)
    output=run.stdout+run.stderr
    assert run.returncode==0 and 'BATTERY_COUNTDOWN_OK' in output,output
    print('PASS: charging and battery recovery cancel countdown; sustained critical battery still hibernates')
