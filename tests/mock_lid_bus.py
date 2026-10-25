"""Private logind that passes a real inhibitor FD and emits Active changes."""
import os,dbus,dbus.service,dbus.mainloop.glib
from gi.repository import GLib
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus=dbus.bus.BusConnection(os.environ['DBUS_SYSTEM_BUS_ADDRESS']);owner=dbus.service.BusName('org.freedesktop.login1',bus)
class Session(dbus.service.Object):
 active=True
 def __init__(self):super().__init__(bus,'/org/freedesktop/login1/session/test')
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
 def Get(self,interface,key):assert key=='Active';return dbus.Boolean(self.active)
 @dbus.service.signal('org.freedesktop.DBus.Properties',signature='sa{sv}as')
 def PropertiesChanged(self,interface,values,invalidated):pass
 @dbus.service.method('org.hics.Test',in_signature='b')
 def SetActive(self,value):self.active=bool(value);self.PropertiesChanged('org.freedesktop.login1.Session',{'Active':dbus.Boolean(value)},[])
class Manager(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/org/freedesktop/login1');self.readers=[]
 @dbus.service.method('org.freedesktop.login1.Manager',in_signature='s',out_signature='o')
 def GetSession(self,name):assert name=='auto';return '/org/freedesktop/login1/session/test'
 @dbus.service.method('org.freedesktop.login1.Manager',in_signature='ssss',out_signature='h')
 def Inhibit(self,what,who,why,mode):
  assert what=='handle-lid-switch' and mode=='block'
  reader,writer=os.pipe();self.readers.append(reader);fd=dbus.types.UnixFd(writer);os.close(writer);return fd
session=Session();manager=Manager();print('ready',flush=True);GLib.MainLoop().run()
