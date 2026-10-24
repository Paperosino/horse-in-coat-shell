"""Bounded native prefetch never executes an application and observes EOF."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PrefetchHelper(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='hics-prefetch-test-');self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
  self.binary=ROOT/'build/native/system/hics-prefetch'
  if not self.binary.exists():self.skipTest('Build helpers first')
  self.executable=self.base/'application';self.executable.write_text('#!/bin/sh\ntouch '+str(self.base/'executed')+'\n'+'#'*(2*1024*1024));self.executable.chmod(0o700)
 def run_helper(self,path=None,mib='1',close=False):
  child=subprocess.Popen([str(self.binary),str(path or self.executable),mib],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   if close:child.stdin.close()
   child.wait(timeout=4);output=child.stdout.read();return child.returncode,json.loads(output) if output else {}
  finally:
   if child.poll() is None:child.kill();child.wait()
   for stream in (child.stdin,child.stdout,child.stderr):
    if stream:stream.close()
 def test_prefix_limit_without_application_execution(self):
  code,data=self.run_helper();self.assertEqual(code,0);self.assertEqual(data['advisedBytes'],1024*1024);self.assertFalse((self.base/'executed').exists())
 def test_eof_cancels_before_warming(self):
  code,data=self.run_helper(close=True);self.assertEqual(code,0);self.assertEqual(data['advisedBytes'],0)
 def test_non_executable_and_invalid_limit_are_rejected(self):
  self.executable.chmod(0o600);self.assertEqual(self.run_helper()[0],1)
  self.assertEqual(self.run_helper(mib='1000')[0],2)
 def test_fifo_is_not_read_or_warmed(self):
  fifo=self.base/'fifo';os.mkfifo(fifo,0o700);code,data=self.run_helper(fifo);self.assertEqual(code,0);self.assertEqual(data['advisedBytes'],0)
