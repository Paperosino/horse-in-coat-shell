"""Native platform operations against private services; no host account/device writes."""
import ast,base64,hashlib,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Platform(unittest.TestCase):
 def test_private_platform(self):
  result=subprocess.run(['dbus-run-session','--',sys.executable,__file__,'--fixture'],capture_output=True,text=True,timeout=45)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertIn('PLATFORM_OK',result.stdout)
def fixture():
 from PIL import ImageCms
 with tempfile.TemporaryDirectory(prefix='hics-platform-') as directory:
  base=Path(directory);bin=base/'bin';bin.mkdir();runtime=base/'runtime';runtime.mkdir(mode=0o700)
  env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=os.environ['DBUS_SESSION_BUS_ADDRESS'],XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_RUNTIME_DIR=str(runtime),XDG_SESSION_ID='test-current',HICS_PLATFORM_TRACE=str(base/'trace'),PATH=str(bin)+':'+os.environ['PATH'])
  (bin/'hyprctl').write_text('#!/usr/bin/python3\nimport json,sys,os\nfrom pathlib import Path\nif sys.argv[1]=="monitors":print(json.dumps([{\"name\":\"DP-TEST\",\"description\":\"Fixture display\"}]))\nelif sys.argv[1]=="configerrors":\n p=Path(os.environ["XDG_CONFIG_HOME"])/"fail-config";print("invalid fixture profile" if p.exists() else "");p.unlink(missing_ok=True)\nelse:print("ok")\n')
  (bin/'fwupdmgr').write_text('#!/usr/bin/python3\nimport json,sys\nprint(json.dumps({"Devices":[{"DeviceId":"a"*40,"Name":"Fixture firmware","Version":"1.0","Releases":[{"Version":"2.0"}]}]}))\n')
  for executable in bin.iterdir():executable.chmod(0o755)
  mock=subprocess.Popen([sys.executable,str(ROOT/'tests/mock_platform_bus.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  assert mock.stdout.readline().strip()=='ready'
  daemon=subprocess.Popen([str(ROOT/'build/native/desktop/hics-desktopd')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
  def call(method,*args):
   r=subprocess.check_output(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.'+method,*args],env=env,text=True,stderr=subprocess.DEVNULL)
   return json.loads(ast.literal_eval(r)[0])
  def job(op,**args):
   start=call('Start',op,json.dumps(args));assert 'id' in start,start
   for _ in range(150):
    value=call('Result',start['id'])
    if value.get('finished'):return value
    time.sleep(.02)
   raise AssertionError('Job timed out: '+op)
  try:
   for _ in range(100):
    owner=subprocess.check_output(['gdbus','call','--session','--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus','--method','org.freedesktop.DBus.NameHasOwner','org.hics.Desktop1'],env=env,text=True)
    if 'true' in owner:break
    if daemon.poll() is not None:raise AssertionError(daemon.stderr.read())
    time.sleep(.03)
   state=job('accounts.status')['result'];assert len(state['users'])==2,state;assert state['fingerprintReader']=='Fixture reader';assert state['fingers']==['right-index-finger'];assert state['sessions'][0]['current']
   admin='/org/freedesktop/Accounts/User1000';guest='/org/freedesktop/Accounts/User1001'
   assert job('accounts.role',path=admin,administrator=False)['error']
   assert not job('accounts.role',path=guest,administrator=True)['error']
   assert not job('accounts.role',path=admin,administrator=False)['error']
   assert 'PermissionDenied' in job('accounts.rename',path=guest,realName='Denied')['error']
   assert not job('accounts.rename',path=guest,realName='Guest renamed')['error']
   assert job('accounts.rename',path='/org/freedesktop/Accounts/User0',realName='No')['error']
   assert job('accounts.create',name='bad;name',realName='No')['error']
   assert not job('accounts.create',name='newuser',realName='New User')['error']
   assert job('accounts.terminate',id='test-current',confirmed=True)['error']
   assert job('accounts.terminate',id='other')['error']
   assert not job('accounts.terminate',id='other',confirmed=True)['error']
   assert not job('accounts.activate',id='other')['error']
   firmware=job('firmware.status');assert not firmware['error'],firmware;assert firmware['result']['Devices'][0]['Name']=='Fixture firmware'
   assert job('firmware.update',id='a'*40)['error'];assert job('firmware.update',id='--force',confirmed=True)['error']
   assert job('accounts.fingerprint-enroll',finger='invalid')['error']
   assert job('accounts.fingerprint-delete',finger='right-index-finger')['error']
   assert not job('accounts.fingerprint-delete',finger='right-index-finger',confirmed=True)['error']
   source=base/'display.icc';source.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
   imported=job('colour.import',path=str(source));assert not imported['error'],imported
   path=imported['result']['path'];assert Path(path).read_bytes()==source.read_bytes()
   corrupt=base/'corrupt.icc';corrupt.write_bytes(b'bad'*100);assert job('colour.import',path=str(corrupt))['error']
   colour=job('colour.status');assert not colour['error'],colour;assert colour['result']['colord'];assert len(colour['result']['profiles'])==1
   assert not job('colour.assign',output='DP-TEST',path=path)['error']
   config=base/'config/hics';before=(config/'colour-profiles.json').read_bytes();lua=(config/'colour-profiles.lua').read_bytes()
   (base/'config/fail-config').write_text('1');failed=job('colour.assign',output='DP-TEST',path='');assert failed['error'],failed
   assert (config/'colour-profiles.json').read_bytes()==before;assert (config/'colour-profiles.lua').read_bytes()==lua
   assert not job('colour.assign',output='DP-TEST',path='')['error'];assert 'icc=""' in (config/'colour-profiles.lua').read_text()
   assert job('colour.assign',output='DP-MISSING',path=path)['error']
   targets=[config/'hypr-user.lua',config/'colour-profiles.lua',config/'colour-profiles.json']
   before=[target.read_bytes() for target in targets]
   after=[before[0],b'-- interrupted colour write\n',before[2]]
   journal=base/'state/hics/desktop/colour-rollback.json'
   journal.write_text(json.dumps({'files':[{'before':base64.b64encode(old).decode(),'existed':True,'afterHash':hashlib.sha256(new).hexdigest()} for old,new in zip(before,after)]}))
   targets[1].write_bytes(after[1])
   daemon.terminate();daemon.wait(timeout=10)
   daemon.stderr.close()
   daemon=subprocess.Popen([str(ROOT/'build/native/desktop/hics-desktopd')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
   for _ in range(100):
    if not journal.exists():break
    time.sleep(.03)
   assert not journal.exists(),'interrupted colour transaction was not recovered on startup'
   assert [target.read_bytes() for target in targets]==before

   print('PLATFORM_OK')
  finally:
   daemon.terminate();daemon.wait(timeout=10);mock.terminate();mock.wait(timeout=3)
   if daemon.returncode:print(daemon.stderr.read())
   daemon.stderr.close();mock.stderr.close();mock.stdout.close()
if __name__=='__main__':
 if '--fixture' in sys.argv:fixture()
 else:unittest.main()
