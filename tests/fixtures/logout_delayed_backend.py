#!/usr/bin/env python3
"""Private-bus backend fixture that delays commit replies to exercise races."""
import os
import sys
from pathlib import Path
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

if not os.environ.get('HICS_TEST_PRIVATE_BUS'):
    raise SystemExit('Private test bus required')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'shell/assets'))
from logout_portal_backend import Broker, BUS_NAME

class DelayedBroker(Broker):
    @dbus.service.method('org.hics.Logout1',in_signature='',out_signature='',
                         sender_keyword='sender',async_callbacks=('reply','error'))
    def Commit(self,reply,error,sender=None):
        self.authorize(sender)
        if not self.ready():
            error(dbus.exceptions.DBusException('Not ready'));return
        self.state=3
        for path in self.monitors:self.publish_state(path)
        GLib.timeout_add(1800,lambda:(reply(),False)[1])

DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus();name=dbus.service.BusName(BUS_NAME,bus,do_not_queue=True)
backend=DelayedBroker(bus)
GLib.MainLoop().run()
