pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.I18n
import Hyprstack.Config
import Hyprstack.Services
import qs.services
Singleton {
 id:root
 readonly property bool requiresSignIn: NetworkService.state.connectivity===2
 property string shownConnection:""
 readonly property string status: requiresSignIn?"portal":NetworkService.state.connectivity===4?"online":NetworkService.state.connectivity===3?"limited":"unknown"
 function signIn():void {
  const existing=Hypr.toplevels.values.find(t=>t.lastIpcObject.class==="org.hics.CaptivePortal");
  if(existing){NotificationActivation.focus(existing);return;}
  DesktopConveniences.openPortal(NetworkService.state.connectivityCheckUri || "http://networkcheck.kde.org/",Tr.language);}
 function check():void {NetworkService.request("connectivity");}
 function sync():void {
  if(!NetworkService.state.connected){shownConnection="";DesktopConveniences.closePortal();return;}
  if(NetworkService.state.connectivity===4){shownConnection="";DesktopConveniences.closePortal();return;}
  if(requiresSignIn&&GlobalConfig.general.network.captivePortalAutoOpen&&shownConnection!==NetworkService.state.activeConnection){shownConnection=NetworkService.state.activeConnection;signIn();}
 }
 Connections {target:NetworkService;function onStateChanged():void{root.sync();}}
 Timer {interval:10000;running:root.requiresSignIn;repeat:true;onTriggered:root.check()}
 Component.onCompleted:sync()
}
