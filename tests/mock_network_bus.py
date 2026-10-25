"""Private cached libnm model: Wi-Fi, Ethernet, APs and 30 saved profiles."""
import dbus,dbus.service,json,os
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.SystemBus();name=dbus.service.BusName('org.freedesktop.NetworkManager',bus)
NM='org.freedesktop.NetworkManager';ROOT='/org/freedesktop/NetworkManager';objects={}
def log(method,data=None):
 with open(os.environ['NETWORK_TEST_LOG'],'a') as stream:stream.write(json.dumps({'method':method,'data':data},default=str)+'\n')
def paths(values):return dbus.Array(values,signature='o')
class Object(dbus.service.Object):
 def __init__(self,path,interfaces):self.path=path;self.interfaces=interfaces;objects[path]=self;super().__init__(bus,path)
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='s',out_signature='a{sv}')
 def GetAll(self,interface):return self.interfaces.get(interface,{})
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
 def Get(self,interface,property):return self.interfaces[interface][property]
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ssv')
 def Set(self,interface,property,value):
  log('Set',{'interface':interface,'property':property,'value':value})
  if property=='WirelessEnabled' and not value:raise dbus.exceptions.DBusException('Fixture denied radio change',name='org.freedesktop.NetworkManager.PermissionDenied')
  self.interfaces[interface][property]=value;self.PropertiesChanged(interface,{property:value},[])
 @dbus.service.signal('org.freedesktop.DBus.Properties',signature='sa{sv}as')
 def PropertiesChanged(self,interface,changed,invalidated):pass
class ObjectManager(dbus.service.Object):
 @dbus.service.method('org.freedesktop.DBus.ObjectManager',out_signature='a{oa{sa{sv}}}')
 def GetManagedObjects(self):return {p:o.interfaces for p,o in objects.items()}
 @dbus.service.signal('org.freedesktop.DBus.ObjectManager',signature='oas')
 def InterfacesRemoved(self,path,interfaces):pass
manager=ObjectManager(bus,'/org/freedesktop')
class Profile(Object):
 def __init__(self,index):
  self.settings={'connection':{'id':'Wired fixture' if index==31 else f'Wi-Fi:{index}','uuid':f'11111111-2222-4333-8444-{index:012d}','type':'802-3-ethernet' if index==31 else '802-11-wireless','autoconnect':True},'ipv4':{'method':'auto'},'ipv6':{'method':'auto','dns-search':dbus.Array(['keep.example'],signature='s')}}
  if index==31:self.settings['802-3-ethernet']={}
  else:self.settings['802-11-wireless']={'ssid':dbus.ByteArray(('Cafe:Сеть' if index==1 else f'Saved {index}').encode())};self.settings['802-11-wireless-security']={'key-mgmt':'wpa-psk'}
  super().__init__(ROOT+'/Settings/'+str(index),{NM+'.Settings.Connection':{'Unsaved':False,'Flags':dbus.UInt32(0),'Filename':''}})
 @dbus.service.method(NM+'.Settings.Connection',out_signature='a{sa{sv}}')
 def GetSettings(self):log('GetSettings',self.path);return {k:dbus.Dictionary(v,signature='sv') for k,v in self.settings.items()}
 @dbus.service.signal(NM+'.Settings.Connection')
 def Updated(self):pass
 @dbus.service.method(NM+'.Settings.Connection',in_signature='a{sa{sv}}ua{sv}',out_signature='a{sv}')
 def Update2(self,settings,flags,args):self.settings=settings;log('Update2',settings);self.Updated();return {}
 @dbus.service.method(NM+'.Settings.Connection')
 def Delete(self):log('Delete',self.path);manager.InterfacesRemoved(self.path,list(self.interfaces));objects.pop(self.path,None)
