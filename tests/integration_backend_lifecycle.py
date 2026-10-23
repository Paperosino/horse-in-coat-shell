#!/usr/bin/env python3
"""Stress helper completion ordering, failures, and reversible game policy."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-backend-lifecycle-') as directory:
    base = Path(directory)
    shell = base / 'shell'
    for folder in ('components', 'services', 'utils'):
        (shell/folder).mkdir(parents=True)
    for relative in ('components/FeatureBackend.qml', 'services/GameMode.qml', 'services/SystemControls.qml'):
        shutil.copy2(ROOT/'shell'/relative, shell/relative)
    (shell/'utils/Paths.qml').write_text('pragma Singleton\nimport Quickshell\nSingleton { function toLocalFile(path) {return path.toString().replace("file://","")} }')
    helper = base / 'helper.py'
    helper.write_text('import json,sys\nif sys.argv[1]=="fail":sys.exit(7)\nprint(json.dumps({"id":int(sys.argv[1])}))\n')
    (shell/'assets').mkdir()
    controls_log=base/'controls.jsonl'
    (shell/'assets/system_controls.py').write_text('import json,sys\nwith open('+repr(str(controls_log))+',"a") as f:f.write(json.dumps(sys.argv[1:])+"\\n")\nprint(json.dumps({"fields":[]}))\n')
    original = {'animations:enabled': 0, 'decoration:shadow:enabled': 1,
        'decoration:blur:enabled': 1, 'general:gaps_in': 7, 'general:gaps_out': 13,
        'general:border_size': 3, 'decoration:rounding': 19, 'general:allow_tearing': 0}
    (shell / 'services/Hypr.qml').write_text('''pragma Singleton
import QtQuick
import Quickshell
Singleton {
 id:root
 property var options: ORIGINAL
 property var requests:[]
 property QtObject extras:QtObject {
  signal optionsChanged()
  signal configOptionsReloaded()
  function applyOptions(values) {
   root.requests=[...root.requests,values];
   root.options=Object.assign({},root.options,values);
   optionsChanged();
  }
 }
}'''.replace('ORIGINAL', json.dumps(original)))
    (shell / 'services/Toaster.qml').write_text('pragma Singleton\nimport Quickshell\nSingleton { function toast(a,b,c){} }')
    (shell / 'shell.qml').write_text('''import QtQuick
import Quickshell
import qs.components
import qs.services
ShellRoot {
 id:root
 property int received:0
 property int expected:0
 property bool failing:false
 FeatureBackend {id:backend;executable:"/usr/bin/python3"}
 FeatureBackend {id:missing;executable:"/nonexistent/hics-helper"}
 function require(value,message) {if(!value){console.error("LIFECYCLE_FAILED",message);Qt.exit(1);throw new Error(message)}}
 function checkQueue() {
  require(received===201,"lost or duplicated helper replies "+received);
  require(!backend.busy&&!missing.busy,"stuck helper queue");
  require(failing,"failed exit delivered as success");
  require(!GameMode.enabled,"reduced motion enabled game mode");
  GameMode.enabled=true;
  require(Hypr.options["general:gaps_in"]===0,"game options missing");
  GameMode.enabled=false;
  require(Hypr.options["general:gaps_in"]===7&&Hypr.options["animations:enabled"]===0,"original options lost");
  GameMode.enabled=true;
  Hypr.options=Object.assign({},Hypr.options,{"general:gaps_in":11});
  Hypr.extras.configOptionsReloaded();
  GameMode.enabled=false;
  require(Hypr.options["general:gaps_in"]===11,"reload snapshot lost");
  console.log("BACKEND_LIFECYCLE_OK");Qt.quit();
 }
 Component.onCompleted: {
  SystemControls.set("fixture.option",42);SystemControls.reset("fixture.option");
  missing.call([],null,d=>{
   require(!!d.error,"missing executable reported success");
   missing.executable="/usr/bin/python3";
   missing.call([HELPER,"900"],null,r=>require(r.id===900,"queue did not recover from failed start"));
  });
  for(let i=0;i<200;i++)backend.call([HELPER,String(i)],null,d=>{
   require(d.id===expected,"reply attached to wrong request: "+d.id+" expected "+expected);
   received++;expected++;
   if(d.id===0)backend.call([HELPER,"200"],null,r=>{require(r.id===200,"callback enqueue lost");received++;});
  });
  backend.call([HELPER,"fail"],null,d=>failing=!!d.error);
 }
 Timer {interval:50;running:true;repeat:true;onTriggered:if(root.received===201&&!backend.busy&&!missing.busy)root.checkQueue()}
 Timer {interval:20000;running:true;onTriggered:{console.error("LIFECYCLE_TIMEOUT",root.received,backend.busy,missing.busy);Qt.exit(1)}}
}'''.replace('HELPER', json.dumps(str(helper))))
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_CONFIG_HOME=str(base/'config'),
        XDG_STATE_HOME=str(base/'state'), XDG_DATA_HOME=str(base/'data'),
        QML_IMPORT_PATH=str(ROOT/'build/qml'), QML2_IMPORT_PATH=str(ROOT/'build/qml'))
    env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    env.pop('WAYLAND_DISPLAY', None)
    result = subprocess.run(['/usr/share/hics/qs/bin/hics-qs', '-p', str(shell)], env=env,
        capture_output=True, text=True, timeout=25)
    output = result.stdout + result.stderr
    assert result.returncode == 0 and 'BACKEND_LIFECYCLE_OK' in output, output
    assert 'TypeError' not in output and 'ReferenceError' not in output, output
    controls=[json.loads(line) for line in controls_log.read_text().splitlines()]
    assert ['reset','fixture.option'] in controls and not any(row[0]=='set' for row in controls),controls
    print('PASS: Reset cancels a pending settings edit before the debounce expires')
    print('PASS: 201 ordered replies, callback enqueue, failed exit and failed-start recovery')
    print('PASS: reduced motion is independent; game-mode exit and config reload restore saved options')
