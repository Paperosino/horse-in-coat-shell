"""Private NetworkManager/UDisks bus. All devices are fictitious."""
import json
import os
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.bus.BusConnection(os.environ['DBUS_SYSTEM_BUS_ADDRESS'])
NM = 'org.freedesktop.NetworkManager'
NP = '/org/freedesktop/NetworkManager'
UD = 'org.freedesktop.UDisks2'
DP = '/org/freedesktop/UDisks2/block_devices/luks'
DRIVE = '/org/freedesktop/UDisks2/drives/usb'
names = [dbus.service.BusName(NM, bus), dbus.service.BusName(UD, bus)]

def log(method, data):
    with open(os.environ['DESKTOP_BUS_LOG'], 'a') as file:
        file.write(json.dumps({'method': method, 'data': data}) + '\n')

class Network(dbus.service.Object):
    @dbus.service.method(NM, in_signature='', out_signature='ao')
    def GetDevices(self):
        return [dbus.ObjectPath(NP + '/Devices/1')]

    @dbus.service.method(NM, in_signature='a{sa{sv}}ooa{sv}', out_signature='ooa{sv}')
    def AddAndActivateConnection2(self, settings, device, specific, options):
        log('hotspot' if str(options['persist']) == 'volatile' else 'hidden', {'ssid': bytes(settings['802-11-wireless']['ssid']).decode(),
            'password': str(settings['802-11-wireless-security']['psk']),
            'persist': str(options['persist']), 'method': str(settings['ipv4']['method']), **({'hidden': bool(settings['802-11-wireless']['hidden'])} if 'hidden' in settings['802-11-wireless'] else {})})
        active.state = 4 if bytes(settings['802-11-wireless']['ssid']).decode() == 'Fail test' else 2
        return (dbus.ObjectPath(NP + '/Settings/1'), dbus.ObjectPath(NP + '/ActiveConnection/1'), {})

    @dbus.service.method(NM, in_signature='o', out_signature='')
    def DeactivateConnection(self, path):
        log('stop-hotspot', str(path))

class Wifi(dbus.service.Object):
    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface == NM + '.Device':
            return {'DeviceType': dbus.UInt32(2), 'Interface': 'wlan-test', 'ActiveConnection': dbus.ObjectPath(NP + '/ActiveConnection/1')}
        return {'Mode': dbus.UInt32(3), 'WirelessCapabilities': dbus.UInt32(0x40)}

class Active(dbus.service.Object):
    state = 2
    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        return {'State': dbus.UInt32(self.state)}

class Disks(dbus.service.Object):
    @dbus.service.method('org.freedesktop.DBus.ObjectManager', in_signature='', out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        return {DP: {UD + '.Block': {'IdLabel': 'Encrypted test', 'PreferredDevice': dbus.ByteArray(b'/dev/fake\0')},
            UD + '.Encrypted': {'CleartextDevice': dbus.ObjectPath('/')}},
            DRIVE: {UD + '.Drive': {'Model': 'USB test', 'Removable': True, 'CanPowerOff': True, 'Ejectable': False}}}

class Encrypted(dbus.service.Object):
    @dbus.service.method(UD + '.Encrypted', in_signature='sa{sv}', out_signature='o')
    def Unlock(self, password, options):
        if password != 'correct passphrase':
            raise dbus.exceptions.DBusException('Incorrect passphrase', name=UD + '.Error.Failed')
        log('unlock', str(password))
        return dbus.ObjectPath('/org/freedesktop/UDisks2/block_devices/cleartext')

    @dbus.service.method(UD + '.Encrypted', in_signature='a{sv}', out_signature='')
    def Lock(self, options):
        raise dbus.exceptions.DBusException('Filesystem is busy', name=UD + '.Error.DeviceBusy')

class Drive(dbus.service.Object):
    @dbus.service.method(UD + '.Drive', in_signature='a{sv}', out_signature='')
    def PowerOff(self, options):
        log('power-off', True)

active = Active(bus, NP + '/ActiveConnection/1')
objects = [active, Network(bus, NP), Wifi(bus, NP + '/Devices/1'), Disks(bus, '/org/freedesktop/UDisks2'),
    Encrypted(bus, DP), Drive(bus, DRIVE)]
print('ready', flush=True)
GLib.MainLoop().run()
