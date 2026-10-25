pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Services
import Hyprstack.I18n
import qs.utils
// Compatibility facade for existing settings/widgets. All network I/O lives in
// the single native NMClient; this object owns no process or polling monitor.
Singleton {
 id:root
 property string lastError:""
 readonly property var state:NetworkService.state
 readonly property var wirelessInterfaces:state.wireless??[]
 readonly property var ethernetInterfaces:state.ethernet??[]
 readonly property var deviceStatus:[...wirelessInterfaces,...ethernetInterfaces]
 readonly property bool isConnected:state.connected??false
 readonly property bool connecting:wirelessInterfaces.some(i=>isConnectingState(i.state))
 readonly property string activeInterface:state.activeInterface??""
 readonly property string activeConnection:state.activeConnection??""
 readonly property bool wifiEnabled:state.wifiEnabled??false
 property bool scanning:false
 readonly property list<AccessPoint> networks:[]
 readonly property AccessPoint active:networks.find(n=>n.active)??null
 readonly property list<EthernetDevice> ethernetDevices:[]
 readonly property EthernetDevice activeEthernet:ethernetDevices.find(d=>d.connected)??null
 readonly property bool hasAvailableEthernet:ethernetInterfaces.some(d=>d.carrier)
 readonly property var profiles:state.profiles??[]
 readonly property var savedConnections:profiles.map(p=>p.id)
 readonly property var savedConnectionSsids:profiles.filter(p=>p.ssid).map(p=>p.ssid)
 readonly property var savedConnectionSecurity:{const result={};for(const p of profiles)if(p.ssid)result[p.ssid.toLowerCase().trim()]=p.security;return result;}
 property var wirelessDeviceDetails:null
 property var ethernetDeviceDetails:null
 property string ethernetDataUsage:""
 property string ethernetSpeed:""
 property var pendingConnection:null
 property var callbacks:({})
 property int generation:0
 signal connectionFailed(string ssid)
 readonly property alias connectionCheckTimer:connectionTimeout
 readonly property alias immediateCheckTimer:immediateCheck
 function isConnectedState(state:string):bool{return state==="connected"||state.startsWith("100 ");}
 function isConnectingState(state:string):bool{return state.startsWith("connecting");}
 function connectingSsid():string{return pendingConnection?.ssid??wirelessInterfaces.find(i=>isConnectingState(i.state))?.connection??"";}
 function run(op:string,args:var,callback=null):void {
  const id=NetworkService.request(op,args??{});if(callback)callbacks[id]=callback;
 }
 function refreshOnConnectionChange():void{run("refresh",{});}
 function profile(name:string):var{return profiles.find(p=>p.uuid===name||p.id===name||p.ssid===name);}
 function savedSecurityFor(ssid:string):string{return savedConnectionSecurity[ssid.toLowerCase().trim()]??"";}
 function hasSavedProfile(ssid:string):bool{return profiles.some(p=>p.ssid===ssid||p.id===ssid);}
 function findNetwork(ssid:string):var{return networks.find(n=>n.ssid===ssid)??null;}
 function syncObjects(items:var,rows:var,component:var,key:string):void {
  const wanted=new Map(rows.map(row=>[row[key],row]));
  for(let i=items.length-1;i>=0;--i)if(!wanted.has(items[i].lastIpcObject[key])){const removed=items.splice(i,1)[0];removed.destroy();}
  for(const row of rows){const object=items.find(o=>o.lastIpcObject[key]===row[key]);if(object)object.lastIpcObject=row;else items.push(component.createObject(root,{lastIpcObject:row}));}
 }
 function details(iface:string,rows:var):var {
  const row=rows.find(d=>d.interface===iface)??rows.find(d=>d.connected);if(!row)return null;
  const result=Object.assign({},row);result.ipv4=row.ipAddress;result.mac=row.macAddress;
  const stats=NetworkService.interfaceStats(row.interface);result.speed=stats.speedMbps?stats.speedMbps>=1000?(stats.speedMbps/1000)+" Gbps":stats.speedMbps+" Mbps":"";
  return result;
 }
 onStateChanged:{
  syncObjects(networks,state.networks??[],accessPoint,"ssid");syncObjects(ethernetDevices,ethernetInterfaces,ethernetDevice,"interface");
  wirelessDeviceDetails=details(wirelessDeviceDetails?.interface??"",wirelessInterfaces);
  ethernetDeviceDetails=details(ethernetDeviceDetails?.interface??"",ethernetInterfaces);
  if(pendingConnection){
   const wifi=wirelessInterfaces.find(i=>i.interface===pendingConnection.interface)??wirelessInterfaces[0];
   if(active?.ssid===pendingConnection.ssid&&wirelessInterfaces.some(i=>i.connected))finishConnection({success:true,output:"Connected",error:"",exitCode:0});
   else if(wifi?.failed&&pendingConnection.started)finishConnection({success:false,error:Tr.tr("Connection failed (NetworkManager reason %1)").arg(wifi.reason),needsPassword:wifi.needsPassword,exitCode:1});
  }
 }
 function finishConnection(result:var):void {
  const pending=pendingConnection;pendingConnection=null;connectionTimeout.stop();
  if(!result.success){lastError=result.error??Tr.tr("Network operation failed");if(pending)connectionFailed(pending.ssid);}else lastError="";
  if(pending?.callback)pending.callback(result);
 }
 function connectToNetwork(ssid:string,password:string,bssid:string,callback:var):void {
  const current=++generation;const point=findNetwork(ssid);
  pendingConnection={ssid:ssid,bssid:bssid??"",interface:point?.lastIpcObject.interface??wirelessInterfaces[0]?.interface??"",callback:callback,started:false};connectionTimeout.restart();
  run("connect",{ssid:ssid,password:password??"",bssid:bssid??"",interface:pendingConnection.interface,hidden:!point},result=>{
   if(current!==generation||!pendingConnection)return;
   if(!result.success)finishConnection(result);else {pendingConnection=Object.assign({},pendingConnection,{started:true});if(active?.ssid===ssid&&wirelessInterfaces.some(i=>i.connected))finishConnection(result);}
  });
 }
 function connectToNetworkWithPasswordCheck(ssid:string,secure:bool,callback:var,bssid:string):void {connectToNetwork(ssid,"",bssid,callback);}
 function connectWireless(ssid:string,password:string,bssid:string,callback:var):void {connectToNetwork(ssid,password,bssid,callback);}
 function disconnectFromNetwork(ssid:string,callback:var):void {
  const point=findNetwork(ssid);run("disconnect",{interface:point?.lastIpcObject.interface??wirelessInterfaces[0]?.interface??""},callback);
 }
 function forgetNetwork(ssid:string,callback:var):void {run("forget",{connection:profile(ssid)?.uuid??ssid},callback);}
 function connectEthernet(name:string,iface:string,callback:var):void {run("activate",{connection:name,interface:iface},callback);}
 function disconnectEthernet(name:string,callback:var):void {run("disconnect",{connection:name},callback);}
 function enableWifi(enabled:bool,callback:var):void {run("wifi",{enabled:enabled},callback);}
 function toggleWifi(callback:var):void {enableWifi(!wifiEnabled,callback);}
 function rescanWifi():void {if(scanning)return;scanning=true;run("scan",{},result=>{scanning=false;if(!result.success)lastError=result.error;});}
 function scanWirelessNetworks(iface:string,callback:var):void {run("scan",{interface:iface},callback);}
 function getWirelessInterfaces(callback:var):void {if(callback)callback(wirelessInterfaces);}
 function getEthernetInterfaces(callback:var):void {if(callback)callback(ethernetInterfaces);}
 function getAllInterfaces(callback:var):void {if(callback)callback(deviceStatus);}
 function getNetworks(callback:var):void {if(callback)callback(networks);}
 function loadSavedConnections(callback:var):void {if(callback)callback(savedConnections);}
 function getWirelessDeviceDetails(iface:string,callback:var):void {wirelessDeviceDetails=details(iface,wirelessInterfaces);if(callback)callback(wirelessDeviceDetails);}
 function getEthernetDeviceDetails(iface:string,callback:var):void {ethernetDeviceDetails=details(iface,ethernetInterfaces);getEthernetSpeed(iface||activeEthernet?.iface||"");getEthernetDataUsage(iface||activeEthernet?.iface||"",null);if(callback)callback(ethernetDeviceDetails);}
 function getEthernetSpeed(iface:string):void {const speed=NetworkService.interfaceStats(iface).speedMbps;ethernetSpeed=speed>0?(speed>=1000?(speed/1000)+" Gbps":speed+" Mbps"):"";}
 function getEthernetDataUsage(iface:string,callback:var):void {const stats=NetworkService.interfaceStats(iface);ethernetDataUsage=stats.rx===undefined?"":Units.formatBytes(Number(stats.rx)+Number(stats.tx));if(callback)callback(ethernetDataUsage);}
 function getIpv4Config(name:string,callback:var):void {if(callback)callback(profile(name)?.ipv4??null);}
 function setIpv4Config(name:string,config:var,callback:var):void {run("ipv4",{connection:profile(name)?.uuid??name,config:config},callback);}
 function getAutoconnect(name:string,callback:var):void {if(callback)callback(profile(name)?.autoconnect??true);}
 function setAutoconnect(name:string,enabled:bool,callback:var):void {run("autoconnect",{connection:profile(name)?.uuid??name,enabled:enabled},callback);}
 Timer {id:connectionTimeout;interval:60000;onTriggered:root.finishConnection({success:false,error:Tr.tr("Network connection timed out"),needsPassword:false,exitCode:1})}
 Timer {id:immediateCheck;property int checkCount:0;interval:1}
 Connections {target:NetworkService;function onOperationFinished(id:int,result:var):void {const callback=root.callbacks[id];delete root.callbacks[id];if(callback)callback(result);}}
 Component {id:accessPoint;AccessPoint{}}
 Component {id:ethernetDevice;EthernetDevice{}}
 component AccessPoint:QtObject {
  required property var lastIpcObject
  readonly property string ssid:lastIpcObject.ssid
  readonly property string bssid:lastIpcObject.bssid
  readonly property int strength:lastIpcObject.strength
  readonly property int frequency:lastIpcObject.frequency
  readonly property bool active:lastIpcObject.active
  readonly property string security:lastIpcObject.security
  readonly property bool isSecure:security.length>0
 }
 component EthernetDevice:QtObject {
  required property var lastIpcObject
  readonly property string iface:lastIpcObject.interface
  readonly property string type:lastIpcObject.type
  readonly property string state:lastIpcObject.state
  readonly property string connection:lastIpcObject.connection
  readonly property bool connected:lastIpcObject.connected
  readonly property string ipAddress:lastIpcObject.ipAddress??""
  readonly property string gateway:lastIpcObject.gateway??""
  readonly property var dns:lastIpcObject.dns??[]
  readonly property string subnet:lastIpcObject.subnet??""
  readonly property string macAddress:lastIpcObject.macAddress??""
  readonly property string speed:lastIpcObject.speed??""
 }
}
