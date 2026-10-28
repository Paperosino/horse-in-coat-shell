#!/usr/bin/env python3
"""XDG Inhibit backend and logout query service for an hics session.

The control methods require the unique owner of org.hics.LogoutController.
Inhibit requests for non-logout flags are delegated to the GTK backend.
"""
import json
import os
import re
import sys
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from logout_inhibitors import InhibitorRegistry, LOGOUT

BUS_NAME='org.freedesktop.impl.portal.desktop.hics'
INHIBIT='org.freedesktop.impl.portal.Inhibit'
REQUEST='org.freedesktop.impl.portal.Request'
SESSION='org.freedesktop.impl.portal.Session'

class Request(dbus.service.Object):
    def __init__(self, broker, path, owner):
        self.broker=broker;self.path=path;self.owner=owner;self.delegate_name=None
        super().__init__(broker.bus,path)

    @dbus.service.method(REQUEST,in_signature='',out_signature='',sender_keyword='sender')
    def Close(self,sender=None):
        if sender!=self.owner:
            raise dbus.exceptions.DBusException('Only the owner can close the request',name='org.freedesktop.DBus.Error.AccessDenied')
        self.broker.remove(self.path,self.owner)

class Monitor(dbus.service.Object):
    def __init__(self, broker, path, owner, app_id, process_name):
        self.broker=broker;self.path=path;self.owner=owner;self.app_id=app_id;self.process_name=process_name
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
        self.delegate_name='org.freedesktop.impl.portal.desktop.gtk'
        self.locked=True
        super().__init__(bus,'/org/freedesktop/portal/desktop')
        bus.add_signal_receiver(self.owner_changed,signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus',bus_name='org.freedesktop.DBus')

    def remove(self,path,owner):
        if self.registry.close(path,owner):
            request=self.requests.pop(path)
            if request.delegate_name:
                self.bus.call_async(request.delegate_name,path,REQUEST,'Close','',(),
                    lambda:None,lambda error:print('delegate close failed:',error,file=sys.stderr))
            # Defer unregistering the object until its Close handler returns.
            GLib.idle_add(lambda:(request.remove_from_connection(),False)[1])
            return True
        return False

    def owner_changed(self,name,old,new):
        if name=='org.hics.LogoutController' and old and old!=new:
            if self.state in (2,3):
                self.state=1;self.stale.update(self.pending);self.pending.clear()
            self.locked=True
            for path in self.monitors:self.publish_state(path)
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
                                                'screensaver-active':dbus.Boolean(self.locked,variant_level=1)})

    def process_name(self,path,app_id,sender):
        if app_id:return ''
        # The trusted portal frontend encodes its caller's unique bus name in
        # the request path. Resolve only that peer, and expose only its short
        # executable name, never its command-line arguments or private paths.
        match=re.fullmatch(r'/org/freedesktop/portal/desktop/(?:request|session)/(\d+)_(\d+)(?:/[A-Za-z0-9_]+)+',path)
        if not match:return ''
        try:
            if self.bus.get_name_owner('org.freedesktop.portal.Desktop')!=sender:return ''
            peer=':'+match.group(1)+'.'+match.group(2)
            daemon=self.bus.get_object('org.freedesktop.DBus','/org/freedesktop/DBus')
            pid=int(daemon.GetConnectionUnixProcessID(peer,dbus_interface='org.freedesktop.DBus',timeout=1))
            proc='/proc/'+str(pid)
            if os.stat(proc).st_uid!=os.getuid():return ''
            with open(proc+'/comm','rb') as stream:
                name=stream.read(256).decode('utf-8','replace').strip()
            return name if name and len(name)<=255 else ''
        except (OSError,dbus.DBusException,ValueError):
            return ''

    @dbus.service.method(INHIBIT,in_signature='ossua{sv}',out_signature='',sender_keyword='sender',
                         async_callbacks=('reply','error'))
    def Inhibit(self,handle,app_id,window,flags,options,reply,error,sender=None):
        flags=int(flags)
        if not flags or flags & ~15:
            error(dbus.exceptions.DBusException('Invalid inhibition flags',name='org.freedesktop.portal.Error.Failed'));return
        if self.state==3:
            error(dbus.exceptions.DBusException('Session is ending',name='org.freedesktop.portal.Error.Failed'));return
        path=str(handle);owner=str(sender);reason=str(options.get('reason',''))
        other=flags & ~LOGOUT
        if other and not self.delegate_name:
            error(dbus.exceptions.DBusException('No delegate for non-logout flags',name='org.freedesktop.portal.Error.Failed'));return
        try:
            self.registry.add(path,owner,str(app_id),reason,flags,self.process_name(path,app_id,sender))
            try:self.requests[path]=Request(self,path,owner)
            except Exception:
                self.registry.close(path,owner)
                raise
        except (ValueError,OverflowError) as exc:
            error(dbus.exceptions.DBusException(str(exc),name='org.freedesktop.portal.Error.Failed'));return
        if not other:
            reply();return
        request=self.requests[path]
        delegate_name=self.delegate_name
        def delegated():
            if self.requests.get(path) is not request:
                self.bus.call_async(delegate_name,path,REQUEST,'Close','',(),lambda:None,lambda exc:None)
                error(dbus.exceptions.DBusException('Request closed during delegation',name='org.freedesktop.portal.Error.Failed'))
                return
            request.delegate_name=delegate_name;reply()
        def failed(exc):
            self.remove(path,owner);error(exc)
        self.bus.call_async(delegate_name,'/org/freedesktop/portal/desktop',INHIBIT,'Inhibit',
                            'ossua{sv}',(handle,app_id,window,dbus.UInt32(other),options),delegated,failed)

    @dbus.service.method(INHIBIT,in_signature='ooss',out_signature='u',sender_keyword='sender')
    def CreateMonitor(self,handle,session_handle,app_id,window,sender=None):
        del handle,window
        path=str(session_handle)
        if len(path)>512 or not re.fullmatch(r'/org/freedesktop/portal/desktop/session/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)+',path) or path in self.monitors or len(self.monitors)>=256:
            raise dbus.exceptions.DBusException('Invalid or duplicate session',name='org.freedesktop.portal.Error.Failed')
        if len(str(app_id))>512:
            raise dbus.exceptions.DBusException('Invalid application ID',name='org.freedesktop.portal.Error.Failed')
        monitor=Monitor(self,path,str(sender),str(app_id),self.process_name(path,app_id,sender));self.monitors[path]=monitor
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

    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='',sender_keyword='sender')
    def BeginQuery(self,sender=None):
        self.authorize(sender)
        if self.locked or self.state!=1 or self.stale:raise dbus.exceptions.DBusException('Session locked, query active or earlier response outstanding')
        self.state=2;self.pending=set(self.monitors)
        for path in self.monitors:self.publish_state(path)

    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='b',sender_keyword='sender')
    def Ready(self,sender=None):
        self.authorize(sender)
        return self.ready()

    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='',sender_keyword='sender')
    def Cancel(self,sender=None):
        self.authorize(sender)
        if self.state!=2 and not (self.state==3 and self.locked):
            raise dbus.exceptions.DBusException('No cancellable query')
        self.state=1;self.stale.update(self.pending);self.pending.clear()
        for path in self.monitors:self.publish_state(path)

    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='',sender_keyword='sender')
    def Commit(self,sender=None):
        self.authorize(sender)
        if not self.ready():raise dbus.exceptions.DBusException('Session is not ready')
        self.state=3
        for path in self.monitors:self.publish_state(path)

    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='s',sender_keyword='sender')
    def List(self,sender=None):
        self.authorize(sender)
        entries=[{'path':entry.path,'app_id':entry.app_id,'reason':entry.reason,'flags':entry.flags,'pending':False,'process_name':entry.process_name}
                 for entry in self.registry.matching(LOGOUT)]
        entries.extend({'path':path,'app_id':self.monitors[path].app_id,'reason':'','flags':LOGOUT,'pending':True,'process_name':self.monitors[path].process_name}
                       for path in sorted(self.pending | self.stale) if path in self.monitors)
        return json.dumps(entries)

    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='u',sender_keyword='sender')
    def MonitorCount(self,sender=None):
        self.authorize(sender)
        return dbus.UInt32(len(self.monitors))

    def authorize(self,sender):
        try:
            owner=self.bus.get_name_owner('org.hics.LogoutController')
        except dbus.DBusException:
            owner=None
        if not sender or owner!=sender:
            raise dbus.exceptions.DBusException('Only the session controller may control logout',name='org.freedesktop.DBus.Error.AccessDenied')

    def ready(self):
        return self.state==2 and not self.locked and not self.pending and not self.stale and not self.registry.matching(LOGOUT)

    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='',sender_keyword='sender')
    def AbortEnding(self,sender=None):
        self.authorize(sender)
        if self.state!=3:raise dbus.exceptions.DBusException('No committed logout')
        self.state=1
        for path in self.monitors:self.publish_state(path)

    @dbus.service.method('org.hics.Logout1',in_signature='b',out_signature='',sender_keyword='sender')
    def SetLocked(self,locked,sender=None):
        self.authorize(sender)
        if self.locked!=bool(locked):
            self.locked=bool(locked)
            for path in self.monitors:self.publish_state(path)

    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='',sender_keyword='sender')
    def Force(self,sender=None):
        self.authorize(sender)
        if self.state!=2 or self.locked:raise dbus.exceptions.DBusException('No active unlocked logout query')
        self.state=3
        for path in self.monitors:self.publish_state(path)

if __name__=='__main__':
    DBusGMainLoop(set_as_default=True)
    bus=dbus.SessionBus()
    name=dbus.service.BusName(BUS_NAME,bus,do_not_queue=True)
    broker=Broker(bus)
    GLib.MainLoop().run()
