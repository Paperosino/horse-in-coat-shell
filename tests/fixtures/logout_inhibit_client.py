#!/usr/bin/env python3
"""Hold a logout inhibition on the explicitly private portal fixture."""
import signal
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus()
portal=dbus.Interface(bus.get_object('org.freedesktop.portal.Desktop','/org/freedesktop/portal/desktop'),
                      'org.freedesktop.portal.Inhibit')
handle=portal.Inhibit('',dbus.UInt32(1),{'reason':dbus.String('Unsaved background work',variant_level=1)})
request=dbus.Interface(bus.get_object('org.freedesktop.portal.Desktop',handle),'org.freedesktop.portal.Request')
def release():
    request.Close();print('released',flush=True)
    return GLib.SOURCE_REMOVE
GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGUSR1,release)
print('ready',flush=True)
GLib.MainLoop().run()
