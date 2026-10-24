"""Crash diagnostics remain private, bounded and independent of a live service."""
import json,os,stat,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CrashReports(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='hics-crash-test-');self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
  self.reports=self.base/'reports';self.reports.mkdir(mode=0o700);tools=self.base/'tools';tools.mkdir()
  for name in ('journalctl','coredumpctl'):
   command=tools/name;command.write_text('#!/usr/bin/python3\nimport sys\nsys.stdout.write("x"*1000000)\n');command.chmod(0o700)
  self.binary=ROOT/'build/native/system/hics-crash-report'
  if not self.binary.exists():self.skipTest('Build native helpers first')
  self.env=dict(os.environ,STATE_DIRECTORY=str(self.reports),PATH=str(tools)+':/usr/bin',SERVICE_RESULT='watchdog',INVOCATION_ID='a'*32)
 def run_report(self,**kwargs):
  return subprocess.run([str(self.binary)],env=dict(self.env,**kwargs),check=True,capture_output=True,timeout=5)
 def test_success_is_not_a_crash_report(self):
  self.run_report(SERVICE_RESULT='success');self.assertEqual(list(self.reports.iterdir()),[])
 def test_private_size_bounds_and_metadata(self):
  self.run_report();report=next(self.reports.iterdir());self.assertEqual(stat.S_IMODE(report.stat().st_mode),0o700)
  self.assertEqual(json.loads((report/'report.json').read_text())['result'],'watchdog')
  for file in report.iterdir():
   self.assertEqual(stat.S_IMODE(file.stat().st_mode),0o600);self.assertLessEqual(file.stat().st_size,256*1024)
  self.assertEqual((report/'journal.log').stat().st_size,256*1024)
 def test_retention_does_not_follow_symlinks(self):
  protected=self.base/'protected';protected.mkdir();(protected/'keep').write_text('keep')
  (self.reports/'report-000-symlink').symlink_to(protected,target_is_directory=True)
  for i in range(12):
   report=self.reports/f'report-001-{i:02}';report.mkdir(mode=0o700);(report/'nested-link').symlink_to(protected,target_is_directory=True)
  self.run_report()
  self.assertTrue((protected/'keep').exists());self.assertLessEqual(sum(p.is_dir() and not p.is_symlink() for p in self.reports.iterdir()),10)
 def test_untrusted_directory_is_rejected(self):
  self.reports.chmod(0o777)
  result=subprocess.run([str(self.binary)],env=self.env,capture_output=True,timeout=3)
  self.assertEqual(result.returncode,1);self.assertEqual(list(self.reports.iterdir()),[])
 def test_hung_log_reader_is_killed(self):
  command=self.base/'tools/journalctl';command.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(30)\n');command.chmod(0o700)
  start=time.monotonic();self.run_report(INVOCATION_ID='invalid');self.assertLess(time.monotonic()-start,2.5)
