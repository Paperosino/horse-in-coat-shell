"""Exercise the candidate hics portal on a private bus; never activates host services."""
import json
import os
from pathlib import Path
import subprocess
import signal
import tempfile
import time
import unittest
import dbus

ROOT=Path(__file__).resolve().parents[1]
SERVICE='org.freedesktop.impl.portal.desktop.hics'
PATH='/org/freedesktop/portal/desktop'
CONTROL='org.hics.Logout1'
INHIBIT='org.freedesktop.impl.portal.Inhibit'
REQUEST='org.freedesktop.impl.portal.Request'

class CandidatePortal(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='hics-candidate-');self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);config=root/'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(root)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        self.daemon=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(config)],stdout=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,self.daemon);address=self.daemon.stdout.readline().strip();self.assertTrue(address)
        env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=address,HICS_TEST_PRIVATE_BUS='1',HICS_TEST_DELEGATE_AS_GTK='1',HOME=str(root),XDG_RUNTIME_DIR=str(root))
        self.env=env;self.root=root
        self.mock=subprocess.Popen(['python3',str(ROOT/'tests/fixtures/logout_inhibit_delegate.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,self.mock);self.assertEqual(self.mock.stdout.readline().strip(),'ready')
        self.backend=subprocess.Popen(['python3',str(ROOT/'shell/assets/logout_portal_backend.py')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,self.backend)
        self.address=address
        self.controller=dbus.bus.BusConnection(address);self.client=dbus.bus.BusConnection(address)
        self.addCleanup(self.controller.close);self.addCleanup(self.client.close)
        deadline=time.monotonic()+5
        while not self.controller.name_has_owner(SERVICE):
            self.assertIsNone(self.backend.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        self.controller.request_name('org.hics.LogoutController',dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
        self.control=dbus.Interface(self.controller.get_object(SERVICE,PATH),CONTROL)
        self.portal=dbus.Interface(self.client.get_object(SERVICE,PATH),INHIBIT)
        self.path='/org/freedesktop/portal/desktop/request/1_1/probe'

    @staticmethod
    def stop(process):
        if process.poll() is None:process.terminate();process.wait(timeout=5)
        for stream in (process.stdout,process.stderr):
            if stream:stream.close()

    def test_only_controller_can_mutate_and_lock_gates_commit(self):
        other=dbus.Interface(self.client.get_object(SERVICE,PATH),CONTROL)
        with self.assertRaises(dbus.DBusException):other.SetLocked(False)
        with self.assertRaises(dbus.DBusException):self.control.BeginQuery()
        self.control.SetLocked(False);self.control.BeginQuery();self.assertTrue(self.control.Ready())
        self.control.SetLocked(True);self.assertFalse(self.control.Ready())
        with self.assertRaises(dbus.DBusException):self.control.Commit()
        with self.assertRaises(dbus.DBusException):self.control.Force()
        self.control.SetLocked(False);self.control.Commit()

    def test_frontend_request_without_app_id_uses_client_process_name(self):
        data=self.root/'data';config=self.root/'config'
        portals=data/'xdg-desktop-portal/portals';portals.mkdir(parents=True)
        (portals/'hics.portal').write_text('[portal]\nDBusName='+SERVICE+'\nInterfaces='+INHIBIT+';\nUseIn=HICS\n')
        preferences=config/'xdg-desktop-portal';preferences.mkdir(parents=True)
        (preferences/'portals.conf').write_text('[preferred]\ndefault=hics\n')
        env=dict(self.env,XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(config),XDG_CACHE_HOME=str(self.root/'cache'),
                 XDG_DATA_DIRS='/usr/share',XDG_CURRENT_DESKTOP='HICS',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(self.root/'absent'))
        frontend=subprocess.Popen(['/usr/lib/xdg-desktop-portal'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,frontend)
        deadline=time.monotonic()+8
        while not self.controller.name_has_owner('org.freedesktop.portal.Desktop'):
            self.assertIsNone(frontend.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        client=subprocess.Popen(['python3',str(ROOT/'tests/fixtures/logout_inhibit_client.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,client)
        self.assertEqual(client.stdout.readline().strip(),'ready')
        while True:
            entries=json.loads(self.control.List())
            match=next((entry for entry in entries if entry['reason']=='Unsaved background work'),None)
            if match:break
            self.assertIsNone(client.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        self.assertIn('python',match['process_name'].lower())
        self.assertNotIn('/',match['process_name'])

    @unittest.skipUnless(os.environ.get('HICS_TEST_GTK_DISPLAY'),'Requires an isolated nested Wayland display')
    def test_real_frontend_and_gtk_query_end(self):
        data=self.root/'data';config=self.root/'config'
        portals=data/'xdg-desktop-portal/portals';portals.mkdir(parents=True)
        (portals/'hics.portal').write_text('[portal]\nDBusName='+SERVICE+'\nInterfaces='+INHIBIT+';\nUseIn=HICS\n')
        preferences=config/'xdg-desktop-portal';preferences.mkdir(parents=True)
        (preferences/'portals.conf').write_text('[preferred]\ndefault=hics\n')
        env=dict(self.env,XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(config),XDG_CACHE_HOME=str(self.root/'cache'),
                 XDG_DATA_DIRS='/usr/share',XDG_CURRENT_DESKTOP='HICS',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(self.root/'absent'),
                 WAYLAND_DISPLAY=os.environ['HICS_TEST_GTK_DISPLAY'],GDK_DEBUG='portals',GDK_BACKEND='wayland',
                 GSETTINGS_BACKEND='memory',GTK_A11Y='none')
        frontend=subprocess.Popen(['/usr/lib/xdg-desktop-portal'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,frontend)
        deadline=time.monotonic()+8
        while not self.controller.name_has_owner('org.freedesktop.portal.Desktop'):
            self.assertIsNone(frontend.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        client=subprocess.Popen(['python3',str(ROOT/'tests/fixtures/logout_gtk_client.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(self.stop,client)
        self.assertEqual(client.stdout.readline().strip(),'ready')
        deadline=time.monotonic()+8
        while not int(self.control.MonitorCount()):
            self.assertIsNone(client.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        self.control.SetLocked(False);self.control.BeginQuery()
        deadline=time.monotonic()+8
        while not any(x['reason']=='Unsaved GTK fixture' for x in json.loads(self.control.List())):
            self.assertIsNone(client.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        self.assertFalse(self.control.Ready())
        os.kill(client.pid,signal.SIGUSR1)
        deadline=time.monotonic()+8
        while not self.control.Ready():
            self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        self.control.Cancel()

    def test_controller_disconnect_relocks_and_requires_late_response(self):
        monitor='/org/freedesktop/portal/desktop/session/1_1/probe'
        self.portal.CreateMonitor(dbus.ObjectPath(self.path),dbus.ObjectPath(monitor),'org.example.Editor','')
        self.control.SetLocked(False);self.control.BeginQuery()
        self.controller.close()
        replacement=dbus.bus.BusConnection(self.address);self.addCleanup(replacement.close)
        deadline=time.monotonic()+4
        while True:
            result=replacement.request_name('org.hics.LogoutController',dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
            if result==dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:break
            self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        control=dbus.Interface(replacement.get_object(SERVICE,PATH),CONTROL)
        with self.assertRaises(dbus.DBusException):control.BeginQuery()
        control.SetLocked(False)
        with self.assertRaises(dbus.DBusException):control.BeginQuery()
        self.portal.QueryEndResponse(dbus.ObjectPath(monitor))
        control.BeginQuery();self.assertFalse(control.Ready())
        self.portal.QueryEndResponse(dbus.ObjectPath(monitor));self.assertTrue(control.Ready())
        control.Cancel()

    def test_pending_monitor_is_visible_and_cannot_be_skipped(self):
        monitor='/org/freedesktop/portal/desktop/session/1_1/probe'
        self.portal.CreateMonitor(dbus.ObjectPath(self.path),dbus.ObjectPath(monitor),'org.example.Editor','')
        self.control.SetLocked(False);self.control.BeginQuery()
        self.assertFalse(self.control.Ready())
        self.assertEqual(json.loads(self.control.List())[0]['app_id'],'org.example.Editor')
        self.assertTrue(json.loads(self.control.List())[0]['pending'])
        self.portal.QueryEndResponse(dbus.ObjectPath(monitor))
        self.assertTrue(self.control.Ready());self.assertEqual(json.loads(self.control.List()),[])
        self.control.Commit()

    def test_failed_logind_can_abort_committed_end(self):
        self.control.SetLocked(False);self.control.BeginQuery();self.control.Commit()
        self.control.AbortEnding()
        self.control.BeginQuery();self.assertTrue(self.control.Ready());self.control.Cancel()

    def test_controller_loss_after_commit_restores_running_state(self):
        self.control.SetLocked(False);self.control.BeginQuery();self.control.Commit()
        self.controller.close()
        replacement=dbus.bus.BusConnection(self.address);self.addCleanup(replacement.close)
        deadline=time.monotonic()+4
        while replacement.request_name('org.hics.LogoutController',dbus.bus.NAME_FLAG_DO_NOT_QUEUE)!=dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:
            self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        control=dbus.Interface(replacement.get_object(SERVICE,PATH),CONTROL)
        control.SetLocked(False);control.BeginQuery();self.assertTrue(control.Ready());control.Cancel()

    def test_mixed_inhibitor_and_delegate_are_released(self):
        delegate=dbus.Interface(self.client.get_object('org.freedesktop.impl.portal.desktop.gtk',PATH),'org.hics.TestDelegate')
        self.portal.Inhibit(dbus.ObjectPath(self.path),'org.example.Editor','',dbus.UInt32(9),{'reason':'Unsaved'})
        self.assertEqual(int(delegate.Flags(dbus.ObjectPath(self.path))),8)
        self.control.SetLocked(False);self.control.BeginQuery();self.assertFalse(self.control.Ready())
        self.assertEqual(json.loads(self.control.List())[0]['reason'],'Unsaved')
        dbus.Interface(self.client.get_object(SERVICE,self.path),REQUEST).Close()
        deadline=time.monotonic()+4
        while int(delegate.Count()) or not self.control.Ready():
            self.assertLess(time.monotonic(),deadline);time.sleep(.02)
        self.control.Commit()

if __name__=='__main__':unittest.main()
