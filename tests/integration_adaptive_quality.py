#!/usr/bin/env python3
"""Exercise real native quality/thermal timers without changing host settings."""
import json,os,shutil,subprocess,tempfile
from pathlib import Path
from integration_support import snapshot_qml_runtime, run_snapshot_qml
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-adaptive-quality-') as directory:
 base=Path(directory);shell=base/'shell';(shell/'services').mkdir(parents=True);(shell/'utils').mkdir()
 for name in ('GameMode.qml','Effects.qml'):shutil.copy2(ROOT/'shell/services'/name,shell/'services'/name)
 (shell/'utils/Paths.qml').write_text('pragma Singleton\nimport Quickshell\nSingleton {readonly property string config:'+json.dumps(str(base/'config/hics'))+'}')
 (shell/'services/Toaster.qml').write_text('pragma Singleton\nimport Quickshell\nSingleton {function toast(a,b,c){}}')
 (shell/'services/Hypr.qml').write_text('''pragma Singleton
import QtQuick
import Quickshell
Singleton {id:root;property bool usingLua:false;property var options:({});signal configReloaded
 property QtObject extras:QtObject {signal optionsChanged();signal configOptionsReloaded();function applyOptions(values){root.options=Object.assign({},root.options,values);optionsChanged();}}
}''')
 tools=base/'tools';tools.mkdir();control=base/'input.json';control.write_text('{"usage":95,"temperature":70}')
 helper=tools/'hics-gpu-monitor';helper.write_text('''#!/usr/bin/python3
import json,os,sys
for command in sys.stdin:
 data=json.load(open(os.environ['HICS_TEST_GPU_INPUT']))
 print(json.dumps(dict(requestId=command.strip().rsplit(" ",1)[-1],available=True,cpuTemperature=-1,**data)),flush=True)
''');helper.chmod(0o700)
 (shell/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Services
import Hyprstack.Config
import qs.services
ShellRoot {
 id:root;property int phase:0
 FileView {id:input;path:INPUT;printErrors:false}
 function require(value,message){if(!value){console.error("ADAPTIVE_FAIL",message);Qt.exit(1);return false;}return true;}
 Component.onCompleted:{
  RuntimePerformance.set("qualityFloor",0);RuntimePerformance.set("qualityDwell",5000);RuntimePerformance.set("sampleInterval",2000);
  RuntimePerformance.set("adaptiveQuality",true);RuntimePerformance.set("thermalGuard",true);
 }
 Timer {interval:100;repeat:true;running:true;onTriggered:{
  if(root.phase===0 && RuntimePerformance.quality===1){
   if(!root.require(Effects.blurEnabled&&!GlobalConfig.appearance.reducedMotion,"preferences changed during adaptive reduction"))return;
   input.setText('{"usage":95,"temperature":100}');root.phase=1;
  } else if(root.phase===1 && RuntimePerformance.thermalLimited){
   if(!root.require(!GameMode.enabled&&!Effects.effectiveBlurEnabled&&Effects.blurEnabled,"thermal guard policy did not isolate appearance preferences"))return;
   input.setText('{"usage":20,"temperature":70}');root.phase=2;
  } else if(root.phase===2 && !RuntimePerformance.thermalLimited && RuntimePerformance.quality===2){
   if(!root.require(Effects.effectiveBlurEnabled&&Effects.blurEnabled&&!GlobalConfig.appearance.reducedMotion,"quality recovery failed"))return;
   RuntimePerformance.set("adaptiveQuality",false);RuntimePerformance.set("thermalGuard",false);
   if(!root.require(!RuntimePerformance.status.monitoring,"disabled policies kept polling"))return;
   console.log("ADAPTIVE_QUALITY_OK");Qt.quit();
  }
 }}
 Timer {interval:45000;running:true;onTriggered:{console.error("ADAPTIVE_TIMEOUT",root.phase,RuntimePerformance.quality,JSON.stringify(RuntimePerformance.status));Qt.exit(1)}}
}'''.replace('INPUT',json.dumps(str(control))))
 env=dict(os.environ,HOME=str(base/'home'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'absent-session'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'),PIPEWIRE_REMOTE='hics-adaptive-fixture-absent',PULSE_SERVER='unix:'+str(base/'absent-pulse'),HICS_HELPER_DIR=str(tools),QT_QPA_PLATFORM='offscreen',PATH=str(tools)+':'+os.environ['PATH'],HICS_TEST_GPU_INPUT=str(control),XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),XDG_DATA_HOME=str(base/'data'))
 env.update(snapshot_qml_runtime(ROOT,base))
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);env.pop('WAYLAND_DISPLAY',None)
 run=run_snapshot_qml(['/usr/share/hics/qs/bin/hics-qs','-p',str(shell)],env,ROOT/'build',50)
 output=run.stdout+run.stderr;Path('/tmp/hics-adaptive-quality.log').write_text(output)
 assert run.returncode==0 and 'ADAPTIVE_QUALITY_OK' in output,output[-7000:]
 assert not any(s in output for s in ('TypeError:','ReferenceError:','Binding loop','Cannot assign','Unable to assign')),output[-7000:]
 print('PASS: native GPU hysteresis, thermal guard and recovery preserve appearance/accessibility and stop polling when disabled')
