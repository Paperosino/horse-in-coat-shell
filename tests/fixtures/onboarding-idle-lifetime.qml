//@ pragma DefaultEnv HICS_NO_ONBOARDING=1
//@ pragma DefaultEnv QS_NO_RELOAD_POPUP=1
import QtQuick
import Quickshell
import qs.services
import qs.modules as Modules
ShellRoot {
 id:root
 settings.watchFiles:false
 property int step:0
 property bool baselineIdle:false
 property bool baselineInhibit:false
 Modules.IdleMonitors {id:idle;lock:null}
 function require(condition,label) {
  if(!condition){console.error("PROFILE_FAIL",label);Qt.exit(1);return false;}
  return true;
 }
 Timer {
  interval:200;running:true;repeat:true
  onTriggered:{
   if(root.step===0){Onboarding.running=false;IdleInhibitor.enabled=false;}
   else if(root.step===1){root.baselineIdle=idle.enabled;root.baselineInhibit=IdleInhibitor.effectiveEnabled;Onboarding.running=true;}
   else if(root.step===2){if(!root.require(IdleInhibitor.effectiveEnabled&&!idle.enabled,"setup must inhibit automatic idle"))return;Onboarding.finish();}
   else if(root.step===3){if(!root.require(idle.enabled===root.baselineIdle&&IdleInhibitor.effectiveEnabled===root.baselineInhibit,"setup exit must restore policy"))return;IdleInhibitor.enabled=true;Onboarding.running=true;}
   else if(root.step===4){Onboarding.skip();}
   else if(root.step===5){if(!root.require(IdleInhibitor.enabled&&IdleInhibitor.effectiveEnabled,"setup must preserve manual keep-awake"))return;IdleInhibitor.enabled=false;}
   else {if(!root.require(idle.enabled===root.baselineIdle&&IdleInhibitor.effectiveEnabled===root.baselineInhibit,"final policy"))return;console.log("PROFILE_COMPLETE",CYCLES);Qt.quit();stop();}
   ++root.step;
  }
 }
}
