"""Accounts, logind, fingerprint and colord fixtures on a private system bus."""
import json, os
import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.bus.BusConnection(os.environ['DBUS_SYSTEM_BUS_ADDRESS'])
names=[dbus.service.BusName(n,bus) for n in ['org.freedesktop.Accounts','org.freedesktop.login1','net.reactivated.Fprint','org.freedesktop.ColorManager']]
def log(method,*args):
 with open(os.environ['HICS_PLATFORM_TRACE'],'a') as f:f.write(json.dumps([method,*args])+ '\n')
class User(dbus.service.Object):
 def __init__(self,uid,name,admin=False,system=False):
  self.path='/org/freedesktop/Accounts/User'+str(uid);self.props={'Uid':dbus.UInt64(uid),'UserName':name,'RealName':name.title(),'SystemAccount':system,'AccountType':dbus.Int32(int(admin)),'Locked':False};super().__init__(bus,self.path)
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='s',out_signature='a{sv}')
 def GetAll(self,interface):return self.props
 @dbus.service.method('org.freedesktop.Accounts.User',in_signature='i')
 def SetAccountType(self,value):self.props['AccountType']=value;log('role',self.path,int(value))
 @dbus.service.method('org.freedesktop.Accounts.User',in_signature='s')
 def SetRealName(self,value):
  if value=='Denied':raise dbus.exceptions.DBusException('Authorization denied',name='org.freedesktop.Accounts.Error.PermissionDenied')
  self.props['RealName']=value;log('rename',self.path,str(value))
users=[User(0,'root',True,True),User(1000,'alex',True),User(1001,'guest')]
class Accounts(dbus.service.Object):
 @dbus.service.method('org.freedesktop.Accounts',out_signature='ao')
 def ListCachedUsers(self):return [dbus.ObjectPath(u.path) for u in users]
 @dbus.service.method('org.freedesktop.Accounts',in_signature='ssi',out_signature='o')
 def CreateUser(self,name,real,kind):
  log('create',str(name),str(real),int(kind));u=User(1000+len(users),str(name),bool(kind));u.props['RealName']=real;u.props['Locked']=True;users.append(u);return dbus.ObjectPath(u.path)
class Login(dbus.service.Object):
 @dbus.service.method('org.freedesktop.login1.Manager',out_signature='a(susso)')
 def ListSessions(self):return [('test-current',1000,'alex','seat0',dbus.ObjectPath('/org/freedesktop/login1/session/current')),('other',1001,'guest','seat1',dbus.ObjectPath('/org/freedesktop/login1/session/other'))]
 @dbus.service.method('org.freedesktop.login1.Manager',in_signature='s')
 def ActivateSession(self,id):log('activate',str(id))
 @dbus.service.method('org.freedesktop.login1.Manager',in_signature='s')
 def TerminateSession(self,id):log('terminate',str(id))
class FingerManager(dbus.service.Object):
 @dbus.service.method('net.reactivated.Fprint.Manager',out_signature='o')
 def GetDefaultDevice(self):return dbus.ObjectPath('/net/reactivated/Fprint/Device/0')
class Finger(dbus.service.Object):
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='s',out_signature='a{sv}')
 def GetAll(self,interface):return {'name':'Fixture reader'}
 @dbus.service.method('net.reactivated.Fprint.Device',in_signature='s',out_signature='as')
 def ListEnrolledFingers(self,user):return ['right-index-finger']
 @dbus.service.method('net.reactivated.Fprint.Device',in_signature='s')
 def Claim(self,user):log('finger-claim',str(user))
 @dbus.service.method('net.reactivated.Fprint.Device')
 def Release(self):log('finger-release')
 @dbus.service.method('net.reactivated.Fprint.Device',in_signature='s')
 def DeleteEnrolledFinger(self,finger):log('finger-delete',str(finger))
class Colour(dbus.service.Object):
 @dbus.service.method('org.freedesktop.ColorManager',out_signature='ao')
 def GetProfiles(self):return []
objects=[Accounts(bus,'/org/freedesktop/Accounts'),Login(bus,'/org/freedesktop/login1'),FingerManager(bus,'/net/reactivated/Fprint/Manager'),Finger(bus,'/net/reactivated/Fprint/Device/0'),Colour(bus,'/org/freedesktop/ColorManager')]
print('ready',flush=True)
GLib.MainLoop().run()
