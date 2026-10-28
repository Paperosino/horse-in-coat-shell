#!/usr/bin/env python3
"""Private-bus-only prototype of the XDG logout inhibitor backend.

Not installed or used by the desktop. Non-logout inhibition flags are
deliberately rejected until their contracts are implemented.
"""
import json
import os
from pathlib import Path
import re
import sys
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'shell/assets'))
from logout_inhibitors import InhibitorRegistry, LOGOUT

BUS_NAME='org.freedesktop.impl.portal.desktop.hicsTest'
INHIBIT='org.freedesktop.impl.portal.Inhibit'
REQUEST='org.freedesktop.impl.portal.Request'
SESSION='org.freedesktop.impl.portal.Session'

class Request(dbus.service.Object):
    def __init__(self, broker, path, owner):
        self.broker=broker;self.path=path;self.owner=owner
        super().__init__(broker.bus,path)

    @dbus.service.method(REQUEST,in_signature='',out_signature='',sender_keyword='sender')
    def Close(self,sender=None):
        if sender!=self.owner:
            raise dbus.exceptions.DBusException('Only the owner can close the request',name='org.freedesktop.DBus.Error.AccessDenied')
        self.broker.remove(self.path,self.owner)

class Monitor(dbus.service.Object):
    def __init__(self, broker, path, owner):
        self.broker=broker;self.path=path;self.owner=owner
        super().__init__(broker.bus,path)

    @dbus.service.method(SESSION,in_signature='',out_signature='',sender_keyword='sender')
    def Close(self,sender=None):
        if sender!=self.owner:
            raise dbus.exceptions.DBusException('Only the owner can close the session',name='org.freedesktop.DBus.Error.AccessDenied')
        self.broker.remove_monitor(self.path,self.owner)

