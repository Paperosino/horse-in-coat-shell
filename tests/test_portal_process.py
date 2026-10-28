"""Actual spawn, pidfd, bounded output, cancellation and reaping; no shell."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PortalProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='hics-process-test-');cls.addClassCleanup(cls.temp.cleanup)
        cls.binary=Path(cls.temp.name)/'probe'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','libsystemd'],text=True))
        sanitizer=['-fsanitize=address,undefined','-fno-omit-frame-pointer','-g'] if os.environ.get('HICS_TEST_SANITIZERS') else []
        subprocess.run(['c++','-std=c++23','-Wall','-Wextra','-Werror','-pthread',*sanitizer,
            '-I'+str(ROOT/'native/portal-runtime'),str(ROOT/'native/portal-runtime/eventloop.cpp'),
            str(ROOT/'native/portal-runtime/process.cpp'),str(ROOT/'tests/fixtures/portal-process-probe.cpp'),*flags,'-o',str(cls.binary)],check=True)
    def probe(self,mode):
        run=subprocess.run([str(self.binary),mode],capture_output=True,text=True,timeout=8)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr);self.assertEqual(run.stdout.strip(),'PASS '+mode)
    def test_output_arguments_environment_and_exit_status(self):self.probe('echo')
    def test_exec_failure_leaves_no_child(self):self.probe('failed')
    def test_ignored_term_escalates_after_timeout(self):self.probe('timeout')
    def test_repeated_cancel_reaps_once(self):self.probe('cancel')
    def test_output_is_bounded(self):self.probe('flood')
    def test_child_does_not_inherit_parent_descriptors(self):self.probe('fds')
    def test_completion_can_destroy_supervisor(self):self.probe('delete')
    def test_destructor_reaps_without_callback(self):self.probe('destroy')
    def test_descendant_does_not_keep_pipes_open(self):self.probe('descendant')
    def test_hundred_lifetimes_do_not_leak_descriptors_or_children(self):self.probe('cleanup')
    def test_concurrent_children_have_bounded_capacity_and_cancel(self):self.probe('capacity')
    def test_missing_inherited_stdin_does_not_corrupt_pipes(self):self.probe('closed-stdin')
    def test_shutdown_releases_captured_results_before_dependencies(self):self.probe('shutdown')