profiles=[Profile(i) for i in range(1,32)]
Object(ROOT+'/Settings',{NM+'.Settings':{'Connections':paths([p.path for p in profiles]),'Hostname':'fixture','CanModify':True}})
IP=ROOT+'/IP4Config/1';AC=ROOT+'/ActiveConnection/1';AP=ROOT+'/AccessPoint/1';WIFI=ROOT+'/Devices/1';ETH=ROOT+'/Devices/2'
Object(IP,{NM+'.IP4Config':{'AddressData':dbus.Array([dbus.Dictionary({'address':'192.0.2.10','prefix':dbus.UInt32(24)},signature='sv')],signature='a{sv}'),'Gateway':'192.0.2.1','NameserverData':dbus.Array([dbus.Dictionary({'address':'1.1.1.1'},signature='sv')],signature='a{sv}') }})
Object(AP,{NM+'.AccessPoint':{'Ssid':dbus.ByteArray('Cafe:Сеть'.encode()),'Strength':dbus.Byte(77),'Frequency':dbus.UInt32(5180),'HwAddress':'AA:BB:CC:DD:EE:FF','Flags':dbus.UInt32(1),'WpaFlags':dbus.UInt32(0),'RsnFlags':dbus.UInt32(256),'Mode':dbus.UInt32(2)}})
Object(AC,{NM+'.Connection.Active':{'Connection':dbus.ObjectPath(profiles[-1].path),'Id':'Wired fixture','Uuid':profiles[-1].settings['connection']['uuid'],'Type':'802-3-ethernet','Devices':paths([ETH]),'State':dbus.UInt32(2),'Default':True,'Ip4Config':dbus.ObjectPath(IP)}})
class Device(Object):
 @dbus.service.method(NM+'.Device')
 def Disconnect(self):log('Disconnect',self.path)
 @dbus.service.method(NM+'.Device.Wireless',in_signature='a{sv}')
 def RequestScan(self,options):log('RequestScan')
for index,kind in ((1,2),(2,1)):
 general={'Interface':'wlan-fixture' if index==1 else 'eth-fixture','IpInterface':'wlan-fixture' if index==1 else 'eth-fixture','DeviceType':dbus.UInt32(kind),'State':dbus.UInt32(30 if index==1 else 100),'StateReason':dbus.Struct((dbus.UInt32(30 if index==1 else 100),dbus.UInt32(0)),signature='uu'),'Managed':True,'Real':True,'Ip4Config':dbus.ObjectPath('/' if index==1 else IP),'ActiveConnection':dbus.ObjectPath('/' if index==1 else AC),'HwAddress':'00:11:22:33:44:55','InterfaceFlags':dbus.UInt32(3)}
 interfaces={NM+'.Device':general}
 if index==1:interfaces[NM+'.Device.Wireless']={'AccessPoints':paths([AP]),'ActiveAccessPoint':dbus.ObjectPath('/'),'WirelessCapabilities':dbus.UInt32(1023),'Mode':dbus.UInt32(2),'LastScan':dbus.Int64(10)}
 else:interfaces[NM+'.Device.Wired']={'Carrier':True,'Speed':dbus.UInt32(1000),'HwAddress':'00:11:22:33:44:55'}
 Device(ROOT+'/Devices/'+str(index),interfaces)
class Manager(Object):
 @dbus.service.method(NM,out_signature='a{ss}')
 def GetPermissions(self):return {'org.freedesktop.NetworkManager.network-control':'yes','org.freedesktop.NetworkManager.settings.modify.system':'yes'}
 @dbus.service.method(NM,in_signature='ooo',out_signature='o')
 def ActivateConnection(self,profile,device,specific):log('ActivateConnection',profile);return AC
 @dbus.service.method(NM,out_signature='u')
 def CheckConnectivity(self):log('CheckConnectivity');return self.interfaces[NM]['Connectivity']
 @dbus.service.method('org.hics.Test')
 def Signal(self):
  objects[AP].interfaces[NM+'.AccessPoint']['Strength']=dbus.Byte(33)
  objects[AP].PropertiesChanged(NM+'.AccessPoint',{'Strength':dbus.Byte(33)},[])
  self.interfaces[NM]['Connectivity']=dbus.UInt32(2)
  self.PropertiesChanged(NM,{'Connectivity':dbus.UInt32(2)},[])
root=Manager(ROOT,{NM:{'Version':'1.52.0','State':dbus.UInt32(70),'NetworkingEnabled':True,'WirelessEnabled':True,'WirelessHardwareEnabled':True,'Devices':paths([WIFI,ETH]),'AllDevices':paths([WIFI,ETH]),'ActiveConnections':paths([AC]),'PrimaryConnection':dbus.ObjectPath(AC),'Connectivity':dbus.UInt32(4),'Startup':False}})
print('ready',flush=True)
GLib.MainLoop().run()
