"""Private NetworkManager settings service. No host connections are modified."""
import dbus,dbus.service,json,os
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.SystemBus();name=dbus.service.BusName('org.freedesktop.NetworkManager',bus)
ROOT='/org/freedesktop/NetworkManager';IF='org.freedesktop.NetworkManager.Settings.Connection'
def settings(kind='vpn'):
 result={'connection':{'id':'Fixture VPN','uuid':'11111111-2222-4333-8444-555555555555','type':kind,'autoconnect':False},'ipv4':{'method':'auto','dns':dbus.Array([dbus.UInt32(16843009)],signature='u'),'dns-search':dbus.Array(['~internal.example'],signature='s'),'route-data':dbus.Array([dbus.Dictionary({'dest':'10.7.0.0','prefix':dbus.UInt32(16),'next-hop':'10.1.0.1','table':dbus.UInt32(123)},signature='sv')],signature='a{sv}')},'ipv6':{'method':'auto'}}
 if kind=='vpn':result['vpn']={'service-type':'org.freedesktop.NetworkManager.openvpn','data':dbus.Dictionary({'remote':'vpn.example','connection-type':'password','vendor-option':'keep-me','password-flags':'0'},signature='ss')}
 return dbus.Dictionary({key:dbus.Dictionary(value,signature='sv') for key,value in result.items()},signature='sa{sv}')
def log(method,data=None):
 with open(os.environ['VPN_TEST_LOG'],'a') as f:f.write(json.dumps({'method':method,'data':data},default=str)+'\n')
class Profile(dbus.service.Object):
 def __init__(self,index,data):
  self.data=data;self.path=ROOT+'/Settings/'+str(index);super().__init__(bus,self.path)
 @dbus.service.method(IF,out_signature='a{sa{sv}}')
 def GetSettings(self):return self.data
 @dbus.service.method(IF,in_signature='s',out_signature='a{sa{sv}}')
 def GetSecrets(self,setting):
  log('GetSecrets')
  return {'vpn':{'secrets':dbus.Dictionary({'password':'stored-password'},signature='ss')}}
 @dbus.service.method(IF,in_signature='a{sa{sv}}ua{sv}',out_signature='a{sv}')
 def Update2(self,data,flags,args):self.data=data;log('Update2',data);return {}
 @dbus.service.method(IF)
 def Delete(self):log('Delete');profiles.pop(self.path,None)
class Settings(dbus.service.Object):
 @dbus.service.method('org.freedesktop.NetworkManager.Settings',out_signature='ao')
 def ListConnections(self):return list(profiles)
 @dbus.service.method('org.freedesktop.NetworkManager.Settings',in_signature='a{sa{sv}}ua{sv}',out_signature='oa{sv}')
 def AddConnection2(self,data,flags,args):
  log('AddConnection2',data);p=Profile(10+len(profiles),data);profiles[p.path]=p;return p.path,{}
class Manager(dbus.service.Object):
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
 def Get(self,iface,prop):
  if prop=='ActiveConnections':return dbus.Array([],signature='o')
  raise dbus.exceptions.DBusException('Unknown property')
 @dbus.service.method('org.freedesktop.NetworkManager',in_signature='ooo',out_signature='o')
 def ActivateConnection(self,path,device,specific):log('ActivateConnection',path);return ROOT+'/ActiveConnection/1'
 @dbus.service.method('org.freedesktop.NetworkManager',in_signature='o')
 def DeactivateConnection(self,path):log('DeactivateConnection',path)
secret_name=dbus.service.BusName('org.freedesktop.secrets',bus)
class SecretStore(dbus.service.Object):
 @dbus.service.method('org.freedesktop.Secret.Service',in_signature='sv',out_signature='vo')
 def OpenSession(self,algorithm,input):
  if algorithm!='plain':raise dbus.exceptions.DBusException('Plain fixture sessions only',name='org.freedesktop.DBus.Error.NotSupported')
  return dbus.String('',variant_level=1),dbus.ObjectPath('/org/freedesktop/secrets/session/fixture')
 @dbus.service.method('org.freedesktop.Secret.Service',in_signature='a{ss}',out_signature='aoao')
 def SearchItems(self,attributes):return dbus.Array([],signature='o'),dbus.Array([],signature='o')
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='s',out_signature='a{sv}')
 def GetAll(self,interface):return {'Collections':dbus.Array([],signature='o')}
 @dbus.service.method('org.freedesktop.Secret.Service',in_signature='s',out_signature='o')
 def ReadAlias(self,alias):return dbus.ObjectPath('/')
secret_store=SecretStore(bus,'/org/freedesktop/secrets')
class AgentManager(dbus.service.Object):
 sender=None
 @dbus.service.method('org.freedesktop.NetworkManager.AgentManager',in_signature='su',sender_keyword='sender')
 def RegisterWithCapabilities(self,identifier,capabilities,sender=None):self.sender=sender
 @dbus.service.method('org.hics.Test',in_signature='ss',out_signature='s',async_callbacks=('reply','error'))
 def Request(self,mode,sender,reply,error):
  connection=settings();connection['vpn']['service-type']='org.freedesktop.NetworkManager.pptp' if mode=='agent-plugin-submit' else 'org.hics.fixture.no-plugin'
  if mode=='agent-plugin-submit':connection['vpn']['data']=dbus.Dictionary({'gateway':'vpn.example','user':'fixture','password-flags':'2'},signature='ss')
  agent=dbus.Interface(bus.get_object(sender,'/org/freedesktop/NetworkManager/SecretAgent',introspect=False),'org.freedesktop.NetworkManager.SecretAgent')
  def success(result):reply(json.dumps({'password':str(result.get('vpn',{}).get('secrets',{}).get('password',''))}))
  def failure(exception):reply(json.dumps({'errorName':exception.get_dbus_name()}))
  agent.GetSecrets(connection,dbus.ObjectPath(ROOT+'/Settings/1'),'vpn',dbus.Array(['password'],signature='s'),dbus.UInt32(0 if mode=='agent-no-interaction' else 3),reply_handler=success,error_handler=failure,timeout=10)
agent_manager=AgentManager(bus,ROOT+'/AgentManager')
profiles={}
p=Profile(1,settings());profiles[p.path]=p
p=Profile(2,settings('802-3-ethernet'));profiles[p.path]=p
manager=Manager(bus,ROOT);store=Settings(bus,ROOT+'/Settings')
print('ready',flush=True)
GLib.MainLoop().run()
