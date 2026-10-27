"""Run new C++ session services against fake tools and a private system bus."""
import contextlib
import json
import select
import shutil
import time
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
        cls.addClassCleanup(cls.cleanup)
        cls.base = Path(cls.temp.name)
        cls.binary = cls.base / 'probe'
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
            'Qt6Core', 'Qt6Qml', 'Qt6DBus', 'Qt6Multimedia'], text=True))
        probe_source=cls.base/'probe.cpp'
        shutil.copy2(ROOT/'tests/fixtures/desktop-integration-probe.cpp',probe_source)
        sources = [probe_source]
        for name in ('desktopintegration', 'notificationpolicy', 'wallpaperplayer'):
            source = Path(os.environ.get('HICS_TEST_DESKTOP_SOURCE', SERVICES / (name + '.cpp'))) if name == 'desktopintegration' else SERVICES / (name + '.cpp')
            header = Path(os.environ.get('HICS_TEST_DESKTOP_HEADER', SERVICES / (name + '.hpp'))) if name == 'desktopintegration' else SERVICES / (name + '.hpp')
            shutil.copy2(source,cls.base/(name+'.cpp'));shutil.copy2(header,cls.base/(name+'.hpp'))
            moc = cls.base / (name + '-moc.cpp')
            subprocess.run([str(Path(subprocess.check_output(['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip()) / 'moc'), str(cls.base / (name + '.hpp')), '-o', str(moc), *shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'Qt6Qml', 'Qt6Multimedia'], text=True))], check=True)
            sources.extend([cls.base/(name+'.cpp'), moc])
        sanitizers=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-g'] if os.environ.get('HICS_TEST_SANITIZERS') else []
        subprocess.run(['c++', '-std=c++20', '-fPIC', *sanitizers, *map(str, sources), '-I', str(cls.base), '-I', str(SERVICES),
            *flags, '-o', str(cls.binary)], check=True)
        if os.environ.get('HICS_TEST_ARTIFACT_DIR'):
            artifact=Path(os.environ['HICS_TEST_ARTIFACT_DIR']);artifact.mkdir(parents=True,exist_ok=True,mode=0o700)
            shutil.copy2(cls.binary,artifact/'desktop-probe')
        bus_config = cls.base/'bus.conf'
        bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(cls.base)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        cls.bus = subprocess.Popen(['dbus-daemon', '--config-file='+str(bus_config), '--nofork', '--print-address=1'], stdout=subprocess.PIPE, text=True)
        cls.env = dict(os.environ, DBUS_SYSTEM_BUS_ADDRESS=cls.bus.stdout.readline().strip(),
            DESKTOP_BUS_LOG=str(cls.base / 'bus.log'), XDG_CONFIG_HOME=str(cls.base / 'config'),
            HOME=str(cls.base/'home'), XDG_DATA_HOME=str(cls.base/'data'),
            XDG_STATE_HOME=str(cls.base/'state'), XDG_CACHE_HOME=str(cls.base/'cache'),
            DESKTOP_PORTAL_FAULT_FILE=str(cls.base/'portal-fault'))
        cls.mock = subprocess.Popen(['python3', str(ROOT / 'tests/mock_desktop_bus.py')], env=cls.env, stdout=subprocess.PIPE, text=True)
        if not select.select([cls.mock.stdout],[],[],5)[0] or cls.mock.stdout.readline().strip() != 'ready':
            raise RuntimeError('Private desktop D-Bus fixture failed to start')
        tools = cls.base / 'tools'
        tools.mkdir()
        tool = '''#!/usr/bin/python3
import json, os, sys, time
name=os.path.basename(sys.argv[0])
mode=os.environ.get('HICS_TEST_TOOL_MODE','')
if name==os.environ.get('HICS_TEST_TOOL_TARGET','pactl') and mode=='hang':time.sleep(60)
if name==os.environ.get('HICS_TEST_TOOL_TARGET','pactl') and mode in ('stdout-overflow','stderr-overflow'):
 os.write(1 if mode=='stdout-overflow' else 2,b'x'*(32*1024*1024));sys.exit(0 if mode=='stdout-overflow' else 1)
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
        cls.env.update(PATH=str(tools) + ':' + os.environ['PATH'], PROFILE_LOG=str(cls.base / 'profile.json'),
            DBUS_SESSION_BUS_ADDRESS=cls.env['DBUS_SYSTEM_BUS_ADDRESS'],
            PIPEWIRE_REMOTE='hics-desktop-test-absent', PULSE_SERVER='unix:'+str(cls.base/'absent-pulse'),QT_FORCE_STDERR_LOGGING='1')

    @classmethod
    def cleanup(cls):
        for name in ('mock', 'bus'):
            process = getattr(cls,name,None)
            if not process:continue
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            if process.stdout and not process.stdout.closed:process.stdout.close()
        cls.temp.cleanup()

    def probe(self, operation, environment=None, **options):
        started=time.monotonic()
        run = subprocess.run([str(self.binary)], input=json.dumps(dict(operation=operation, **options)),
            env=environment or self.env, capture_output=True, text=True, check=False, timeout=options.get('waitMs',5000)/1000+8)
        self.assertEqual(run.returncode,0,run.stderr[-16000:])
        self.last_stderr=run.stderr;self.last_seconds=time.monotonic()-started
        return json.loads(run.stdout)

    def test_network_refresh_does_not_load_multimedia_backend(self):
        data=self.probe('refresh')
        self.assertFalse(data['multimediaBackendLoaded'])

    def test_observers_can_destroy_backend_at_operation_boundaries(self):
        for mode in ('delete-busy', 'delete-success', 'delete-microphone'):
            with self.subTest(mode=mode):
                env = dict(self.env,QT_FFMPEG_DECODING_HW_DEVICE_TYPES=',',QT_FFMPEG_ENCODING_HW_DEVICE_TYPES=',')
                data = self.probe(mode,environment=env)
                self.assertTrue(data['deletedFromSignal'])
                self.assertTrue(data['childReaped'])
                self.assertEqual(data['retiredProcesses'],0)

    def test_deleting_backend_reaps_hanging_helper_without_ui_wait(self):
        data = self.probe('delete-busy',environment=dict(self.env,HICS_TEST_TOOL_MODE='hang'))
        self.assertTrue(data['deletedFromSignal'])
        self.assertTrue(data['childReaped'])
        self.assertLess(data['deletionMs'],1000)
        self.assertNotIn('Destroyed while process',self.last_stderr)
        self.assertEqual(data['retiredProcesses'],0)

    def test_dbus_result_signals_can_destroy_backend(self):
        for mode, backend in (('delete-success','hotspot'), ('delete-success','unlock'),
                              ('delete-hidden-finished',''), ('delete-mounted','')):
            with self.subTest(mode=mode,backend=backend):
                self.assertTrue(self.probe(mode,backend=backend)['deletedFromSignal'])

    def test_error_notification_can_destroy_backend_after_failed_exec(self):
        tool = self.base/'tools/pactl'; original = tool.read_bytes()
        tool.write_text('#!/nonexistent/hics-test-interpreter\n')
        try:
            self.assertTrue(self.probe('delete-error')['deletedFromSignal'])
        finally:
            tool.write_bytes(original)

    def test_destroy_while_exec_is_failing_does_not_leave_retired_process(self):
        tool = self.base/'tools/pactl'; original = tool.read_bytes()
        tool.write_text('#!/nonexistent/hics-test-interpreter\n')
        try:
            data = self.probe('delete-busy')
            self.assertTrue(data['deletedFromSignal'])
            self.assertEqual(data['retiredProcesses'],0)
        finally:
            tool.write_bytes(original)

    def test_stdout_overflow_is_bounded_and_releases_busy(self):
        data=self.probe('refresh',environment=dict(self.env,HICS_TEST_TOOL_MODE='stdout-overflow'))
        self.assertFalse(data['busy'])
        self.assertEqual(data['pendingProcesses'],[])
        self.assertEqual(data['pendingCalls'],0)
        self.assertIn('too much data',data['error'][:512])
        self.assertIn('pactl',self.last_stderr)
        self.assertNotIn('x'*128,self.last_stderr)

    def test_stderr_overflow_keeps_diagnostics_bounded(self):
        data=self.probe('refresh',environment=dict(self.env,HICS_TEST_TOOL_MODE='stderr-overflow'))
        self.assertFalse(data['busy'])
        self.assertLessEqual(len(data['error']),4096)
        self.assertIn('too much data',data['error'][:512])

    def test_silent_capture_overflow_marks_monitor_unavailable(self):
        data=self.probe('monitor',environment=dict(self.env,HICS_TEST_TOOL_MODE='stdout-overflow',HICS_TEST_TOOL_TARGET='pw-dump'))
        self.assertFalse(data['busy'])
        self.assertFalse(data['captureAvailable'])
        self.assertEqual(data['captures'],[])
        self.assertEqual(data['pendingProcesses'],[])
        self.assertIn('pw-dump',self.last_stderr)

    def test_helper_timeout_kills_process_and_releases_busy(self):
        data=self.probe('refresh',environment=dict(self.env,HICS_TEST_TOOL_MODE='hang'),waitMs=18000)
        self.assertFalse(data['busy'])
        self.assertEqual(data['pendingProcesses'],[])
        self.assertIn('did not respond in time',data['error'])
        self.assertIn('operation timed out',self.last_stderr)
        self.assertGreater(self.last_seconds,14)

    def test_failed_exec_does_not_strand_busy(self):
        tool=self.base/'tools/pactl';original=tool.read_bytes()
        tool.write_text('#!/nonexistent/hics-test-interpreter\n')
        try:data=self.probe('refresh')
        finally:tool.write_bytes(original)
        self.assertFalse(data['busy'],data)
        self.assertEqual(data['pendingProcesses'],[])
        self.assertTrue(data['error'])

    @contextlib.contextmanager
    def portal_fault(self, mode):
        file=Path(self.env['DESKTOP_PORTAL_FAULT_FILE']);file.write_text(mode)
        try:yield
        finally:
            file.unlink(missing_ok=True)
            if self.mock.poll() is not None:self.restart_mock()

    def restart_mock(self):
        self.mock.wait(timeout=5);self.mock.stdout.close()
        self.__class__.mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_desktop_bus.py')],env=self.env,stdout=subprocess.PIPE,text=True)
        self.assertEqual(self.mock.stdout.readline().strip(),'ready')

    def test_portal_timeout_and_late_reply_do_not_keep_busy_or_publish_stale_capabilities(self):
        for mode in ('hang','late'):
            with self.subTest(mode=mode),self.portal_fault(mode):
                data=self.probe('refresh',settleMs=1200)
                self.assertFalse(data['busy'],data)
                self.assertEqual(data['pendingCalls'],0)
                self.assertEqual(data['portalSourceTypes'],0)

    def test_backend_destroyed_before_late_portal_reply(self):
        with self.portal_fault('late'):
            self.assertTrue(self.probe('destroy-active')['destroyed'])

    def test_malformed_portal_capabilities_are_unavailable(self):
        with self.portal_fault('malformed'):
            data=self.probe('refresh')
        self.assertFalse(data['busy'],data)
        self.assertEqual(data['portalSourceTypes'],0)

    def test_portal_owner_death_and_retry_use_the_replacement_service(self):
        resume=self.base/'portal-resume';resume.unlink(missing_ok=True)
        with self.portal_fault('drop'):
            child=subprocess.Popen([str(self.binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=self.env)
            try:
                child.stdin.write(json.dumps({'operation':'portal-retry','resumeFile':str(resume)}));child.stdin.close()
                self.assertTrue(select.select([child.stdout],[],[],8)[0],'Probe did not settle after service death')
                first=json.loads(child.stdout.readline())
                self.assertTrue(first['readyForRetry']);self.assertFalse(first['busy'])
                self.assertEqual(first['portalSourceTypes'],0)
                self.mock.wait(timeout=5)
                Path(self.env['DESKTOP_PORTAL_FAULT_FILE']).unlink()
                self.restart_mock();resume.touch()
                self.assertTrue(select.select([child.stdout],[],[],8)[0],'Probe did not settle after replacement service')
                data=json.loads(child.stdout.readline());child.wait(timeout=5)
                self.assertEqual(child.returncode,0,child.stderr.read())
                self.assertFalse(data['busy'],data)
                self.assertEqual(data['pendingCalls'],0)
                self.assertEqual(data['portalSourceTypes'],3)
            finally:
                if child.poll() is None:child.kill();child.wait(timeout=5)
                child.stdout.close();child.stderr.close();resume.unlink(missing_ok=True)

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
        log = self.base/'bus.log'
        offset = log.stat().st_size if log.exists() else 0
        result = self.probe('hotspot', path='/org/freedesktop/NetworkManager/Devices/1', ssid='Test hotspot', password='secret123')
        self.assertTrue(result['succeeded'], result)
        entries = [json.loads(line) for line in log.read_bytes()[offset:].splitlines()]
        hotspots = [e['data'] for e in entries if e['method'] == 'hotspot']
        self.assertEqual(hotspots, [dict(ssid='Test hotspot', password='secret123', persist='volatile', method='shared')])

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
