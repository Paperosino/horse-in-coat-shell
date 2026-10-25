"""Exercise actual C++ storage code against a private UDisks D-Bus fixture."""
import json,os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'build/native/system/libhics-system-backend.a'
@unittest.skipUnless(LIB.exists(),'build native backend first')
class StorageBusTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  try:import dbus
  except ImportError:raise unittest.SkipTest('dbus-python is required')
  cls.tmp=tempfile.TemporaryDirectory(prefix='hyprstack-storage-test-')
  cls.probeBinary=Path(cls.tmp.name)/'probe'
  source=cls.probeBinary.with_suffix('.cpp')
  source.write_text('''#include "backend.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QTextStream>
int main(int argc,char **argv) { QCoreApplication app(argc,argv); try {
QJsonObject result;
if (argc == 1) result=System::storageStatus();
else if(QString::fromUtf8(argv[1])=="broker-configure") { System::storageMaintenance("configure",QJsonDocument::fromJson(QTextStream(stdin).readAll().toUtf8()).object()); result={{"ok",true}}; }
else if(QString::fromUtf8(argv[1]).startsWith("maintenance-")) { System::storageMaintenance(QString::fromUtf8(argv[1]).mid(12),QJsonDocument::fromJson(QTextStream(stdin).readAll().toUtf8()).object()); result={{"ok",true}}; }
else result=System::storageAction(QString::fromUtf8(argv[1]), QJsonDocument::fromJson(QTextStream(stdin).readAll().toUtf8()).object());
QTextStream(stdout)<<System::encode(result)<<Qt::endl; return 0;
} catch(const std::exception &e) { QTextStream(stdout)<<System::encode(System::failure(e))<<Qt::endl;return 1; }}''')
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus'],text=True))
  subprocess.run(['c++','-std=c++20','-fPIC',str(source),'-I',str(ROOT/'native/system'),str(LIB),*flags,'-lcups','-o',str(cls.probeBinary)],check=True,capture_output=True)
  cls.bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True)
  cls.env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=cls.bus.stdout.readline().strip())
  cls.mockProcess=subprocess.Popen(['python3',str(ROOT/'tests/mock_storage_bus.py')],env=cls.env,stdout=subprocess.PIPE,text=True)
  if cls.mockProcess.stdout.readline().strip()!='ready':raise RuntimeError('storage fixture did not start')
 @classmethod
 def tearDownClass(cls):
  for proc in (cls.mockProcess,cls.bus):proc.terminate();proc.wait(timeout=5);proc.stdout.close()
  cls.tmp.cleanup()
 def probe(self,op=None,options=None):
  p=subprocess.run([str(self.probeBinary)]+([op] if op else []),input=json.dumps(options or {}),text=True,capture_output=True,env=self.env,timeout=5)
  return json.loads(p.stdout)
 def fixture(self,method,*args):
  subprocess.run(['busctl','--address='+self.env['DBUS_SYSTEM_BUS_ADDRESS'],'call','org.freedesktop.UDisks2','/org/freedesktop/UDisks2/block_devices/test','org.hics.Test',method,*args],check=True,capture_output=True)
 def options(self):return dict(path='/org/freedesktop/UDisks2/block_devices/test',directory='/mnt/test',automatic=True,readOnly=False,noexec=True,nosuid=True,nodev=True,nofail=True,noatime=False)
 def test_broker_reloads_mount_units_after_configuration(self):
  self.fixture('SetOptions','s','defaults')
  self.assertTrue(self.probe('broker-configure',self.options())['ok'])
  response=subprocess.check_output(['busctl','--address='+self.env['DBUS_SYSTEM_BUS_ADDRESS'],'call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.hics.Test','ReloadCount'],text=True)
  self.assertEqual(response.strip(),'u 1')
 def test_cached_smart_without_device_io(self):
  v=self.probe()['volumes'][0];self.assertEqual(v['smart']['temperature'],30);self.assertEqual(v['smart']['hours'],2);self.assertFalse(v['smart']['failing'])
 def test_maintenance_uses_typed_background_jobs(self):
  target=Path(self.tmp.name)/'volume';target.mkdir(exist_ok=True)
  for op,ssd,program in [('defragment',False,'e4defrag'),('trim',True,'fstrim')]:
   with self.subTest(operation=op):
    self.fixture('SetMount','sb',str(target),'true' if ssd else 'false')
    result=self.probe('maintenance-'+op,{'path':self.options()['path']})
    self.assertTrue(result.get('ok'),result)
    output=subprocess.check_output(['busctl','--address='+self.env['DBUS_SYSTEM_BUS_ADDRESS'],'--json=short','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.hics.Test','LastTask'],text=True)
    task=json.loads(json.loads(output)['data'][0])
    self.assertTrue(task['program'].endswith('/'+program));self.assertEqual(task['arguments'][1:],['--',str(target)])
    self.assertEqual(task['nice'],19);self.assertTrue(task['noNewPrivileges']);self.assertEqual(task['unit'],'hyprstack-disk-test.service')
  self.fixture('SetMount','sb','','true')
 def test_cleanup_uses_fixed_commands_and_rejects_paths(self):
  for op,program,args in [('clean-packages','paccache',['-r','-k3']),('clean-coredumps','systemd-tmpfiles',['--clean','--prefix=/var/lib/systemd/coredump'])]:
   with self.subTest(operation=op):
    result=self.probe('maintenance-'+op,{})
    self.assertTrue(result.get('ok'),result)
    output=subprocess.check_output(['busctl','--address='+self.env['DBUS_SYSTEM_BUS_ADDRESS'],'--json=short','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.hics.Test','LastTask'],text=True)
    task=json.loads(json.loads(output)['data'][0]);self.assertTrue(task['program'].endswith('/'+program));self.assertEqual(task['arguments'][1:],args);self.assertEqual(task['nice'],19)
    invalid=self.probe('maintenance-'+op,{'path':'/home'})
    self.assertEqual(invalid.get('code'),'invalid')
  self.assertEqual(self.probe('maintenance-automatic-package-cleanup',{'enabled':'yes'}).get('code'),'invalid')
 def test_mount_options_preserve_unrelated_values(self):
  self.fixture('SetOptions','s','uid=1000,gid=1000,relatime,compress=zstd:1,rw,exec,auto')
  self.assertTrue(self.probe('configure',self.options())['ok'])
  v=self.probe()['volumes'][0];opts=set(v['mountOptions'].split(','))
  self.assertTrue({'uid=1000','gid=1000','relatime','compress=zstd:1','noexec','nosuid','nodev','nofail'}<=opts)
  self.assertTrue(v['automatic']);self.assertTrue(v['mountEditable'])
 def test_disable_startup_removes_systemd_automount(self):
  self.fixture('SetOptions','s','defaults,x-systemd.automount')
  o=self.options();o['automatic']=False;o['readOnly']=True;o['noatime']=True
  self.assertTrue(self.probe('configure',o)['ok'])
  v=self.probe()['volumes'][0];self.assertFalse(v['automatic']);self.assertIn('ro',v['mountOptions']);self.assertNotIn('x-systemd.automount',v['mountOptions'])
 def test_system_mounts_cannot_be_modified(self):
  self.fixture('Protect')
  self.assertEqual(self.probe('configure',self.options())['code'],'invalid')
 def test_typed_switches_and_paths(self):
  for key,value in [('directory','/etc'),('directory','/mnt/test/../etc'),('directory','/mnt/test\nother'),('directory','/mnt/test\n'),('automatic','yes')]:
   o=self.options();o[key]=value
   self.assertEqual(self.probe('configure',o)['code'],'invalid')
if __name__=='__main__':unittest.main()
