#!/usr/bin/env python3
"""Mock for delegation tests; only available on an explicitly private bus."""
import os
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

IFACE='org.freedesktop.impl.portal.Inhibit'
REQUEST='org.freedesktop.impl.portal.Request'
SERVICE='org.freedesktop.impl.portal.desktop.hicsDelegateTest'

class Request(dbus.service.Object):
    def __init__(self, backend, path):
        self.backend=backend;self.path=path
        super().__init__(backend.bus,path)

    @dbus.service.method(REQUEST,in_signature='',out_signature='')
    def Close(self):
        self.backend.requests.pop(self.path,None)
        GLib.idle_add(lambda:(self.remove_from_connection(),False)[1])

class Backend(dbus.service.Object):
    def __init__(self,bus):
        self.bus=bus;self.requests={}
        super().__init__(bus,'/org/freedesktop/portal/desktop')

    @dbus.service.method(IFACE,in_signature='ossua{sv}',out_signature='')
    def Inhibit(self,path,app_id,window,flags,options):
        if int(flags)&2:
            raise dbus.exceptions.DBusException('Fixture rejects switch',name='org.freedesktop.portal.Error.Failed')
        self.requests[str(path)]=(int(flags),Request(self,str(path)))

    @dbus.service.method('org.hics.TestDelegate',in_signature='',out_signature='u')
    def Count(self):return dbus.UInt32(len(self.requests))

    @dbus.service.method('org.hics.TestDelegate',in_signature='o',out_signature='u')
    def Flags(self,path):return dbus.UInt32(self.requests[str(path)][0])

class Screensaver(dbus.service.Object):
    def __init__(self,bus):
        self.cookies=set();self.next_cookie=1
        super().__init__(bus,'/org/freedesktop/ScreenSaver')

    @dbus.service.method('org.freedesktop.ScreenSaver',in_signature='ss',out_signature='u')
    def Inhibit(self,app,reason):
        cookie=self.next_cookie;self.next_cookie+=1;self.cookies.add(cookie)
        return dbus.UInt32(cookie)

    @dbus.service.method('org.freedesktop.ScreenSaver',in_signature='u',out_signature='')
    def UnInhibit(self,cookie):self.cookies.discard(int(cookie))

    @dbus.service.method('org.hics.TestScreensaver',in_signature='',out_signature='u')
    def Count(self):return dbus.UInt32(len(self.cookies))

if __name__=='__main__':
    if not os.environ.get('HICS_TEST_PRIVATE_BUS'):
        raise SystemExit('Private bus required')
    DBusGMainLoop(set_as_default=True)
    bus=dbus.SessionBus()
    name=dbus.service.BusName(SERVICE,bus,do_not_queue=True)
    screensaver_name=dbus.service.BusName('org.freedesktop.ScreenSaver',bus,do_not_queue=True)
    screensaver=Screensaver(bus)
    backend=Backend(bus)
    print('ready',flush=True)
    GLib.MainLoop().run()
