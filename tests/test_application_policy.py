"""Run the real admin backend in a user/mount namespace with fake package tools."""
import hashlib,json,os,shlex,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(shutil.which('apparmor_parser') and shutil.which('unshare'),'requires parser and user namespaces')
class ApplicationPolicy(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if subprocess.run(['unshare','--user','--map-root-user','--mount','true'],capture_output=True).returncode:raise unittest.SkipTest('unprivileged mount namespaces unavailable')
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-application-policy-');cls.addClassCleanup(cls.temp.cleanup);cls.base=Path(cls.temp.name)
  cls.pacman=cls.base/'pacman';cls.pacman.write_text('#!/usr/bin/python3\nimport os,sys\nprint(os.environ.get("HICS_POLICY_PACKAGE","fixture-app")+(" 1.0" if "-Q" in sys.argv else ""))\n');cls.pacman.chmod(0o755)
  cls.runner=cls.base/'systemd-run';cls.runner.write_text('#!/usr/bin/python3\nimport json,os,sys\nopen(os.environ["HICS_POLICY_COMMAND"],"w").write(json.dumps(sys.argv[1:]))\n');cls.runner.chmod(0o755)
  source=cls.base/'probe.cpp';source.write_text('''#include "backend.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QTextStream>
int main(int argc,char** argv){QCoreApplication app(argc,argv);auto input=QJsonDocument::fromJson(QTextStream(stdin).readAll().toUtf8()).object();QJsonObject result;try{System::validateApplications(argv[1],input);System::applyApplications(argv[1],input);result={{"ok",true}};}catch(const System::Failure& error){result={{"error",QString::fromUtf8(error.what())},{"code",error.code}};}QTextStream(stdout)<<QJsonDocument(result).toJson(QJsonDocument::Compact);}
''')
  cls.probe=cls.base/'probe';flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus'],text=True))
  subprocess.run(['c++','-std=c++20','-fPIC',str(source),str(ROOT/'native/system/applications.cpp'),'-I'+str(ROOT/'native/system'),'-DHYPRSTACK_PACMAN="'+str(cls.pacman)+'"','-DHYPRSTACK_SYSTEMD_RUN="'+str(cls.runner)+'"','-DHYPRSTACK_SYSTEMCTL="/usr/bin/systemctl"','-DHYPRSTACK_APPARMOR_PARSER="'+shutil.which('apparmor_parser')+'"',*flags,'-o',str(cls.probe)],check=True)
 def setUp(self):
  self.case=tempfile.TemporaryDirectory(dir=self.base);self.addCleanup(self.case.cleanup);self.dir=Path(self.case.name);self.profiles=self.dir/'profiles';self.profiles.mkdir();self.state=self.dir/'state';self.state.mkdir();self.apps=self.dir/'applications';self.apps.mkdir();(self.apps/'org.hics.Fixture.desktop').write_text('[Desktop Entry]\nType=Application\nName=Fixture\nExec=true\n')
  self.profile=self.profiles/'usr.bin.fixture';self.original='profile hics_fixture {\n /tmp/hics-test r,\n}\n';self.profile.write_text(self.original);self.command=self.dir/'command.json'
 def request(self,op,options,package='fixture-app'):
  code='''import os,subprocess,sys
profiles,state,apps,probe,operation=sys.argv[1:]
for source,target in [(profiles,"/etc/apparmor.d"),(apps,"/usr/share/applications")]:subprocess.run(["mount","--bind",source,target],check=True)
subprocess.run(["mount","-t","tmpfs","none","/var/lib"],check=True)
os.makedirs("/var/lib/hics")
subprocess.run(["mount","--bind",state,"/var/lib/hics"],check=True)
os.execv(probe,[probe,operation])
'''
  env=dict(os.environ,HICS_POLICY_PACKAGE=package,HICS_POLICY_COMMAND=str(self.command))
  value=subprocess.run(['unshare','--user','--map-root-user','--mount','--propagation','private','python3','-c',code,str(self.profiles),str(self.state),str(self.apps),str(self.probe),op],input=json.dumps(options),env=env,text=True,capture_output=True,timeout=40)
  self.assertEqual(value.returncode,0,value.stderr);return json.loads(value.stdout)
 def test_remove_uses_package_owner_and_keeps_dependency_checks(self):
  self.assertTrue(self.request('remove',{'desktop':'org.hics.Fixture.desktop','version':'1.0'})['ok'])
  command=json.loads(self.command.read_text());self.assertEqual(command[-4:],['-R','--noconfirm','--','fixture-app']);self.assertEqual(command[-5],str(self.pacman))
 def test_protected_packages_and_changed_versions_never_start_transaction(self):
  self.assertEqual(self.request('remove',{'desktop':'org.hics.Fixture.desktop','version':'1.0'},'pacman')['code'],'denied')
  self.assertEqual(self.request('remove',{'desktop':'org.hics.Fixture.desktop','version':'wrong'})['code'],'changed');self.assertFalse(self.command.exists())
 def test_policy_validation_and_atomic_backup(self):
  content=self.original.replace('/tmp/hics-test','/tmp/hics-other');result=self.request('profile-save',{'profile':self.profile.name,'content':content,'sha256':hashlib.sha256(self.original.encode()).hexdigest()});self.assertTrue(result.get('ok'),result)
  self.assertEqual(self.profile.read_text(),content);backups=list((self.state/'apparmor-backups').iterdir());self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_text(),self.original)
 def test_invalid_policy_and_stale_hash_preserve_previous_file(self):
  result=self.request('profile-save',{'profile':self.profile.name,'content':'profile { broken','sha256':hashlib.sha256(self.original.encode()).hexdigest()});self.assertIn('error',result);self.assertEqual(self.profile.read_text(),self.original)
  result=self.request('profile-save',{'profile':self.profile.name,'content':self.original,'sha256':'0'*64});self.assertEqual(result['code'],'changed');self.assertEqual(self.profile.read_text(),self.original)
 def test_visual_controls_preserve_local_policy_and_check_hashes(self):
  original=self.original.replace('}\n','#include <local/usr.bin.fixture>\n}\n');self.profile.write_text(original)
  local=self.profiles/'local';local.mkdir();(self.profiles/'tunables').mkdir();(self.profiles/'tunables/global').write_text('@{HOME}=/home/*/\n')
  policy=local/self.profile.name;policy.write_text('deny /tmp/keep rw,\n');before=policy.read_bytes()
  options={'profile':self.profile.name,'sha256':hashlib.sha256(original.encode()).hexdigest(),'localSha256':hashlib.sha256(before).hexdigest(),'restrictions':{'network':True,'camera':True,'home':False,'audio':False,'removable':False}}
  value=self.request('profile-controls',options);self.assertTrue(value.get('ok'),value)
  after=policy.read_text();self.assertIn('deny /tmp/keep rw,',after);self.assertIn('deny network inet,',after);self.assertIn('deny /dev/video[0-9]* rw,',after)
  self.assertNotIn('deny @{HOME}',after);self.assertEqual(self.profile.read_text(),original)
  value=self.request('profile-controls',options);self.assertEqual(value.get('code'),'changed');self.assertEqual(policy.read_text(),after)
 def test_visual_controls_reject_profiles_without_local_include(self):
  value=self.request('profile-controls',{'profile':self.profile.name,'sha256':hashlib.sha256(self.original.encode()).hexdigest(),'localSha256':hashlib.sha256(b'').hexdigest(),'restrictions':{'network':True}})
  self.assertEqual(value.get('code'),'unsupported');self.assertEqual(self.profile.read_text(),self.original)
if __name__=='__main__':unittest.main()
