#!/usr/bin/env python3
"""Real DemoCard frames stop while locked and resume, with isolated services."""
import os,shutil,subprocess,tempfile
from pathlib import Path
from integration_support import require_wayland_session,snapshot_qml_runtime,run_snapshot_qml
require_wayland_session();ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-tour-playback-') as directory:
 base=Path(directory);root=base/'shell'
 shutil.copytree(ROOT/'shell',root,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 (root/'shell.qml').write_text('''import QtQuick
import Quickshell
import Hyprstack.Config
import qs.modules.onboarding
import qs.services
ShellRoot {
 id:root;property int phase:0;property int ticks:0;property int lockedTicks:0;property real before:0
 FloatingWindow {
  id:window;visible:true;implicitWidth:480;implicitHeight:270
  contentItem.Config.screen:screen?.name??""
  contentItem.Tokens.screen:screen?.name??""
  DemoCard {id:demo;anchors.fill:parent;demoId:"stacking"}
 }
 Timer {interval:250;running:true;repeat:true;onTriggered:{
  if(++root.ticks>80){console.error("TOUR_PLAYBACK_FAIL",root.phase,demo.playbackError,demo.renderedFrames());Qt.exit(1);return;}
  if(root.phase===0&&demo.renderedFrames()>3){root.before=demo.renderedFrames();PerformancePolicy.locked=true;root.phase=1;}
  else if(root.phase===1&&++root.lockedTicks>=6){
   if(demo.animate||demo.renderedFrames()>root.before+1){console.error("TOUR_PLAYBACK_FAIL locked decode",root.before,demo.renderedFrames());Qt.exit(1);return;}
   root.before=demo.renderedFrames();PerformancePolicy.locked=false;root.phase=2;
  }else if(root.phase===2&&demo.renderedFrames()>root.before+3){console.log("TOUR_PLAYBACK_OK");Qt.quit();}
 }}
}''')
 runtime=snapshot_qml_runtime(ROOT,base)
 bus_config=base/'bus.conf'
 bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
 env=dict(os.environ,**runtime,XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(base/'absent-system'),QT_QPA_PLATFORM='wayland',QT_QPA_PLATFORMTHEME='',HYPRLAND_INSTANCE_SIGNATURE='tour-playback-isolation',PULSE_SERVER='unix:'+str(base/'absent-audio'))
 result=run_snapshot_qml(['dbus-run-session','--config-file='+str(bus_config),'--','/usr/share/hics/qs/bin/hics-qs','-p',str(root)],env,ROOT/'build',30)
 output=result.stdout+result.stderr
 Path('/tmp/hics-tour-playback.log').write_text(output)
 assert result.returncode==0 and 'TOUR_PLAYBACK_OK' in output and 'TOUR_PLAYBACK_FAIL' not in output,output[-5000:]
 print('PASS: production DemoCard stops decoded frames while locked and resumes afterward')