class Broker(dbus.service.Object):
    def __init__(self,bus):
        self.bus=bus;self.registry=InhibitorRegistry();self.requests={};self.monitors={}
        self.pending=set();self.stale=set();self.state=1
        super().__init__(bus,'/org/freedesktop/portal/desktop')
        bus.add_signal_receiver(self.owner_changed,signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus',bus_name='org.freedesktop.DBus')

    def remove(self,path,owner):
        if self.registry.close(path,owner):
            request=self.requests.pop(path)
            # Defer unregistering the object until its Close handler returns.
            GLib.idle_add(lambda:(request.remove_from_connection(),False)[1])
            return True
        return False

    def owner_changed(self,name,old,new):
        if name.startswith(':') and old and not new:
            for path,request in list(self.requests.items()):
                if request.owner==name:self.remove(path,name)
            for path,monitor in list(self.monitors.items()):
                if monitor.owner==name:self.remove_monitor(path,name)

    def remove_monitor(self,path,owner):
        monitor=self.monitors.get(path)
        if monitor is None or monitor.owner!=owner:return False
        del self.monitors[path];self.pending.discard(path);self.stale.discard(path)
        GLib.idle_add(lambda:(monitor.remove_from_connection(),False)[1])
        return True

    @dbus.service.signal(INHIBIT,signature='oa{sv}')
    def StateChanged(self,session_handle,state):pass

    def publish_state(self,path):
        self.StateChanged(dbus.ObjectPath(path),{'session-state':dbus.UInt32(self.state,variant_level=1),
                                                'screensaver-active':dbus.Boolean(False,variant_level=1)})

    @dbus.service.method(INHIBIT,in_signature='ossua{sv}',out_signature='',sender_keyword='sender')
    def Inhibit(self,handle,app_id,window,flags,options,sender=None):
        del window
        # Never report success for sleep/idle/switch while they are unsupported.
        if int(flags)!=LOGOUT:
            raise dbus.exceptions.DBusException('Only logout is implemented by this test backend',name='org.freedesktop.portal.Error.Failed')
        if self.state==3:
            raise dbus.exceptions.DBusException('Session is ending',name='org.freedesktop.portal.Error.Failed')
        path=str(handle);owner=str(sender);reason=str(options.get('reason',''))
        try:
            self.registry.add(path,owner,str(app_id),reason,int(flags))
            try:self.requests[path]=Request(self,path,owner)
            except Exception:
                self.registry.close(path,owner)
                raise
        except (ValueError,OverflowError) as error:
            raise dbus.exceptions.DBusException(str(error),name='org.freedesktop.portal.Error.Failed')

    @dbus.service.method(INHIBIT,in_signature='ooss',out_signature='u',sender_keyword='sender')
    def CreateMonitor(self,handle,session_handle,app_id,window,sender=None):
        del handle,app_id,window
        path=str(session_handle)
        if len(path)>512 or not re.fullmatch(r'/org/freedesktop/portal/desktop/session/[A-Za-z0-9_]+/[A-Za-z0-9_]+',path) or path in self.monitors or len(self.monitors)>=256:
            raise dbus.exceptions.DBusException('Invalid or duplicate session',name='org.freedesktop.portal.Error.Failed')
        monitor=Monitor(self,path,str(sender));self.monitors[path]=monitor
        if self.state==2:self.pending.add(path)
        GLib.idle_add(lambda:(self.publish_state(path),False)[1] if self.monitors.get(path) is monitor else False)
        return dbus.UInt32(0)

    @dbus.service.method(INHIBIT,in_signature='o',out_signature='',sender_keyword='sender')
    def QueryEndResponse(self,session_handle,sender=None):
        path=str(session_handle);monitor=self.monitors.get(path)
        if monitor is None or monitor.owner!=sender:
            raise dbus.exceptions.DBusException('Unknown or foreign session',name='org.freedesktop.DBus.Error.AccessDenied')
        if path in self.stale:
            self.stale.remove(path)
            return
        if self.state!=2 or path not in self.pending:
            raise dbus.exceptions.DBusException('No query is pending',name='org.freedesktop.portal.Error.Failed')
        self.pending.remove(path)

    @dbus.service.method('org.hics.TestInhibitors',in_signature='',out_signature='')
    def BeginQuery(self):
        if self.state!=1 or self.stale:raise dbus.exceptions.DBusException('A query is active or an earlier response is outstanding')
        self.state=2;self.pending=set(self.monitors)
        for path in self.monitors:self.publish_state(path)

    @dbus.service.method('org.hics.TestInhibitors',in_signature='',out_signature='b')
    def Ready(self):
        return self.state==2 and not self.pending and not self.stale and not self.registry.matching(LOGOUT)

    @dbus.service.method('org.hics.TestInhibitors',in_signature='',out_signature='')
    def Cancel(self):
        if self.state!=2:raise dbus.exceptions.DBusException('No cancellable query')
        self.state=1;self.stale.update(self.pending);self.pending.clear()
        for path in self.monitors:self.publish_state(path)

    @dbus.service.method('org.hics.TestInhibitors',in_signature='',out_signature='')
    def Commit(self):
        if not self.Ready():raise dbus.exceptions.DBusException('Session is not ready')
        self.state=3
        for path in self.monitors:self.publish_state(path)

    @dbus.service.method('org.hics.TestInhibitors',in_signature='',out_signature='s')
    def List(self):
        return json.dumps([{'path':entry.path,'app_id':entry.app_id,'reason':entry.reason,'flags':entry.flags}
                           for entry in self.registry.matching(LOGOUT)])

    @dbus.service.method('org.hics.TestInhibitors',in_signature='',out_signature='u')
    def MonitorCount(self):
        return dbus.UInt32(len(self.monitors))

if __name__=='__main__':
    # The fixture requires an explicitly provided private bus; it has no
    # activation file and is never installed as a service.
    if not os.environ.get('HICS_TEST_PRIVATE_BUS'):
        raise SystemExit('This prototype is restricted to an explicitly created private test bus')
    DBusGMainLoop(set_as_default=True)
    bus=dbus.SessionBus()
    name=dbus.service.BusName(BUS_NAME,bus,do_not_queue=True)
    broker=Broker(bus)
    print('ready',flush=True)
    GLib.MainLoop().run()
