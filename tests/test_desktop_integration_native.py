"""Run new C++ session services against fake tools and a private system bus."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / 'shell/plugin/src/Hyprstack/Services'

class DesktopIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='hics-desktop-test-')
        cls.base = Path(cls.temp.name)
        cls.binary = cls.base / 'probe'
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
            'Qt6Core', 'Qt6Qml', 'Qt6DBus', 'Qt6Multimedia'], text=True))
        sources = [ROOT / 'tests/fixtures/desktop-integration-probe.cpp']
        for name in ('desktopintegration', 'notificationpolicy', 'wallpaperplayer'):
            moc = cls.base / (name + '-moc.cpp')
            subprocess.run([str(Path(subprocess.check_output(['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip()) / 'moc'), str(SERVICES / (name + '.hpp')), '-o', str(moc), *shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'Qt6Qml', 'Qt6Multimedia'], text=True))], check=True)
            sources.extend([SERVICES / (name + '.cpp'), moc])
        subprocess.run(['c++', '-std=c++20', '-fPIC', *map(str, sources), '-I', str(SERVICES),
            *flags, '-o', str(cls.binary)], check=True)
        cls.bus = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'], stdout=subprocess.PIPE, text=True)
        cls.env = dict(os.environ, DBUS_SYSTEM_BUS_ADDRESS=cls.bus.stdout.readline().strip(),
            DESKTOP_BUS_LOG=str(cls.base / 'bus.log'), XDG_CONFIG_HOME=str(cls.base / 'config'))
        cls.mock = subprocess.Popen(['python3', str(ROOT / 'tests/mock_desktop_bus.py')], env=cls.env, stdout=subprocess.PIPE, text=True)
        if cls.mock.stdout.readline().strip() != 'ready':
            raise RuntimeError('Private desktop D-Bus fixture failed to start')
        tools = cls.base / 'tools'
        tools.mkdir()
        tool = '''#!/usr/bin/python3
import json, os, sys
name=os.path.basename(sys.argv[0])
if name=='pactl':
 if 'set-card-profile' in sys.argv:
  open(os.environ['PROFILE_LOG'],'w').write(json.dumps(sys.argv[1:]));sys.exit(0)
 print(json.dumps([{'name':'card-test','active_profile':'stereo','properties':{'device.description':'Test card'},'profiles':{'stereo':{'description':'Stereo','available':'yes'},'missing':{'available':'no'}}}]))
elif name=='pw-dump':
 print(json.dumps([{'id':1,'info':{'state':'running','props':{'media.class':'Stream/Input/Video','application.name':'Browser','media.role':'Screen'}}},{'id':2,'info':{'state':'running','props':{'media.class':'Stream/Input/Video','application.name':'Camera'}}},{'id':3,'info':{'props':{'media.class':'Audio/Sink'}}}]))
elif name=='hyprctl':
 if 'monitors' in sys.argv: print(json.dumps([{'name':'DP-test','x':0,'y':0,'width':3840,'height':2160,'scale':2,'transform':0}]))
 else: print(json.dumps([{'title':'Window','mapped':True,'hidden':False,'at':[10,20],'size':[600,400]}]))
'''
        for name in ('pactl', 'pw-dump', 'hyprctl'):
            path = tools / name
            path.write_text(tool)
            path.chmod(0o700)
        cls.env.update(PATH=str(tools) + ':' + os.environ['PATH'], PROFILE_LOG=str(cls.base / 'profile.json'))

    @classmethod
    def tearDownClass(cls):
        for process in (cls.mock, cls.bus):
            process.terminate()
            process.wait(timeout=5)
            process.stdout.close()
        cls.temp.cleanup()

    def probe(self, operation, environment=None, **options):
        run = subprocess.run([str(self.binary)], input=json.dumps(dict(operation=operation, **options)),
            env=environment or self.env, capture_output=True, text=True, check=True, timeout=10)
        return json.loads(run.stdout)

    def test_normal_portal_reply_preserves_screen_and_window_capabilities(self):
        env=dict(self.env,DBUS_SESSION_BUS_ADDRESS=self.env['DBUS_SYSTEM_BUS_ADDRESS'])
        data=self.probe('refresh',environment=env)
        self.assertFalse(data['busy'],data)
        self.assertEqual(data['portalSourceTypes'],3)

    def test_disconnected_session_bus_does_not_strand_busy_state(self):
        data=self.probe('refresh',environment=dict(self.env,DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent/hics-session-test'))
        self.assertFalse(data['busy'],data)
        self.assertEqual(data['pendingCalls'],0)

    def test_both_buses_disconnected_complete_without_stale_devices(self):
        env=dict(self.env,DBUS_SYSTEM_BUS_ADDRESS='unix:path=/nonexistent/hics-system-test',DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent/hics-session-test')
        data=self.probe('refresh',environment=env)
        self.assertFalse(data['busy'],data)
        self.assertEqual(data['wifi'],[])
        self.assertEqual(data['drives'],[])
        self.assertEqual(data['pendingCalls'],0)

    def test_status_keeps_cameras_distinct_and_filters_unavailable_profiles(self):
        data = self.probe('refresh')
        self.assertFalse(data['busy'],data)
        self.assertEqual([p['name'] for p in data['cards'][0]['profiles']], ['stereo'])
        self.assertEqual([c['screen'] for c in data['captures']], [True, False])
        self.assertTrue(data['wifi'][0]['hotspot'])
        self.assertFalse(data['encrypted'][0]['unlocked'])
        self.assertTrue(data['drives'][0]['powerOff'])
        self.assertEqual({s['geometry'] for s in data['sources']}, {'0,0 1920x1080', '10,20 600x400'})

    def test_background_monitor_does_not_enumerate_audio_windows_or_wifi(self):
        data = self.probe('monitor')
        self.assertFalse(data['busy'],data)
        self.assertEqual(data['cards'], [])
        self.assertEqual(data['wifi'], [])
        self.assertEqual(data['sources'], [])
        self.assertEqual(len(data['captures']), 2)
        self.assertEqual(len(data['drives']), 1)

    def test_profile_uses_literal_arguments(self):
        name = 'card; echo injected'
        self.assertTrue(self.probe('profile', card=name, profile='stereo')['succeeded'])
        self.assertEqual(json.loads((self.base / 'profile.json').read_text()), ['set-card-profile', name, 'stereo'])

    def test_hotspot_is_volatile_and_password_goes_over_dbus(self):
        result = self.probe('hotspot', path='/org/freedesktop/NetworkManager/Devices/1', ssid='Test hotspot', password='secret123')
        self.assertTrue(result['succeeded'], result)
        entries = [json.loads(line) for line in (self.base / 'bus.log').read_text().splitlines()]
        hotspot = next(e['data'] for e in entries if e['method'] == 'hotspot')
        self.assertEqual(hotspot, dict(ssid='Test hotspot', password='secret123', persist='volatile', method='shared'))

    def test_hidden_network_uses_dbus_and_keeps_a_saved_profile(self):
        result = self.probe('hidden', ssid='Hidden test', password='secret123')
        self.assertTrue(result['succeeded'], result)
        entries = [json.loads(line) for line in (self.base / 'bus.log').read_text().splitlines()]
        hidden = next(e['data'] for e in entries if e['method'] == 'hidden' and e['data']['ssid'] == 'Hidden test')
        self.assertEqual(hidden, dict(ssid='Hidden test', password='secret123', persist='disk', method='auto', hidden=True))

    def test_activation_failure_is_not_reported_as_a_success(self):
        data = self.probe('hidden', ssid='Fail test', password='secret123')
        self.assertFalse(data['succeeded'])
        self.assertIn('Connection failed', data['error'])

    def test_short_hotspot_password_rejected_before_dbus(self):
        data = self.probe('hotspot', path='/org/freedesktop/NetworkManager/Devices/1', ssid='Test', password='short')
        self.assertFalse(data['succeeded'])
        self.assertIn('8', data['error'])

    def test_unlock_and_busy_volume_failure(self):
        path = '/org/freedesktop/UDisks2/block_devices/luks'
        self.assertIn('Incorrect passphrase', self.probe('unlock', path=path, password='wrong')['error'])
        self.assertTrue(self.probe('unlock', path=path, password='correct passphrase')['succeeded'])
        self.assertIn('busy', self.probe('lock', path=path)['error'])
        self.assertIn('Invalid', self.probe('unlock', path='/etc/passwd', password='x')['error'])

    def test_safe_power_off_uses_drive_api(self):
        self.assertTrue(self.probe('eject', path='/org/freedesktop/UDisks2/drives/usb')['succeeded'])

    def test_notification_rules_and_pause_survive_restart(self):
        first = self.probe('policy-write')
        second = self.probe('policy-read')
        self.assertTrue(second['paused'])
        self.assertEqual(second['until'], first['until'])
        self.assertEqual(second['rule'], 'silent')
        self.assertFalse(self.probe('policy-resume')['paused'])
        self.assertFalse(self.probe('policy-read')['paused'])

if __name__ == '__main__':
    unittest.main()
