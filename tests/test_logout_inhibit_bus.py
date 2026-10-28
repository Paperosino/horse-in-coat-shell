"""Exercise the logout inhibitor prototype on an isolated real D-Bus broker."""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)

ROOT=Path(__file__).resolve().parents[1]
SERVICE='org.freedesktop.impl.portal.desktop.hicsTest'
PATH='/org/freedesktop/portal/desktop'
IFACE='org.freedesktop.impl.portal.Inhibit'
REQ='org.freedesktop.impl.portal.Request'

class PrototypeBus(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='hics-inhibit-bus-')
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);config=root/'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(root)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        self.bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(config)],stdout=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,self.bus)
        self.address=self.bus.stdout.readline().strip();self.assertTrue(self.address)
        env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=self.address,HICS_TEST_PRIVATE_BUS='1',HOME=str(root),XDG_RUNTIME_DIR=str(root))
        self.env=env
        self.backend=subprocess.Popen(['python3',str(ROOT/'tests/fixtures/logout_inhibit_backend.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,self.backend)
        self.assertEqual(self.backend.stdout.readline().strip(),'ready')
        self.owner=dbus.bus.BusConnection(self.address)
        self.observer=dbus.bus.BusConnection(self.address)
        self.addCleanup(self.owner.close);self.addCleanup(self.observer.close)
        self.path='/org/freedesktop/portal/desktop/request/1_123/example'

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate();process.wait(timeout=5)
        for stream in (process.stdout,process.stderr):
            if stream:stream.close()

    def portal(self,bus):return dbus.Interface(bus.get_object(SERVICE,PATH),IFACE)
    def entries(self):
        iface=dbus.Interface(self.observer.get_object(SERVICE,PATH),'org.hics.TestInhibitors')
        return json.loads(iface.List())

    def test_logout_inhibition_lifetime_and_owner(self):
        self.portal(self.owner).Inhibit(dbus.ObjectPath(self.path),'org.example.Editor','',dbus.UInt32(1),{'reason':dbus.String('Unsaved work',variant_level=1)})
        self.assertEqual(self.entries()[0]['reason'],'Unsaved work')
        foreign=dbus.Interface(self.observer.get_object(SERVICE,self.path),REQ)
        with self.assertRaises(dbus.DBusException):foreign.Close()
        self.assertEqual(len(self.entries()),1)
        dbus.Interface(self.owner.get_object(SERVICE,self.path),REQ).Close()
        self.assertEqual(self.entries(),[])

    def test_owner_loss_releases_only_its_inhibitor(self):
        self.portal(self.owner).Inhibit(dbus.ObjectPath(self.path),'org.example.Backup','',dbus.UInt32(1),{})
        self.owner.close()
        deadline=time.monotonic()+3
        while self.entries():
            self.assertLess(time.monotonic(),deadline,'inhibitor survived owner disconnect')
            time.sleep(.02)

    def test_unsupported_flags_fail_without_registering(self):
        with self.assertRaises(dbus.DBusException):
            self.portal(self.owner).Inhibit(dbus.ObjectPath(self.path),'org.example.Editor','',dbus.UInt32(9),{})
        self.assertEqual(self.entries(),[])

    def test_query_waits_for_monitors_and_new_inhibitors(self):
        monitor='/org/freedesktop/portal/desktop/session/1_123/test'
        events=[]
        self.owner.add_signal_receiver(lambda path,state:events.append((str(path),int(state['session-state']))),
            signal_name='StateChanged',dbus_interface=IFACE,bus_name=SERVICE,path=PATH)
        portal=self.portal(self.owner)
        self.assertEqual(int(portal.CreateMonitor(dbus.ObjectPath(self.path),dbus.ObjectPath(monitor),'org.example.Editor','')),0)
        control=dbus.Interface(self.observer.get_object(SERVICE,PATH),'org.hics.TestInhibitors')
        control.BeginQuery();self.assertFalse(control.Ready())
        with self.assertRaises(dbus.DBusException):self.portal(self.observer).QueryEndResponse(dbus.ObjectPath(monitor))
        portal.QueryEndResponse(dbus.ObjectPath(monitor));self.assertTrue(control.Ready())
        portal.Inhibit(dbus.ObjectPath(self.path),'org.example.Editor','',dbus.UInt32(1),{})
        self.assertFalse(control.Ready())
        with self.assertRaises(dbus.DBusException):control.Commit()
        dbus.Interface(self.owner.get_object(SERVICE,self.path),REQ).Close()
        self.assertTrue(control.Ready());control.Commit()
        deadline=time.monotonic()+3;context=GLib.MainContext.default()
        while (monitor,3) not in events:
            while context.pending():context.iteration(False)
            self.assertLess(time.monotonic(),deadline,'Session state signal missing')
            time.sleep(.01)
        self.assertIn((monitor,2),events)

    def test_cancelled_query_must_drain_late_response_before_retry(self):
        monitor='/org/freedesktop/portal/desktop/session/1_123/test'
        portal=self.portal(self.owner)
        portal.CreateMonitor(dbus.ObjectPath(self.path),dbus.ObjectPath(monitor),'org.example.Editor','')
        control=dbus.Interface(self.observer.get_object(SERVICE,PATH),'org.hics.TestInhibitors')
        control.BeginQuery();control.Cancel()
        with self.assertRaises(dbus.DBusException):control.BeginQuery()
        portal.QueryEndResponse(dbus.ObjectPath(monitor))
        control.BeginQuery();self.assertFalse(control.Ready())
        portal.QueryEndResponse(dbus.ObjectPath(monitor));self.assertTrue(control.Ready())

    def test_pending_monitor_never_expires_and_owner_loss_unblocks(self):
        monitor='/org/freedesktop/portal/desktop/session/1_123/stalled'
        self.portal(self.owner).CreateMonitor(dbus.ObjectPath(self.path),dbus.ObjectPath(monitor),'org.example.Slow','')
        control=dbus.Interface(self.observer.get_object(SERVICE,PATH),'org.hics.TestInhibitors')
        control.BeginQuery()
        # The GTK implementation uses a one-second timeout. A timeout must
        # never turn a still-outstanding query into a successful logout.
        time.sleep(1.2)
        self.assertFalse(control.Ready())
        with self.assertRaises(dbus.DBusException):control.Commit()
        self.owner.close()
        deadline=time.monotonic()+3
        while not control.Ready():
            self.assertLess(time.monotonic(),deadline,'Dead monitor remained pending')
            time.sleep(.02)
        control.Commit()

    def test_monitor_created_during_query_must_respond(self):
        monitor='/org/freedesktop/portal/desktop/session/1_123/late'
        control=dbus.Interface(self.observer.get_object(SERVICE,PATH),'org.hics.TestInhibitors')
        control.BeginQuery();self.assertTrue(control.Ready())
        portal=self.portal(self.owner)
        portal.CreateMonitor(dbus.ObjectPath(self.path),dbus.ObjectPath(monitor),'org.example.Late','')
        self.assertFalse(control.Ready())
        with self.assertRaises(dbus.DBusException):control.Commit()
        portal.QueryEndResponse(dbus.ObjectPath(monitor))
        self.assertTrue(control.Ready());control.Commit()

    def start_frontend(self):
        root=Path(self.tmp.name);data=root/'data';config=root/'config'
        portals=data/'xdg-desktop-portal/portals';portals.mkdir(parents=True)
        (portals/'hicsTest.portal').write_text('[portal]\nDBusName='+SERVICE+'\nInterfaces='+IFACE+';\nUseIn=HICS\n')
        prefs=config/'xdg-desktop-portal';prefs.mkdir(parents=True)
        (prefs/'portals.conf').write_text('[preferred]\ndefault=hicsTest\n')
        env=dict(self.env,XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(config),XDG_CACHE_HOME=str(root/'cache'),
                 XDG_DATA_DIRS='/usr/share',XDG_CURRENT_DESKTOP='HICS',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'absent'))
        frontend=subprocess.Popen(['/usr/lib/xdg-desktop-portal','--verbose'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,frontend)
        deadline=time.monotonic()+8
        while True:
            try:
                self.observer.get_object('org.freedesktop.portal.Desktop','/org/freedesktop/portal/desktop').Introspect(dbus_interface='org.freedesktop.DBus.Introspectable',timeout=1)
                break
            except dbus.DBusException:
                self.assertIsNone(frontend.poll(),'Portal frontend exited')
                self.assertLess(time.monotonic(),deadline,'Portal frontend did not become ready')
                time.sleep(.05)
        return env

    def test_real_frontend_forwards_and_releases_logout_inhibit(self):
        self.start_frontend()
        frontend_iface=dbus.Interface(self.owner.get_object('org.freedesktop.portal.Desktop',PATH),'org.freedesktop.portal.Inhibit')
        handle=frontend_iface.Inhibit('',dbus.UInt32(1),{'reason':dbus.String('Background backup',variant_level=1)})
        deadline=time.monotonic()+5
        while not self.entries():
            self.assertLess(time.monotonic(),deadline,'Frontend did not forward the inhibitor')
            time.sleep(.02)
        self.assertEqual(self.entries()[0]['reason'],'Background backup')
        request=dbus.Interface(self.owner.get_object('org.freedesktop.portal.Desktop',handle),'org.freedesktop.portal.Request')
        request.Close()
        while self.entries():
            self.assertLess(time.monotonic(),deadline,'Backend inhibitor survived frontend Close')
            time.sleep(.02)
        # The frontend owns backend requests on behalf of clients. Losing a
        # client must still cause the frontend to close its delegated request.
        client=dbus.bus.BusConnection(self.address)
        try:
            iface=dbus.Interface(client.get_object('org.freedesktop.portal.Desktop',PATH),'org.freedesktop.portal.Inhibit')
            iface.Inhibit('',dbus.UInt32(1),{'reason':dbus.String('Client disconnect',variant_level=1)})
            deadline=time.monotonic()+5
            while not self.entries():
                self.assertLess(time.monotonic(),deadline,'Second inhibition not forwarded')
                time.sleep(.02)
        finally:
            client.close()
        while self.entries():
            self.assertLess(time.monotonic(),deadline,'Frontend retained a disconnected client inhibitor')
            time.sleep(.02)
        responses=[];states=[]
        self.owner.add_signal_receiver(lambda response,results:responses.append((int(response),results)),
            signal_name='Response',dbus_interface='org.freedesktop.portal.Request',bus_name='org.freedesktop.portal.Desktop')
        self.owner.add_signal_receiver(lambda session,state:states.append((str(session),int(state.get('session-state',0)))),
            signal_name='StateChanged',dbus_interface='org.freedesktop.portal.Inhibit',bus_name='org.freedesktop.portal.Desktop')
        frontend_iface.CreateMonitor('',{'handle_token':dbus.String('monrequest',variant_level=1),
            'session_handle_token':dbus.String('monsession',variant_level=1)})
        deadline=time.monotonic()+5;context=GLib.MainContext.default()
        while not responses:
            while context.pending():context.iteration(False)
            self.assertLess(time.monotonic(),deadline,'Monitor response not forwarded')
            time.sleep(.01)
        self.assertEqual(responses[-1][0],0)
        session=responses[-1][1]['session_handle']
        control=dbus.Interface(self.observer.get_object(SERVICE,PATH),'org.hics.TestInhibitors')
        control.BeginQuery();self.assertFalse(control.Ready())
        while (str(session),2) not in states:
            while context.pending():context.iteration(False)
            self.assertLess(time.monotonic(),deadline,'Query End not forwarded to the client')
            time.sleep(.01)
        frontend_iface.QueryEndResponse(session)
        while not control.Ready():
            self.assertLess(time.monotonic(),deadline,'Monitor response not forwarded')
            time.sleep(.01)
        control.Cancel()
        dbus.Interface(self.owner.get_object('org.freedesktop.portal.Desktop',session),'org.freedesktop.portal.Session').Close()

    @unittest.skipUnless(os.environ.get('HICS_TEST_GTK_DISPLAY'),'Requires the explicit nested Wayland GTK fixture')
    def test_real_gtk_query_end_inhibits_logout(self):
        env=self.start_frontend()
        env.update(WAYLAND_DISPLAY=os.environ['HICS_TEST_GTK_DISPLAY'],GDK_DEBUG='portals',GDK_BACKEND='wayland',GSETTINGS_BACKEND='memory',GTK_A11Y='none')
        client=subprocess.Popen(['python3',str(ROOT/'tests/fixtures/logout_gtk_client.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,client)
        self.assertEqual(client.stdout.readline().strip(),'ready')
        control=dbus.Interface(self.observer.get_object(SERVICE,PATH),'org.hics.TestInhibitors')
        deadline=time.monotonic()+8
        while not control.MonitorCount():
            self.assertIsNone(client.poll(),'GTK fixture exited')
            if time.monotonic()>=deadline:
                client.terminate();_,stderr=client.communicate(timeout=5)
                self.fail('GTK did not register a session monitor: '+stderr)
            time.sleep(.02)
        control.BeginQuery()
        while not self.entries():
            self.assertIsNone(client.poll(),'GTK fixture exited during query')
            self.assertLess(time.monotonic(),deadline,'GTK did not inhibit logout')
            time.sleep(.02)
        self.assertEqual(self.entries()[0]['reason'],'Unsaved GTK fixture')
        self.assertFalse(control.Ready())
        client.send_signal(signal.SIGUSR1)
        while self.entries() or not control.Ready():
            self.assertLess(time.monotonic(),deadline,'GTK inhibitor or query response was retained')
            time.sleep(.02)
        control.Cancel()

if __name__=='__main__':unittest.main()
