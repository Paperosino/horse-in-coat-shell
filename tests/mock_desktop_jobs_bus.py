"""Private Fcitx, portal and OBEX fixture; never contacts host devices."""
import json
import os
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus()
names=[dbus.service.BusName(name,bus) for name in ['org.fcitx.Fcitx5','org.bluez.obex','sm.puri.OSK0','org.freedesktop.impl.portal.PermissionStore','org.freedesktop.FileManager1']]
class Input(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/controller');self.groups={'Default':('us',[('keyboard-us','')])};self.current='Default';self.method='keyboard-us'
 @dbus.service.method('org.fcitx.Fcitx.Controller1',out_signature='a(ssssssb)')
 def AvailableInputMethods(self):return [('keyboard-us','English','English','','','en',False),('keyboard-ru','Russian','Русский','','','ru',False)]
 @dbus.service.method('org.fcitx.Fcitx.Controller1',out_signature='as')
 def InputMethodGroups(self):return list(self.groups)
 @dbus.service.method('org.fcitx.Fcitx.Controller1',out_signature='s')
 def CurrentInputMethodGroup(self):return self.current
 @dbus.service.method('org.fcitx.Fcitx.Controller1',out_signature='s')
 def CurrentInputMethod(self):return self.method
 @dbus.service.method('org.fcitx.Fcitx.Controller1',in_signature='s',out_signature='sa(ss)')
 def InputMethodGroupInfo(self,group):return self.groups.get(str(group),('',[]))
 @dbus.service.method('org.fcitx.Fcitx.Controller1',in_signature='ssa(ss)')
 def SetInputMethodGroupInfo(self,group,layout,entries):self.groups[str(group)]=(str(layout),[(str(i),str(l)) for i,l in entries])
 @dbus.service.method('org.fcitx.Fcitx.Controller1',in_signature='s')
 def AddInputMethodGroup(self,group):self.groups[str(group)]=('us',[])
 @dbus.service.method('org.fcitx.Fcitx.Controller1',in_signature='s')
 def RemoveInputMethodGroup(self,group):self.groups.pop(str(group),None)
 @dbus.service.method('org.fcitx.Fcitx.Controller1',in_signature='s')
 def SwitchInputMethodGroup(self,group):self.current=str(group)
 @dbus.service.method('org.fcitx.Fcitx.Controller1',in_signature='s')
 def SetCurrentIM(self,method):self.method=str(method)
class Keyboard(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/sm/puri/OSK0')
 @dbus.service.method('sm.puri.OSK0',in_signature='b')
 def SetVisible(self,visible):pass
class Permissions(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/org/freedesktop/impl/portal/PermissionStore')
 @dbus.service.method('org.freedesktop.impl.portal.PermissionStore',in_signature='sbssas')
 def SetPermission(self,table,create,id,app,permissions):assert table=='devices' and id=='camera'
 @dbus.service.method('org.freedesktop.impl.portal.PermissionStore',in_signature='sss')
 def DeletePermission(self,table,id,app):pass
class Transfer(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/org/bluez/obex/session1/transfer1');self.state='active'
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='s',out_signature='a{sv}')
 def GetAll(self,interface):return {'Status':self.state,'Transferred':dbus.UInt64(2)}
 @dbus.service.signal('org.freedesktop.DBus.Properties',signature='sa{sv}as')
 def PropertiesChanged(self,interface,changes,invalid):pass
 @dbus.service.method('org.bluez.obex.Transfer1')
 def Cancel(self):self.state='error'
 def finish(self):self.state='complete';self.PropertiesChanged('org.bluez.obex.Transfer1',{'Status':'complete','Transferred':dbus.UInt64(8)},[]);return False
class Session(dbus.service.Object):
 def __init__(self,transfer):super().__init__(bus,'/org/bluez/obex/session1');self.transfer=transfer
 @dbus.service.method('org.bluez.obex.ObjectPush1',in_signature='s',out_signature='oa{sv}')
 def SendFile(self,path):GLib.timeout_add(300,self.transfer.finish);return ('/org/bluez/obex/session1/transfer1',{})
class Client(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/org/bluez/obex')
 @dbus.service.method('org.bluez.obex.Client1',in_signature='sa{sv}',out_signature='o')
 def CreateSession(self,destination,options):return '/org/bluez/obex/session1'
 @dbus.service.method('org.bluez.obex.Client1',in_signature='o')
 def RemoveSession(self,session):pass
class FileManager(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/org/freedesktop/FileManager1')
 @dbus.service.method('org.freedesktop.FileManager1',in_signature='ass')
 def ShowItems(self,uris,startup):
  if os.environ.get('HICS_FM_TRACE'):
   with open(os.environ['HICS_FM_TRACE'],'w') as target:json.dump([str(uri) for uri in uris],target)
objects=[Input(),Keyboard(),Permissions(),FileManager()];transfer=Transfer();objects.extend([transfer,Session(transfer),Client()])
print('ready',flush=True)
GLib.MainLoop().run()
