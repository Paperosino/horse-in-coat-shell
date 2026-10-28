"""Real sd-event fd/timer lifetimes and async replies on a private D-Bus."""
import os
from pathlib import Path
import select
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PortalEventLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='hics-event-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.binary = cls.base/'probe'
        flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','libsystemd','sdbus-c++'],text=True))
        sanitizer = ['-fsanitize=address,undefined','-fno-omit-frame-pointer','-g'] if os.environ.get('HICS_TEST_SANITIZERS') else []
        subprocess.run(['c++','-std=c++23','-Wall','-Wextra','-Werror','-pthread',*sanitizer,
                        '-I'+str(ROOT/'native/portal-runtime'),str(ROOT/'native/portal-runtime/eventloop.cpp'),str(ROOT/'native/portal-runtime/process.cpp'),
                        str(ROOT/'tests/fixtures/portal-eventloop-probe.cpp'),*flags,'-o',str(cls.binary)],check=True)
        config=cls.base/'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(cls.base)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        cls.bus=subprocess.Popen(['dbus-daemon','--nofork','--config-file='+str(config),'--print-address=1'],stdout=subprocess.PIPE,text=True)
        cls.addClassCleanup(cls.close_bus)
        assert select.select([cls.bus.stdout],[],[],5)[0], 'Private bus unavailable'
        address=cls.bus.stdout.readline().strip()
        assert address
        cls.env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address)

    @classmethod
    def close_bus(cls):
        cls.bus.terminate()
        try:cls.bus.wait(timeout=5)
        except subprocess.TimeoutExpired:cls.bus.kill();cls.bus.wait(timeout=5)
        cls.bus.stdout.close()

    def probe(self, mode):
        run=subprocess.run([str(self.binary),mode],env=self.env,capture_output=True,text=True,timeout=8)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertEqual(run.stdout.strip(),'PASS '+mode)

    def test_timer_callbacks_can_change_timer_set(self):self.probe('timers')
    def test_two_thousand_timer_callbacks_remain_safe(self):self.probe('timer-storm')
    def test_fd_callback_can_remove_itself(self):self.probe('fd-remove')
    def test_fd_callback_can_replace_itself(self):self.probe('fd-replace')
    def test_closed_fd_number_can_be_reused(self):self.probe('fd-reuse')
    def test_pipe_eof_does_not_terminate_other_sources(self):self.probe('hup')
    def test_timer_can_destroy_loop_owner(self):self.probe('delete-timer')
    def test_fd_callback_can_destroy_loop_owner(self):self.probe('delete-io')
    def test_callback_exception_stays_inside_c_boundary(self):self.probe('throw')
    def test_foreign_thread_cannot_mutate_loop(self):self.probe('thread')
    def test_repeated_loop_lifetimes_release_fds(self):self.probe('cleanup')
    def test_invalid_replacement_retains_original_watch(self):self.probe('invalid')
    def test_actual_delayed_dbus_reply(self):self.probe('dbus')
    def test_pending_process_result_dies_before_dbus_connection(self):self.probe('dbus-process-teardown')
