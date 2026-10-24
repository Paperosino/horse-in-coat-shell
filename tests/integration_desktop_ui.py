"""Construct system-integration pages headlessly with private config and D-Bus."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-desktop-ui-') as directory:
    base = Path(directory)
    shell = base / 'shell'
    shutil.copytree(ROOT / 'shell', shell, ignore=shutil.ignore_patterns('plugin', 'extras', '__pycache__'))
    (shell / 'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import Hyprstack.Services
import qs.modules.nexus
import qs.modules.extensions as Extensions
import qs.modules
import qs.modules.nexus.pages
import qs.modules.bar.popouts as Popouts
import qs.modules.nexus.common
import qs.modules.nexus.pages.services
import qs.services
import qs.modules.background
import qs.modules.bar.components
import qs.components
import qs.modules.bar as Bar
import qs.modules.drawers as Drawers
import "utils/scripts/settings-search.js" as Search
import "services/NotificationActivation.js" as ActivationMatch
ShellRoot {
 id: root
 property int defaultActionCount: 0
 property int otherActionCount: 0
 property NotifData activationProbe: NotifData {
  appName: "Test sender"; desktopEntry: "test.sender"
  liveActions: [{identifier:"default", invoke:() => root.defaultActionCount++}, {identifier:"delete", invoke:() => root.otherActionCount++}]
 }
 property var vpnProtocols: __VPN_PROTOCOLS__
 property var dockPreviewA: ({title:"First window",wayland:null})
 property var dockPreviewB: ({title:"Second window",wayland:null})
 property int phase: 0
 property var current: null
 property NexusState state: NexusState {}
 FloatingWindow { visible: true; implicitWidth: 1000; implicitHeight: 900;color:Colours.palette.m3surface; Item { id: host; anchors.fill: parent } }
 Bar.ExtraPanel {id:extraTop;screen:Quickshell.screens[0];spec:({id:"11111111-1111-1111-1111-111111111111",edge:"top",thickness:48,hideDelay:500,autoHide:false});edgeOffset:0}
 Bar.ExtraPanel {id:extraBottom;screen:Quickshell.screens[0];spec:({id:"22222222-2222-2222-2222-222222222222",edge:"bottom",thickness:52,hideDelay:500,autoHide:true});edgeOffset:0}
 Extensions.PluginHost {}
 Extensions.PluginDesktop {parent:host;screen:Quickshell.screens[0];width:host.width;height:host.height}
 Timer {interval:5000;running:true;onTriggered:{const data=Plugins.isolatedStates["isolated-counter"];if(!data?.slots?.desktopWidget?.length){console.error("ISOLATED_WIDGET_FAILED",JSON.stringify(Plugins.runtimeErrors));Qt.quit();}else console.log("ISOLATED_WIDGET_OK");}}
 Timer {interval:5500;running:true;onTriggered:Plugins.workerAction("isolated-counter","increment",null)}
 Timer {interval:6000;running:true;onTriggered:Plugins.reloadCode()}
 Timer {interval:8500;running:true;onTriggered:{if(Plugins.isolatedStates["isolated-counter"]?.slots?.barWidget?.[0]?.text!=="1"||!Plugins.byId("isolated-counter")?.enabled){console.error("ISOLATED_RESTART_FAILED",JSON.stringify(Plugins.runtimeErrors));Qt.quit();}else console.log("ISOLATED_RESTART_OK");}}
 ScreenState { id: popupState; modelData: Quickshell.screens[0] }
 Bar.BarWrapper { id: testBar; parent:host; screen:Quickshell.screens[0]; screenState:popupState; popouts:popupPanels.popouts; fullscreen:false }
 Drawers.Panels { id:popupPanels; parent:host; screen:Quickshell.screens[0]; screenState:popupState; bar:testBar; borderThickness:0 }
 PageBase {
  id: scrollProbe; parent: host; title: "Scroll regression"; nState: root.state; width: 800; height: 360
  property var rows: Array.from({length: 40}, (_, i) => i)
  Column {
   width: scrollProbe.cappedWidth
   Repeater { model: scrollProbe.rows; Rectangle { required property var modelData; width: 600; height: 40; color: "transparent" } }
  }
 }
 PageBase {
  id: expansionPage; parent:host; visible:false; title:"Expansion regression"; nState:root.state; width:800;height:360
  Column {
   width:expansionPage.cappedWidth
   SettingsCard {
    id:expansionCard; width:parent.width;title:"Animated section";collapsible:true;expanded:false
    Rectangle { implicitWidth:600;implicitHeight:700;color:"transparent" }
   }
   Rectangle {width:600;height:80;color:"transparent"}
  }
 }
 Component { id: disposableExpansion; SettingsCard { title:"Disposable animation";width:600;collapsible:true;expanded:false;Rectangle {implicitHeight:200;implicitWidth:500;color:"transparent"} } }
 property var disposableCard:null
 property int expansionPhase:0
 property real lastExpansion:0
 property real expandedPageHeight:0
 FrameAnimation {
  running:root.expansionPhase===1 || root.expansionPhase===2
  onTriggered:{
   const value=expansionCard.expansionExtent;
   if(!root.check(value>=-0.1 && value<=700+Tokens.spacing.medium+0.1,"expansion extent bounds: "+value))return;
   if(root.expansionPhase===1 && !root.check(value>=root.lastExpansion-0.1,"monotonic expansion"))return;
   if(root.expansionPhase===2 && !root.check(value<=root.lastExpansion+0.1,"monotonic collapse"))return;
   if(root.expansionPhase===2 && value>80 && value<400 && !root.check(expansionPage.settledContentHeight<root.expandedPageHeight-40,"scroll extent follows collapse"))return;
   root.lastExpansion=value;
  }
 }
 Timer {
  interval:50;running:true;repeat:true
  onTriggered:{
   if(root.expansionPhase===0 && !expansionPage.contentLayoutSettled.running){root.lastExpansion=0;root.expansionPhase=1;expansionCard.expanded=true;}
   else if(root.expansionPhase===1 && !expansionPage.layoutAnimations.length && !expansionPage.contentLayoutSettled.running && expansionCard.expansionExtent>690){
    root.expandedPageHeight=expansionPage.settledContentHeight;
    expansionPage.flickable.contentY=expansionPage.flickable.contentHeight-expansionPage.flickable.height+expansionPage.flickable.bottomMargin;
    root.lastExpansion=expansionCard.expansionExtent;root.expansionPhase=2;expansionCard.expanded=false;
   }else if(root.expansionPhase===2 && !expansionPage.layoutAnimations.length && !expansionPage.contentLayoutSettled.running && expansionCard.expansionExtent<.1){
    root.expansionPhase=3;expansionCard.expanded=true;
   }else if(root.expansionPhase===3){
    const value=expansionCard.expansionExtent;expansionCard.expanded=false;
    if(!root.check(Math.abs(expansionCard.expansionExtent-value)<1,"continuous animation reversal: "+value+" → "+expansionCard.expansionExtent))return;
    root.expansionPhase=4;
   }else if(root.expansionPhase===4){
    expansionCard.expanded=true;root.expansionPhase=5;
   }else if(root.expansionPhase===5 && !expansionPage.layoutAnimations.length && !expansionPage.contentLayoutSettled.running){
    root.disposableCard=disposableExpansion.createObject(expansionPage.contentChild);root.expansionPhase=6;
   }else if(root.expansionPhase===6){root.disposableCard.expanded=true;root.expansionPhase=7;
   }else if(root.expansionPhase===7){root.disposableCard.destroy();root.disposableCard=null;root.expansionPhase=8;
   }else if(root.expansionPhase===8 && !expansionPage.layoutAnimations.length && !expansionPage.contentLayoutSettled.running){
    root.expansionPhase=9;console.log("SETTINGS_EXPANSION_OK");stop();
   }
  }
 }
 Timer { id: restoreRows; interval: 24; onTriggered: scrollProbe.rows = Array.from({length: 40}, (_, i) => i + 1) }
 Timer {
  property int step: 0
  interval: 160; running: true; repeat: true
  onTriggered: {
   if (step === 0) {
    if (scrollProbe.contentLayoutSettled.running || scrollProbe.flickable.contentHeight < 1000) return;
    scrollProbe.flickable.contentY = 500;
   }
   else if (step <= 4) {
    if (scrollProbe.contentLayoutSettled.running) return;
    if (!root.check(Math.abs(scrollProbe.flickable.contentY - 500) < 1, "scroll position after live update: " + scrollProbe.flickable.contentY + "/" + scrollProbe.flickable.contentHeight)) return;
    scrollProbe.rows = []; restoreRows.start();
   } else if (step === 5) {
    if (scrollProbe.contentLayoutSettled.running) return;
    if (!root.check(Math.abs(scrollProbe.flickable.contentY - 500) < 1, "scroll position after repeated updates")) return;
    scrollProbe.rows = [1];
   } else if (step >= 10) {
    if (!root.check(scrollProbe.flickable.contentY <= 0, "scroll clamped after actual content removal: " + scrollProbe.flickable.contentY + "/" + scrollProbe.flickable.contentHeight)) return;
    console.log("SCROLL_REFRESH_OK"); stop(); scrollProbe.visible = false;
   }
   step++;
  }
 }

 Timer {id:screenshot;interval:120;property string file;onTriggered:Quickshell.execDetached(["/usr/bin/grim",file])}
 property QtObject fakeClipboard: QtObject {
  property var entries:[{id:"fixture",text:"Pinned project notes",isBinary:false,pinned:true,application:"Editor",timestamp:1700000000,imagePath:""}]
  property var settings:({enabled:true,paused:false,text:true,images:true,maxEntries:500,expiryDays:30})
  property string error:""
  property bool capturing:true
  property bool busy:false
  function refresh():void {}
  function configure(values):void {settings=Object.assign({},settings,values)}
  function clear(keep):void {if(!keep)entries=[]}
  function pin(id):void {}
  function copy(id):void {}
  function remove(id):void {}
  function importLegacy():void {}
 }
 property QtObject fakeShortcuts: QtObject {
  property var actions:[{id:"fixture",description:"Shell: Open launcher",keys:["SUPER + Space"],submap:"",flags:{}}]
  property var settings:({physicalKeys:false})
  property var savedAction:({})
  property string error:""
  function refresh():void {}
  function conflicts(id,key,submap):var {return key==="SUPER + X"?[{description:"Existing action"}]:[]}
  function save(action):void {savedAction=action}
  function configure(values):void {settings=Object.assign({},settings,values)}
 }
 property QtObject fakeSessions: QtObject {
  property var settings:({enabled:true,autosave:true,startup:"ask",interval:120})
  property var snapshots:[{id:"fixture",name:"Development",count:2,created:1700000000}]
  property var preview:({version:1,id:"fixture",name:"Development",windows:[{key:"a",application:"Editor",name:"Editor",enabled:true,command:["editor"],workspace:2},{key:"b",application:"Terminal",name:"Terminal",enabled:true,command:["terminal"]}]})
  property var report:[]
  property string error:""
  property string desktop:"Hyprland"
  property bool busy:false
  property var restored:[]
  signal changed()
  function refresh():void {}
  function configure(values):void {settings=Object.assign({},settings,values)}
  function savePreview(snapshot):void {preview=snapshot}
  function restore(id,selected):void {restored=selected}
 }
 property QtObject fakeEditorVpn: QtObject {
  property bool busy:false
  property string error:""
  property var plugins:root.vpnProtocols.map(p=>Object.assign({},p,{installed:true}))
  property var profiles:[]
  property var draft:({})
  signal changed()
  signal operationSucceeded()
  signal saved(string path)
  function refresh():void {}
 }
 property QtObject fakeQuickVpn: QtObject {
  property bool busy:false
  property string error:""
  property string activated
  property string deactivated
  property string removed
  property var plugins:[]
  property var draft:({})
  signal changed()
  function remove(path):void {removed=path;profiles=profiles.filter(p=>p.path!==path)}
  function edit(path):void {}
  property var profiles:Array.from({length:25},(_,i)=>({name:"VPN "+i,path:"/profile/"+i,active:i===0,state:2,activePath:"/active/"+i}))
  function refresh():void {}
  function activate(path):void {activated=path}
  function deactivate(path):void {deactivated=path}
 }
 VpnPasswordField {id:passwordProbe;parent:host;width:800;label:"Password";value:"saved-fixture-password"}
 VpnSection {id:deleteProbe;parent:host;width:800;nState:root.state;vpnBackend:root.fakeQuickVpn}
 property QtObject fakeAuthAgent:QtObject {
  property var challenge:({requestId:1,name:"VPN fixture",fields:[{key:"password",label:"Password",value:"saved-auth-fixture",secret:true}]})
  property string error:""
  signal changed()
  function submit(values,remember):void {}
  function cancel():void {if(challenge.name){challenge=({});changed()}}
 }
 VpnAuthentication {id:authProbe;agent:root.fakeAuthAgent}
 function findNamed(item,name):var {
  if(item.objectName===name)return item;
  for(const child of item.children??[]){const found=findNamed(child,name);if(found)return found;}
  return null;
 }
 Timer {
  interval:2000;running:true
  onTriggered:{
   if(!root.check(passwordProbe.field.echoMode===TextInput.Password&&passwordProbe.field.text==="saved-fixture-password","stored password is present but masked"))return;
   passwordProbe.toggleVisibility();
   if(!root.check(passwordProbe.field.echoMode===TextInput.Normal&&passwordProbe.field.text==="saved-fixture-password","show password preserves the value"))return;
   passwordProbe.toggleVisibility();
   if(!root.check(passwordProbe.field.echoMode===TextInput.Password,"password can be hidden again"))return;
   if(!root.check(authProbe.credentials.password==="saved-auth-fixture","authentication input is prefilled"))return;
   authProbe.credentials={password:"typed-auth-fixture"};root.fakeAuthAgent.changed();
   if(!root.check(authProbe.credentials.password==="typed-auth-fixture","authentication updates do not clear input"))return;
   const removeButton=root.findNamed(deleteProbe,"vpnDeleteButton");
   if(!root.check(removeButton!==null,"delete action exists beside VPN profiles"))return;
   removeButton.clicked();
   if(!root.check(!!deleteProbe.removingPath&&!root.fakeQuickVpn.removed,"deletion requires confirmation"))return;
   const path=deleteProbe.removingPath;
   root.findNamed(deleteProbe,"vpnConfirmDelete").clicked(null);
   if(!root.check(root.fakeQuickVpn.removed===path&&!deleteProbe.removingPath,"confirmed deletion removes exactly the chosen profile"))return;
   passwordProbe.visible=false;deleteProbe.visible=false;root.fakeAuthAgent.cancel();
   console.log("VPN_CREDENTIALS_DELETE_OK");
  }
 }
 Popouts.PopoutState {id:quickPopoutState;screen:Quickshell.screens[0]}
 Popouts.Network {id:quickNetwork;parent:host;popouts:quickPopoutState;vpnBackend:root.fakeQuickVpn}
 Timer {
  property int step:0
  interval:400;repeat:true;running:true
  onTriggered:{
   const list=quickNetwork.connectionList;
   if(!list.height||list.count<25)return;
   if(step===0){
    if(!root.check(list.count===25,"all quick VPN profiles remain reachable"))return;
    if(!root.check(list.height<=quickNetwork.rowHeight*10+1&&list.contentHeight>list.height,"network popup is capped at ten scrollable rows"))return;
    quickNetwork.activateRow(quickNetwork.connectionRows[1]);
    quickNetwork.activateRow(quickNetwork.connectionRows[0]);
    if(!root.check(root.fakeQuickVpn.activated==="/profile/1"&&root.fakeQuickVpn.deactivated==="/active/0","quick VPN connect and disconnect"))return;
    root.fakeQuickVpn.busy=true;quickNetwork.activateRow(quickNetwork.connectionRows[2]);root.fakeQuickVpn.busy=false;
    if(!root.check(root.fakeQuickVpn.activated==="/profile/1","busy VPN action is not duplicated"))return;
    list.contentY=quickNetwork.rowHeight*12;list.preferredY=list.contentY;
    root.fakeQuickVpn.profiles=root.fakeQuickVpn.profiles.map(p=>Object.assign({},p));
   }else{
    if(!root.check(Math.abs(list.contentY-quickNetwork.rowHeight*12)<1,"popup scroll survives VPN status refresh"))return;
    list.positionViewAtEnd();
    if(!root.check(list.contentY>quickNetwork.rowHeight*10,"VPN connections past the tenth row can be reached"))return;
    if(!root.check(PageRegistry.route("vpn").id==="network"&&!PageRegistry.navigationPages.some(p=>p.id==="vpn"),"VPN belongs to network settings"))return;
    console.log("NETWORK_QUICK_VPN_OK");quickNetwork.visible=false;stop();
   }
   step++;
  }
 }
 QtObject {
  id:fakeStorage
  property bool busy:false
  property string error:""
  property var state:({volumes:[
   {path:"/mock/p1",drivePath:"/mock/d1",driveSize:200000000000,device:"/dev/test1",model:"Fixture SSD",label:"Files",filesystem:"ext4",size:100000000000,total:100000000000,free:60000000000,mountPoint:"/mnt/files",ssd:true,removable:false,mountEditable:true,mountDirectory:"/mnt/files",mountOptions:"",smart:{supported:false}},
   {path:"/mock/p2",drivePath:"/mock/d1",driveSize:200000000000,device:"/dev/test2",model:"Fixture SSD",filesystem:"ext4",size:100000000000,mountPoint:"",ssd:true,removable:false,mountEditable:true,mountDirectory:"/mnt/extra",mountOptions:"",smart:{supported:false}},
   {path:"/mock/p3",drivePath:"/mock/d2",device:"/dev/test3",model:"Fixture USB",filesystem:"ext4",size:50000000000,mountPoint:"/",removable:false,smart:{supported:false}}
  ]})
  function reload(){}
  function apply(operation,options){}
  signal applied(string operation)
 }
 StoragePage {id:storageProbe;parent:host;visible:false;width:800;height:600;nState:root.state;backend:fakeStorage}
 property var storageEditor:null
 function namedChild(item,name){if(item.objectName===name)return item;for(const child of item.children??[]){const found=namedChild(child,name);if(found)return found;}return null}
 Timer {
  property int step:0
  interval:150;running:true;repeat:true
  onTriggered:{
   if(step===0){
    if(!root.check(storageProbe.drives.length===2&&storageProbe.drives[0].volumes.length===2,"group physical disks and their volumes"))return;
    if(!root.check(!storageProbe.canUnmount(fakeStorage.state.volumes[2]),"protect the system mount"))return;
    storageProbe.inspect(fakeStorage.state.volumes[0]);
   }else if(step===1){
    root.storageEditor=root.namedChild(storageProbe,"storageVolumeSettings");
    if(!root.check(!!root.storageEditor,"selected volume inspector"))return;
    root.storageEditor.edit("automatic",true);
    fakeStorage.state={volumes:fakeStorage.state.volumes.map(v=>Object.assign({},v))};
   }else{
    if(!root.check(root.storageEditor===root.namedChild(storageProbe,"storageVolumeSettings")&&root.storageEditor.dirty&&root.storageEditor.draft.automatic,"storage draft survives background refresh"))return;
    storageProbe.selectedPath="";console.log("STORAGE_DESIGN_OK");stop();
   }
   step++;
  }
 }
 VpnAuthentication {}
 StatusIcons {}
 VideoWallpaper { settings: ({kind:"video",source:"",muted:true,volume:0,scaling:"fill"}); paused:true }
 Process { id: notifier }
 property string actionReply
 Process { id: actionNotifier; stdout: StdioCollector { onStreamFinished: root.actionReply = text.trim() } }
 function findPopup(item): var {
  if (item.objectName === "notificationPopup") return item;
  for (const child of item.children ?? []) { const found = findPopup(child); if (found) return found; }
  return null;
 }
 function sendNotification(): void { notifier.exec(["notify-send", "--app-name=Integration test", "--expire-time=10000", "Integration notification"]); }
 function check(condition, message): bool { if (condition) return true; console.error("NOTIFICATION_TEST_FAILED", message); Qt.quit(); return false; }
 property var sources: PageRegistry.navigationPages.map(p => p.pageIndex).concat(["DockPage.qml", "AudioPage.qml", "NetworkPage.qml", "StoragePage.qml", "AccessibilityPage.qml", "SharingPage.qml", "services/NotificationsPage.qml", "network/AddNetworkPage.qml", "MediaPage.qml", "network/VpnProfilesPage.qml", "network/VpnEditorPage.qml", "network/VpnPluginsPage.qml", "ClipboardPage.qml", "ShortcutEditorPage.qml", "WorkspaceSessionPage.qml"]).concat(__DESIGN_PAGES__).concat(["wireguard","openvpn","pptp","l2tp","openconnect","vpnc","strongswan","libreswan","sstp","fortisslvpn","ssh"].map(p=>"vpn-test:"+p))
 Component.onCompleted: {
  const oldVideos=LiveWallpapers.videoStates, oldEngines=LiveWallpapers.engineRunning;
  LiveWallpapers.reportEngine("fixture",false);const engineState=LiveWallpapers.engineRunning;
  LiveWallpapers.reportEngine("fixture",false);
  if(!check(engineState===LiveWallpapers.engineRunning,"unchanged engine status must stay idle"))return;
  LiveWallpapers.reportVideo("fixture",{frames:10,paused:true,error:""});const videoState=LiveWallpapers.videoStates;
  LiveWallpapers.reportVideo("fixture",{frames:10,paused:true,error:""});
  if(!check(videoState===LiveWallpapers.videoStates,"paused video status must stay idle"))return;
  LiveWallpapers.reportVideo("fixture",{frames:11,paused:false,error:""});
  if(!check(videoState!==LiveWallpapers.videoStates&&LiveWallpapers.videoStates.fixture.frames===11,"new video frames remain observable"))return;
  LiveWallpapers.videoStates=oldVideos;LiveWallpapers.engineRunning=oldEngines;
  console.log("WALLPAPER_IDLE_STATUS_OK");
  if (!check(PageRegistry.pages.length === PageCompRegistry.pageComps.length, "page registry alignment")) return;
  for (const page of PageRegistry.navigationPages) {
   if (!check(PageRegistry.indexOf(page.id) === page.pageIndex, "canonical route " + page.id)) return;
  }
  const searches = [["Volume step", 5], ["Brightness step", 1], ["Wi-Fi rescan", 3], ["Smart colour scheme", 0], ["Lyrics backend", 5], ["Application rules", 20], ["Encrypted volumes", 24]];
  for (const test of searches) {
   const result = Search.find(test[0], text => text).find(r => r.label === test[0]);
   if (!check(result && result.page === test[1], "search destination " + test[0])) return;
  }
  for (const entry of Search.catalogue) {
   if (!check(entry.page >= 0 && entry.page < PageRegistry.pages.length, "search page index")) return;
  }
  if (!check(GlobalConfig.notifs.actionOnClick, "notification activation enabled by default")) return;
  if (!check(activationProbe.activate() && defaultActionCount === 1 && otherActionCount === 0, "default action takes priority over other actions")) return;
  const entry = {id:"org.telegram.desktop", name:"Telegram", startupClass:"TelegramDesktop"};
  const old = {lastIpcObject:{mapped:true, class:"TelegramDesktop", focusHistoryID:3}};
  const recent = {lastIpcObject:{mapped:true, class:"org.telegram.desktop", focusHistoryID:0}};
  const wrong = {lastIpcObject:{mapped:true, class:"AyugramDesktop", focusHistoryID:0}};
  const spoofed = {lastIpcObject:{mapped:true, class:"Firefox", title:"Telegram", focusHistoryID:0}};
  if (!check(ActivationMatch.bestWindow({desktopEntry:"org.telegram.desktop"}, entry, [wrong, old, recent, spoofed]) === recent, "exact sender and most recent window")) return;
  if (!check(ActivationMatch.bestWindow({appName:"Telegram"}, null, [wrong, recent]) === recent, "sender app name fallback")) return;
  if (!check(!ActivationMatch.bestWindow({desktopEntry:"org.telegram.desktop", appName:"Firefox"}, null, [wrong, spoofed]), "unrelated app and title are not matched")) return;
  if (!check(!ActivationMatch.desktopEntry({appName:"Editor"}, [{id:"a",name:"Editor"},{id:"b",name:"Editor"}]), "ambiguous application names do not launch")) return;
  if (!check(!ActivationMatch.bestWindow({appName:"Telegram"}, null, [{lastIpcObject:{mapped:false,class:"TelegramDesktop"}}]), "closed windows are ignored")) return;
  if (!check(ActivationMatch.followWindow({desktopEntry:"org.telegram.desktop"}, entry, [recent], spoofed) === recent, "drawer focus changes do not cancel sender activation")) return;
  if (!check(ActivationMatch.followWindow({desktopEntry:"org.telegram.desktop"}, entry, [recent,old], old) === old, "application-selected window is preserved")) return;
  console.log("NOTIFICATION_ACTIVATION_OK");
  DesktopIntegration.refresh();
  Nmcli.setAutoconnect("Saved network", false, () => {});
  NotificationPolicy.observe("test.app", "Test app");
  NotificationPolicy.setRule("test.app", "silent");
 }
 Timer {
  interval: 500; running: true; repeat: true
  onTriggered: {
   if (root.expansionPhase < 9) return;
   if (root.current) { root.current.destroy(); root.current = null; }
   if (root.phase >= root.sources.length) {
    const step = root.phase++ - root.sources.length;
    if (step === 0) {
     Notifs.clearAll(); Notifs.dnd = false; NotificationPolicy.resume();
     NotificationPolicy.observe("Integration test", "Integration test");
     NotificationPolicy.setRule("Integration test", "silent"); root.sendNotification();
    } else if (step === 1) {
     if (!root.check(Notifs.notClosed.length === 1 && Notifs.popups.length === 0, "silent rule")) return;
     NotificationPolicy.setRule("Integration test", "blocked"); root.sendNotification();
    } else if (step === 2) {
     if (!root.check(Notifs.notClosed.length === 1, "blocked rule")) return;
     Notifs.clearAll(); NotificationPolicy.setRule("Integration test", "all"); NotificationPolicy.pauseFor(30); root.sendNotification();
    } else if (step === 3) {
     if (!root.check(Notifs.notClosed.length === 1 && Notifs.popups.length === 0, "temporary pause")) return;
     NotificationPolicy.resume(); Notifs.clearAll();
     popupPanels.popouts.currentName = "audio";
     popupPanels.popouts.currentCenter = 950;
     popupPanels.popouts.hasCurrent = true;
     root.sendNotification();
    } else if (step === 4) {
     if (!root.check(Notifs.popups.length === 1, "resume popups")) return;
     if (!root.check(popupPanels.notificationPopoutOverlap, "right-hand popup intersects notification column")) return;
     if (!root.check(popupPanels.notifications.y + 5 >= popupPanels.popoutsWrapper.y + popupPanels.popoutsWrapper.height, "notifications are below the popup instead of overlapping")) return;
     if (!root.check(popupPanels.notifications.y + popupPanels.notifications.height <= popupPanels.height + 1, "notification stack fits remaining screen height")) return;
     const card = root.findPopup(popupPanels.notifications);
     if (!root.check(card !== null, "actual notification card exists")) return;
     const cardTop = card.mapToItem(popupPanels, 0, 0).y;
     if (!root.check(cardTop >= popupPanels.popoutsWrapper.y + popupPanels.popoutsWrapper.height, "notification card follows its background: " + cardTop)) return;
     console.log("NOTIFICATION_POPUP_LAYOUT_OK");
     popupPanels.popouts.close();
    } else if (step === 5) {
     Notifs.clearAll(); root.actionReply = "";
     actionNotifier.exec(["notify-send", "--app-name=Integration test", "--expire-time=10000", "--action=default=Open", "Action notification"]);
    } else if (step === 6) {
     const notification = Notifs.notClosed.find(n => n.summary === "Action notification");
     if (!root.check(notification && notification.activate(), "live notification default action")) return;
    } else if (step === 7) {
     if (!root.check(root.actionReply === "default", "ActionInvoked delivered to application")) return;
     console.log("NOTIFICATION_DBUS_ACTION_OK");
     DockConf.enabled = true;
     popupPanels.dock.menuTask = {entry:null,windows:[],group:{key:"fixture"},pinned:false,mapToItem:() => Qt.point(0,0)};
     popupPanels.dock.menuOpen = true;
     popupPanels.dock.hoverWindow(root.dockPreviewA);
    } else if (step === 8) {
     if (!root.check(!popupPanels.dock.previewWindow, "dock preview requires hover delay")) return;
    } else if (step === 10) {
     if (!root.check(popupPanels.dock.previewWindow === root.dockPreviewA, "dock preview opens after one second")) return;
     popupPanels.dock.hoverWindow(root.dockPreviewB);
     if (!root.check(popupPanels.dock.previewWindow === root.dockPreviewB, "warm dock preview switches immediately")) return;
     popupPanels.dock.leaveWindow(root.dockPreviewB);
    } else if (step === 11) {
     if (!root.check(popupPanels.dock.previewWarm, "dock preview remains warm during grace period")) return;
    } else if (step === 21) {
     if (!root.check(!popupPanels.dock.previewWarm && !popupPanels.dock.previewWindow, "dock preview grace expires")) return;
     popupPanels.dock.hoverWindow(root.dockPreviewA);
     if (!root.check(!popupPanels.dock.previewWindow, "expired preview requires hover again")) return;
     popupPanels.dock.closeMenu();
     if (!root.check(!popupPanels.dock.menuOpen && !popupPanels.dock.hoveredWindow, "closing dock cancels hover state")) return;
     console.log("DOCK_PREVIEW_OK");
     console.log("DESKTOP_UI_OK"); Qt.quit();
    }
    return;
   }
   let path = root.sources[root.phase++];
   if (typeof path === "string" && path.startsWith("vpn-test:")) {
    const protocol = path.substring(9);
    NetworkManagerVpn.create(protocol === "wireguard" ? protocol : "org.freedesktop.NetworkManager." + protocol);
    path = "network/VpnEditorPage.qml";
   }

   const component = typeof path === "number" ? PageCompRegistry.pageComps[path] : Qt.createComponent("modules/nexus/pages/" + path);
   if (component.status !== Component.Ready) { console.error(component.errorString()); Qt.quit(); return; }
   root.current = component.createObject(host, {nState: root.state, width: 1000, height: 900});
   if (!root.current) { console.error("PAGE_CREATION_FAILED", path); Qt.quit(); return; }
   if(path==="ClipboardPage.qml"){
    root.current.backend=root.fakeClipboard;
    root.current.set("maxEntries",750);
    if(!root.check(root.fakeClipboard.settings.maxEntries===750,"clipboard retention updates the backend"))return;
   }
   if(path==="ShortcutEditorPage.qml"){
    root.current.backend=root.fakeShortcuts;
    root.current.begin(root.fakeShortcuts.actions[0]);root.current.chord="SUPER + X";
    if(!root.check(root.current.conflicts.length===1,"shortcut conflicts appear before applying"))return;
    root.current.chord="SUPER + SHIFT + T";root.current.save();
    if(!root.check(root.fakeShortcuts.savedAction.keys[0]==="SUPER + SHIFT + T","shortcut editor saves the recorded combination"))return;
   }
   if(path==="WorkspaceSessionPage.qml"){
    root.current.backend=root.fakeSessions;root.current.loadPreview();root.current.windowChange(1,"enabled",false);
    if(!root.check(root.current.selected.length===1&&root.current.selected[0].key==="a","snapshot application selection"))return;
    root.current.confirmRestore=true;root.findNamed(root.current,"confirmSessionRestore").clicked(null);
    if(!root.check(root.fakeSessions.restored.length===1&&root.fakeSessions.restored[0]==="a","restore uses only selected applications"))return;
   }
   if(path==="network/VpnEditorPage.qml"){
    root.current.protocol=root.vpnProtocols.find(p=>p.service===root.current.form.type)??({fields:[]});
    if(!root.check(!root.current.advanced,"VPN advanced settings start collapsed"))return;
    const before=JSON.stringify(root.current.form);
    root.current.advanced=true;root.current.advanced=false;
    if(!root.check(JSON.stringify(root.current.form)===before,"collapsing advanced VPN settings preserves their data"))return;
    if(String(root.current.form.type??"").endsWith(".openvpn")){
     root.current.nested("data","connection-type","password");
     if(!root.check(root.current.basicFields.some(f=>f.key==="username")&&!root.current.basicFields.some(f=>f.key==="cert"),"password authentication hides TLS-only fields"))return;
     root.current.nested("data","connection-type","password-tls");
     if(!root.check(root.current.basicFields.some(f=>f.key==="username")&&root.current.basicFields.some(f=>f.key==="cert"),"combined authentication shows credentials and certificates"))return;
    }
    if(String(root.current.form.type??"").endsWith(".l2tp")){
     root.current.nested("data","user-auth-type","tls");
     if(!root.check(root.current.basicFields.some(f=>f.key==="user-cert")&&!root.current.basicFields.some(f=>f.key==="password"),"L2TP certificate authentication"))return;
     root.current.nested("data","ipsec-enabled","yes");root.current.nested("data","machine-auth-type","tls");
     if(!root.check(root.current.basicFields.some(f=>f.key==="machine-cert")&&!root.current.basicFields.some(f=>f.key==="ipsec-psk"),"IPsec certificate and PSK fields are mutually exclusive"))return;
    }
    if(!root.check(root.findNamed(root.current,"vpnProtocolSelector")!==null,"existing VPN protocol has an editable selector"))return;
    root.current.vpnBackend=root.fakeEditorVpn;
    const original=JSON.parse(JSON.stringify(root.current.form));
    root.current.requestProtocol("wireguard");
    if(!root.check(root.current.form.type===original.type,"protocol selection requires confirmation"))return;
    root.current.pendingProtocol="";
    if(!root.check(JSON.stringify(root.current.form)===JSON.stringify(original),"cancel protocol change preserves all fields"))return;
    if(String(original.type??"").endsWith(".openvpn")){
     root.current.form=Object.assign({},root.current.form,{name:"Keep name",data:Object.assign({},root.current.form.data,{remote:"vpn.example",username:"alice"}),secrets:{password:"old-protocol-secret"}});
     root.current.requestProtocol("wireguard");root.current.applyProtocol();
     if(!root.check(root.current.form.type==="wireguard"&&root.current.form.name==="Keep name"&&Object.keys(root.current.form.secrets).length===0,"protocol change clears incompatible secrets and keeps identity"))return;
     root.current.requestProtocol(original.type);root.current.applyProtocol();
     if(!root.check(root.current.form.data.remote==="vpn.example"&&root.current.form.secrets.password==="old-protocol-secret","switching back restores unsaved protocol fields"))return;
    }
    root.current.advanced=true;
   }
   if(["ClipboardPage.qml","ShortcutEditorPage.qml","WorkspaceSessionPage.qml"].includes(path)&&Quickshell.env("HICS_UI_PREVIEW_DIR")){
    screenshot.file=Quickshell.env("HICS_UI_PREVIEW_DIR")+"/"+path+".png";screenshot.restart();
   }
   GlobalConfig.appearance.highContrast = Quickshell.env("HICS_UI_PREVIEW_DIR")?false:root.phase % 2 === 1;
   if(Quickshell.env("HICS_UI_PREVIEW_DIR")){const hide=["ClipboardPage.qml","ShortcutEditorPage.qml","WorkspaceSessionPage.qml"].includes(path);testBar.visible=!hide;popupPanels.visible=!hide;}
   GlobalConfig.appearance.reducedMotion = true;
   console.log("PAGE_OK", path);
  }
 }
 Timer { interval: 55000; running: true; onTriggered: { console.error("DESKTOP_UI_TIMEOUT"); Qt.quit(); } }
}'''.replace('__DESIGN_PAGES__',json.dumps([str(p.relative_to(ROOT/'shell/modules/nexus/pages')) for p in (ROOT/'shell/modules/nexus/pages').rglob('*.qml') if 'PageBase {' in p.read_text() and any(part in str(p.relative_to(ROOT/'shell/modules/nexus/pages')) for part in ('panels/', 'keyboard/', 'audio/', 'network/NetworkDetail', 'network/EthernetDetail', 'network/SavedNetworks', 'network/AllNetworks', 'network/AddVpn'))])).replace('__VPN_PROTOCOLS__',json.dumps(json.loads((ROOT/'shell/plugin/src/Hyprstack/Services/vpn-protocols.json').read_text()))))
    tools = base / 'tools'
    tools.mkdir()
    fake = '#!/usr/bin/python3\nimport sys,json\nprint(json.dumps({"error":"Test backend unavailable"}) if "status" in sys.argv or "apply" in sys.argv else "[]")\n'
    for name in ('hyprctl', 'nmcli', 'hics', 'hics-systemctl', 'pactl', 'pw-dump'):
        path = tools / name
        if name == 'pactl':
            path.write_text('#!/usr/bin/python3\nimport json\nprint(json.dumps([{"name":"test-card","properties":{"device.description":"Test card"},"active_profile":"stereo","profiles":{"stereo":{"description":"Stereo","available":"yes"}}}]))\n')
        elif name == 'pw-dump':
            path.write_text('#!/usr/bin/python3\nimport json\nprint(json.dumps([{"id":1,"info":{"state":"running","props":{"media.class":"Stream/Input/Video","application.name":"Test camera"}}}]))\n')
        elif name == 'nmcli':
            path.write_text('#!/usr/bin/python3\nimport os,json,sys\nwith open(os.environ["TEST_NETWORK_LOG"], "a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\nprint("")\n')
        else:
            path.write_text(fake)
        path.chmod(0o700)
    (base/'config/hics').mkdir(parents=True,exist_ok=True)
    (base/'config/hics/plugins.json').write_text(json.dumps({'enabled':{'isolated-counter':True}}))
    (base/'config/hics/workspace.json').write_text(json.dumps({'clipboard':{'enabled':False}}))
    env = dict(os.environ, QT_QPA_PLATFORM='wayland', QT_QUICK_BACKEND='software',
        XDG_CONFIG_HOME=str(base / 'config'), XDG_STATE_HOME=str(base / 'state'),
        XDG_DATA_HOME=str(base / 'data'), XDG_CACHE_HOME=str(base / 'cache'),
        TEST_NETWORK_LOG=str(base / 'network.log'), XDG_RUNTIME_DIR=str(base / 'runtime'), QML_IMPORT_PATH=str(ROOT / 'build/qml'),
        QML2_IMPORT_PATH=str(ROOT / 'build/qml'), HYPRSTACK_NESTED='1',
        PATH=str(tools) + ':' + os.environ['PATH'])
    if os.environ.get('HICS_UI_HARDWARE'):
        env.pop('QT_QUICK_BACKEND',None)
        env['QSG_RHI_BACKEND']='opengl'
    Path(env['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
    env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    env.pop('WAYLAND_DISPLAY', None)
    # Use one private bus for both APIs so no host service can be activated.
    runner = base / 'run.py'
    runner.write_text('import os,sys\nos.environ["DBUS_SYSTEM_BUS_ADDRESS"]=os.environ["DBUS_SESSION_BUS_ADDRESS"]\nos.execvp(sys.argv[1],sys.argv[1:])\n')
    compositor = None
    try:
        display = os.environ.get('WAYLAND_DISPLAY')
        if not display:
            raise SystemExit('This integration test needs a parent Wayland session')
        parent = display if display.startswith('/') else str(Path(os.environ['XDG_RUNTIME_DIR']) / display)
        config = base / 'compositor.lua'
        config.write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
        nestedEnv = dict(env, WAYLAND_DISPLAY=parent, AQ_BACKEND='wayland')
        nestedEnv['PATH'] = os.environ['PATH']
        with (base / 'compositor.log').open('w') as log:
            compositor = subprocess.Popen(['Hyprland', '--config', str(config)], env=nestedEnv, stdout=log, stderr=subprocess.STDOUT)
        sockets = []
        for _ in range(80):
            sockets = [p for p in Path(env['XDG_RUNTIME_DIR']).glob('wayland-*') if p.is_socket()]
            if sockets or compositor.poll() is not None:
                break
            time.sleep(.1)
        if not sockets:
            raise RuntimeError((base / 'compositor.log').read_text()[-5000:])
        time.sleep(.7)
        env['WAYLAND_DISPLAY'] = str(sockets[0])
        instances = list((Path(env['XDG_RUNTIME_DIR']) / 'hypr').glob('*'))
        if instances:
            env['HYPRLAND_INSTANCE_SIGNATURE'] = instances[0].name
        run = subprocess.run(['dbus-run-session', '--', 'python3', str(runner),
            'quickshell', '-p', str(shell)], env=env, capture_output=True, text=True, timeout=120)
        output = run.stdout + run.stderr
        print(output[-24000:])
        assert run.returncode == 0 and 'DESKTOP_UI_OK' in output and 'VPN_CREDENTIALS_DELETE_OK' in output and 'ISOLATED_RESTART_OK' in output and 'ISOLATED_WIDGET_OK' in output and 'SETTINGS_EXPANSION_OK' in output and 'NETWORK_QUICK_VPN_OK' in output and 'SCROLL_REFRESH_OK' in output and 'NOTIFICATION_ACTIVATION_OK' in output and 'NOTIFICATION_DBUS_ACTION_OK' in output and 'NOTIFICATION_POPUP_LAYOUT_OK' in output, 'Pages failed to construct'
        forbidden = ('TypeError:', 'ReferenceError:', 'Unable to assign', 'PAGE_CREATION_FAILED', 'Cannot assign to non-existent', 'Binding loop', 'NOTIFICATION_TEST_FAILED')
        assert not any(message in output for message in forbidden), 'QML runtime errors'
        import json
        commands = [json.loads(line) for line in (base / 'network.log').read_text().splitlines()]
        assert ['connection', 'modify', 'Saved network', 'connection.autoconnect', 'no'] in commands
        assert not any('delete' in cmd or '802-11-wireless-security.psk' in cmd or '802-11-wireless-security.psk-flags' in cmd for cmd in commands)
        print('PASS: all navigation pages, profile menus, notification delivery, palettes and autoconnect credential preservation')
    finally:
        if compositor and compositor.poll() is None:
            compositor.terminate()
            compositor.wait(timeout=5)
