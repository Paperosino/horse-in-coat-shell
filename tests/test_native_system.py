"""Validate native client requests before any privileged D-Bus operation."""
import json,os,subprocess,unittest
from pathlib import Path
CLIENT=Path(__file__).resolve().parents[1]/'build/native/system/hics-systemctl'
@unittest.skipUnless(CLIENT.exists(),'build hics-systemctl first')
class NativeSystemTests(unittest.TestCase):
 def invalid(self,section,operation,payload):
  env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS='unix:path=/nonexistent/hics-validation-test')
  result=subprocess.run([str(CLIENT),'apply',section,operation],input=json.dumps(payload),text=True,capture_output=True,env=env,timeout=3)
  response=json.loads(result.stdout);self.assertNotEqual(result.returncode,0);self.assertEqual(response['code'],'invalid',response)
 def test_printer_name_uri_and_operations(self):
  for op,value in [('add',{'name':'../cups','uri':'ipp://host/print','description':'x'}),('add',{'name':'ok','uri':'file:///etc/shadow','description':'x'}),('add',{'name':'ok','uri':'ipp://user:password@host/print','description':'x'}),('remove',{'name':'-o dest=evil'}),('shell',{'name':'ok'}),('cancel-job',{'id':-1}),('cancel-job',{'id':1.5})]:
   with self.subTest(op=op,value=value):self.invalid('printers',op,value)
 def test_time_and_profile_are_typed(self):
  for section,op,payload in [('datetime','ntp',{'enabled':'false'}),('datetime','timezone',{'timezone':'../../etc/shadow'}),('datetime','time',{'time':'1900-01-01T00:00:00'}),('power','profile',{'profile':'performance; reboot'}),('system','exec',{'command':'id'})]:
   with self.subTest(section=section,op=op):self.invalid(section,op,payload)
 def test_storage_only_accepts_udisks_volumes(self):
  self.invalid('storage','mount',{'path':'/org/freedesktop/systemd1'})
  self.invalid('storage','format',{'path':'/org/freedesktop/UDisks2/block_devices/sda'})
 def test_invalid_json_never_reaches_bus(self):
  result=subprocess.run([str(CLIENT),'apply','power','profile'],input='{"bad":',text=True,capture_output=True,timeout=3)
  self.assertEqual(json.loads(result.stdout)['code'],'invalid')
if __name__=='__main__':unittest.main()
