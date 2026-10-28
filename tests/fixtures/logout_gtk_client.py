#!/usr/bin/env python3
"""GTK4 app that inhibits logout when Query End is received (fixture only)."""
import signal
import sys
import gi
gi.require_version('Gtk','4.0')
from gi.repository import Gtk, Gio, GLib

class Fixture(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.hics.LogoutFixture',flags=Gio.ApplicationFlags.NON_UNIQUE,register_session=True)
        self.cookie=0;self.window=None
        self.connect('query-end',self.query)
    def do_activate(self):
        self.window=Gtk.ApplicationWindow(application=self,title='Logout test fixture')
        self.window.set_default_size(320,180);self.window.present()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGUSR1,self.release)
        print('ready',flush=True)
    def query(self,app):
        self.cookie=self.inhibit(self.window,Gtk.ApplicationInhibitFlags.LOGOUT,'Unsaved GTK fixture')
        print('query-cookie',self.cookie,flush=True)
    def release(self):
        if self.cookie:self.uninhibit(self.cookie);self.cookie=0
        return GLib.SOURCE_CONTINUE

if __name__=='__main__':
    raise SystemExit(Fixture().run(sys.argv))
