"""Real native game helper against private fake daemons; no host power writes."""
import json,os,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class GameLeases(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='hics-game-lease-tests-');self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
  self.binary=ROOT/'build/native/system/hics-game-lease'
  if not self.binary.exists():self.skipTest('Build native helpers first')
  self.bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True)
  address=self.bus.stdout.readline().strip()
  self.env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address,HICS_LEASE_TEST_LOG=str(self.base/'calls'),HICS_LEASE_TEST_READY=str(self.base/'ready'))
  self.mock=None;self.game=None;self.helper=None
 def start(self,delay=0):
  self.mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_performance_bus.py')],env=dict(self.env,HICS_LEASE_TEST_DELAY=str(delay)),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  self.until(lambda:(self.base/'ready').exists())
  self.game=subprocess.Popen(['sleep','30'])
  self.helper=subprocess.Popen([str(self.binary),str(self.game.pid),'--gamemode','--performance'],env=self.env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 def events(self):
  try:return [json.loads(x) for x in (self.base/'calls').read_text().splitlines()]
  except FileNotFoundError:return []
 def until(self,predicate,timeout=4):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   if predicate():return
   time.sleep(.01)
  self.fail('Timed out: '+repr(self.events()))
 def tearDown(self):
  for child in (self.helper,self.game,self.mock,self.bus):
   if child is None:continue
   if child.poll() is None:child.terminate()
   try:child.wait(timeout=4)
   except subprocess.TimeoutExpired:child.kill();child.wait()
   for stream in (child.stdin,child.stdout,child.stderr):
    if stream:stream.close()
 def assert_released(self):
  self.assertEqual(self.helper.wait(timeout=4),0)
  events=self.events();kinds=[e['kind'] for e in events]
  for what in ('game-acquired','game-released','power-acquired','power-released'):self.assertIn(what,kinds)
  acquired=next(e for e in events if e['kind']=='game-acquired')
  self.assertEqual(acquired['pids'],[self.game.pid,self.helper.pid])
 def test_eof_releases_game_and_power_leases(self):
  self.start();self.until(lambda:len(self.events())==2);self.helper.stdin.close();self.assert_released()
 def test_late_acquisition_after_eof_is_released(self):
  self.start(delay=300);time.sleep(.08);self.helper.stdin.close();self.assert_released()
 def test_game_exit_triggers_pidfd_cleanup(self):
  self.start();self.until(lambda:len(self.events())==2);self.game.terminate();self.game.wait();self.assert_released()

 def test_zero_cookie_is_released_explicitly(self):
  self.env['HICS_LEASE_TEST_COOKIE']='0';self.start();self.until(lambda:len(self.events())==2);self.helper.stdin.close();self.assert_released()
  self.assertEqual(next(e['cookie'] for e in self.events() if e['kind']=='power-released'),0)
