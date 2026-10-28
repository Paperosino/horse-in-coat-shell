"""Exercise the packaged portal descriptors on a private activatable bus."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import dbus

ROOT=Path(__file__).resolve().parents[1]
SERVICE='org.freedesktop.impl.portal.desktop.hics'
PATH='/org/freedesktop/portal/desktop'

class Activation(unittest.TestCase):
    def test_portal_selection_activates_hics_backend(self):
        with tempfile.TemporaryDirectory(prefix='hics-activation-') as directory:
            root=Path(directory);services=root/'services';services.mkdir()
            descriptor=(ROOT/'distribution/portal/org.freedesktop.impl.portal.desktop.hics.service.in').read_text().replace('@HICS_BIN_DIR@',str(ROOT/'distribution/bin'))
            (services/(SERVICE+'.service')).write_text(descriptor)
            data=root/'data';portals=data/'xdg-desktop-portal/portals';portals.mkdir(parents=True)
            (portals/'hics.portal').write_text((ROOT/'distribution/portal/hics.portal').read_text())
            prefs=root/'config/xdg-desktop-portal';prefs.mkdir(parents=True)
            (prefs/'hics-portals.conf').write_text((ROOT/'distribution/portal/hics-portals.conf').read_text())
            config=root/'bus.conf'
            config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(root)+'</listen><servicedir>'+str(services)+'</servicedir><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
            env=dict(os.environ,HOME=str(root),XDG_RUNTIME_DIR=str(root),HICS_DATA_DIR=str(ROOT),
                     XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(root/'config'),XDG_CACHE_HOME=str(root/'cache'),
                     XDG_DATA_DIRS='/usr/share',XDG_CURRENT_DESKTOP='HICS',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'absent'))
            bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(config)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            frontend=None
            try:
                address=bus.stdout.readline().strip();self.assertTrue(address)
                env['DBUS_SESSION_BUS_ADDRESS']=address
                client=dbus.bus.BusConnection(address)
                self.assertFalse(client.name_has_owner(SERVICE))
                frontend=subprocess.Popen(['/usr/lib/xdg-desktop-portal'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
                deadline=time.monotonic()+8
                while not client.name_has_owner('org.freedesktop.portal.Desktop'):
                    self.assertIsNone(frontend.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.02)
                portal=dbus.Interface(client.get_object('org.freedesktop.portal.Desktop',PATH),'org.freedesktop.portal.Inhibit')
                request=portal.Inhibit('',dbus.UInt32(1),{'reason':dbus.String('Activation test',variant_level=1)})
                while not client.name_has_owner(SERVICE):
                    self.assertIsNone(frontend.poll());self.assertLess(time.monotonic(),deadline);time.sleep(.02)
                client.request_name('org.hics.LogoutController',dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
                control=dbus.Interface(client.get_object(SERVICE,PATH),'org.hics.Logout1')
                while 'Activation test' not in str(control.List()):
                    self.assertLess(time.monotonic(),deadline);time.sleep(.02)
                dbus.Interface(client.get_object('org.freedesktop.portal.Desktop',request),'org.freedesktop.portal.Request').Close()
                client.close()
            finally:
                if frontend and frontend.poll() is None:frontend.terminate();frontend.wait(timeout=5)
                bus.terminate();bus.wait(timeout=5)
                if frontend and frontend.stderr:frontend.stderr.close()
                bus.stdout.close();bus.stderr.close()

if __name__=='__main__':unittest.main()
