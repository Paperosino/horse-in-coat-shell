pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.Config
import qs.services
Singleton {
 id:root
 property bool configured:false
 function apply():void {
  if(!Hypr.usingLua)return;
  Hypr.extras.applyOptions({"misc:enable_anr_dialog":GlobalConfig.utilities.operations.watchUnresponsive,"misc:anr_missed_pings":Math.max(1,Math.min(20,GlobalConfig.utilities.operations.unresponsiveMissedPings))});
  configured=true;
 }
 Component.onCompleted:apply()
 Connections {target:GlobalConfig.utilities.operations;function onWatchUnresponsiveChanged():void {root.apply();}function onUnresponsiveMissedPingsChanged():void {root.apply();}}
 Connections {target:Hypr;function onUsingLuaChanged():void {root.apply();}}
 Connections {target:Hypr.extras;function onConfigOptionsReloaded():void {root.apply();}}
}
