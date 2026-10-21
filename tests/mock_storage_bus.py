"""Isolated UDisks fixture. Never connects to the host system bus or disks."""
import json, os
import dbus, dbus.service, dbus.mainloop.glib
from gi.repository import GLib

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.bus.BusConnection(os.environ['DBUS_SYSTEM_BUS_ADDRESS'])
name = dbus.service.BusName('org.freedesktop.UDisks2', bus)
B='org.freedesktop.UDisks2.Block'; F='org.freedesktop.UDisks2.Filesystem'; D='org.freedesktop.UDisks2.Drive'; A=D+'.Ata'
PATH='/org/freedesktop/UDisks2/block_devices/test'; DRIVE='/org/freedesktop/UDisks2/drives/test'
def ay(s):return dbus.ByteArray(s.encode()+b'\0')
class Fixture(dbus.service.Object):
 def __init__(self):
  super().__init__(bus,PATH)
  self.mount="";self.ssd=True
  self.configuration=dbus.Array([], signature='(sa{sv})')
 def mounts(self):return dbus.Array([ay(self.mount)] if self.mount else [],signature='ay')
 @dbus.service.method('org.hics.Test',in_signature='sb',out_signature='')
 def SetMount(self,path,ssd):self.mount=str(path);self.ssd=bool(ssd)
 def block(self):return {'IdUsage':'filesystem','IdType':'ext4','IdUUID':'test-uuid','IdLabel':'Test','PreferredDevice':ay('/dev/test'), 'Size':dbus.UInt64(1000000000),'ReadOnly':False,'Drive':dbus.ObjectPath(DRIVE),'Configuration':self.configuration}
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='s',out_signature='a{sv}')
 def GetAll(self,interface):
  if interface==B:return self.block()
  if interface==F:return {'MountPoints':self.mounts()}
  raise dbus.exceptions.DBusException('Absent interface',name='org.freedesktop.DBus.Error.UnknownInterface')
 @dbus.service.method(B,in_signature='(sa{sv})a{sv}',out_signature='')
 def AddConfigurationItem(self,item,options):self.configuration=dbus.Array([item],signature='(sa{sv})')
 @dbus.service.method(B,in_signature='(sa{sv})(sa{sv})a{sv}',out_signature='')
 def UpdateConfigurationItem(self,old,new,options):
  assert str(old[0])=='fstab';self.configuration=dbus.Array([new],signature='(sa{sv})')
 @dbus.service.method('org.hics.Test',in_signature='s',out_signature='')
 def SetOptions(self,options):
  fields={'fsname':ay('UUID=test-uuid'),'dir':ay('/mnt/test'),'type':ay('ext4'),'opts':ay(str(options)),'freq':dbus.Int32(0),'passno':dbus.Int32(2)}
  self.configuration=dbus.Array([dbus.Struct(('fstab',dbus.Dictionary(fields,signature='sv')),signature='sa{sv}')],signature='(sa{sv})')
 @dbus.service.method('org.hics.Test',in_signature='',out_signature='')
 def Protect(self):
  self.SetOptions('defaults');self.configuration[0][1]['dir']=ay('/')
class Manager(dbus.service.Object):
 def __init__(self,fixture):super().__init__(bus,'/org/freedesktop/UDisks2');self.fixture=fixture
 @dbus.service.method('org.freedesktop.DBus.ObjectManager',in_signature='',out_signature='a{oa{sa{sv}}}')
 def GetManagedObjects(self):
  return {PATH:{B:self.fixture.block(),F:{'MountPoints':self.fixture.mounts()}},DRIVE:{D:{'Model':'Mock SSD','Serial':'Test','RotationRate':dbus.Int32(0 if self.fixture.ssd else 5400)}, A:{'SmartSupported':True,'SmartEnabled':True,'SmartUpdated':dbus.UInt64(1),'SmartFailing':False,'SmartTemperature':dbus.Double(303.15),'SmartPowerOnSeconds':dbus.UInt64(7200),'SmartNumBadSectors':dbus.Int64(0),'SmartNumAttributesFailing':dbus.Int32(0),'SmartSelftestStatus':'success','SmartSelftestPercentRemaining':dbus.Int32(0)}}}
systemdName=dbus.service.BusName('org.freedesktop.systemd1',bus)
class Systemd(dbus.service.Object):
 def __init__(self):super().__init__(bus,'/org/freedesktop/systemd1');self.reloads=0;self.last={}
 @dbus.service.method('org.freedesktop.systemd1.Manager',in_signature='s',out_signature='o')
 def GetUnit(self,name):raise dbus.exceptions.DBusException('No unit',name='org.freedesktop.systemd1.NoSuchUnit')
 @dbus.service.method('org.freedesktop.systemd1.Manager',in_signature='',out_signature='')
 def Reload(self):self.reloads+=1
 @dbus.service.method('org.freedesktop.systemd1.Manager',in_signature='ss',out_signature='o')
 def StopUnit(self,name,mode):raise dbus.exceptions.DBusException('No unit',name='org.freedesktop.systemd1.NoSuchUnit')
 @dbus.service.method('org.freedesktop.systemd1.Manager',in_signature='s',out_signature='')
 def ResetFailedUnit(self,name):pass
 @dbus.service.method('org.freedesktop.systemd1.Manager',in_signature='ssa(sv)a(sa(sv))',out_signature='o')
 def StartTransientUnit(self,name,mode,properties,aux):
  props=dict(properties);execstart=props.get('ExecStart',props.get('ExecStartEx'))[0]
  self.last={'unit':str(name),'program':str(execstart[0]),'arguments':[str(x) for x in execstart[1]],'nice':int(props['Nice']),'noNewPrivileges':bool(props['NoNewPrivileges'])}
  return dbus.ObjectPath('/org/freedesktop/systemd1/job/1')
 @dbus.service.method('org.hics.Test',in_signature='',out_signature='s')
 def LastTask(self):return json.dumps(self.last)
 @dbus.service.method('org.hics.Test',in_signature='',out_signature='u')
 def ReloadCount(self):return self.reloads
systemd=Systemd()
f=Fixture();m=Manager(f)
print('ready',flush=True)
GLib.MainLoop().run()
