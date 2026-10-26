"""Exercise installer commands with fake pacman/makepkg; no host mutations."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ArchInstaller(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.bin=self.base/'bin';self.bin.mkdir();self.log=self.base/'log'
  self.env=dict(os.environ,PATH=str(self.bin)+':'+os.environ['PATH'],HICS_INSTALL_TEST_LOG=str(self.log),HICS_INSTALL_FIXTURE=str(self.base))
  tool='''#!/usr/bin/python3
import os,sys,json,shutil
from pathlib import Path
name=Path(sys.argv[0]).name;args=sys.argv[1:];base=Path(os.environ['HICS_INSTALL_FIXTURE'])
with open(os.environ['HICS_INSTALL_TEST_LOG'],'a') as log:log.write(json.dumps([name,*args])+'\\n')
if name=='pacman':
 if args[0]=='-T':
  if not (base/'dependencies-installed').exists():print('rsync\\nlibsecret');sys.exit(127)
 elif args[0]=='-S':(base/'dependencies-installed').touch()
 elif args[0]=='-Qqp':print('hic-shell')
 elif args[0]=='-U':
  assert all(Path(arg).exists() for arg in args[2:]),args
elif name=='sudo':
 if os.environ.get('HICS_INSTALL_DENY_SUDO'):sys.exit(1)
 assert args[0]=='--',args
 os.execvp(args[1],args[1:])
elif name=='Hyprland':print(json.dumps({'version':'0.56.2','abiHash':'fixture'}))
elif name=='python3':
 if args[0]=='-c':print('fixture')
 else:assert args[0].endswith('distribution/check_headers.py'),args
elif name=='rsync':
 # The real source staging is covered by package tests; avoid copying 400MB.
 pass
elif name=='makepkg':
 target=Path(os.environ['PKGDEST'])/'hic-shell-1.1.1-67-x86_64.pkg.tar.zst'
 if '--packagelist' in args:print(target)
 else:
  assert '-i' not in args and '--install' not in args,args
  assert (base/'dependencies-installed').exists()
  target.write_text('fixture package');Path(str(target)+'.sig').write_text('signature')
'''
  for name in ('pacman','sudo','Hyprland','python3','rsync','makepkg'):
   path=self.bin/name;path.write_text(tool);path.chmod(0o755)
  # Run a source copy of scripts in a path with spaces. Only installer artifacts
  # may be written to this private repository, never to the real checkout.
  self.repo=self.base/'repo with spaces';(self.repo/'packaging/arch').mkdir(parents=True);(self.repo/'distribution').mkdir()
  for relative in ('packaging/arch/build-package.sh','packaging/arch/PKGBUILD','packaging/arch/hic-shell.install','install.sh'):
   target=self.repo/relative;target.write_bytes((ROOT/relative).read_bytes());target.chmod(0o755)
 def run_script(self,*args,entry='packaging/arch/build-package.sh'):
  result=subprocess.run(['bash',str(self.repo/entry),*args],env=self.env,capture_output=True,text=True,timeout=10)
  commands=[json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
  return result,commands
 def test_source_installs_runtime_and_build_dependencies_before_staging(self):
  result,commands=self.run_script('--install')
  self.assertEqual(result.returncode,0,result.stderr)
  check=next(c for c in commands if c[:2]==['pacman','-T']);self.assertIn('libsecret',check);self.assertIn('rsync',check);self.assertIn('hyprland=0.56.2',check)
  install=next(c for c in commands if c[:2]==['pacman','-S']);self.assertEqual(install,['pacman','-S','--needed','--','rsync','libsecret'])
  self.assertLess(commands.index(install),next(i for i,c in enumerate(commands) if c[0]=='rsync'))
  built=[c for c in commands if c[0]=='makepkg'];self.assertEqual(len(built),2)
  upgrades=[c for c in commands if c[:2]==['pacman','-U']];self.assertEqual(len(upgrades),1)
  self.assertEqual(len(upgrades[0]),4);self.assertTrue(upgrades[0][-1].endswith('.pkg.tar.zst'))
  artifact=Path(upgrades[0][-1]);self.assertTrue(artifact.exists());self.assertTrue(Path(str(artifact)+'.sig').exists())
  self.assertFalse(any('-n' in c or '--noconfirm' in c or '-Sy' in c for c in commands))
 def test_dry_run_never_installs_or_builds(self):
  result,commands=self.run_script('--dry-run','--install');self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual([c[0] for c in commands],['pacman']);self.assertIn('libsecret',result.stdout)
 def test_build_only_does_not_install_artifact(self):
  result,commands=self.run_script();self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(any(c[:2]==['pacman','-U'] for c in commands))
 def test_prebuilt_installs_without_build_dependencies(self):
  package=self.base/'binary package.pkg.tar.zst';package.write_text('fixture')
  result,commands=self.run_script('--package',str(package),entry='install.sh');self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual([c[0] for c in commands],['pacman','sudo','pacman']);self.assertEqual(commands[-1],['pacman','-U','--',str(package)])
 def test_prebuilt_dry_run_is_read_only(self):
  package=self.base/'binary.pkg.tar.zst';package.touch()
  result,commands=self.run_script('--package',str(package),'--dry-run',entry='install.sh');self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(len(commands),1)

 def test_failed_authentication_never_reports_a_successful_install(self):
  (self.base/'dependencies-installed').touch();self.env['HICS_INSTALL_DENY_SUDO']='1'
  result,commands=self.run_script('--install')
  self.assertNotEqual(result.returncode,0);self.assertNotIn('Package installed.',result.stdout)
  self.assertTrue(list(self.repo.glob('hic-shell-*.pkg.tar.zst')),'Built artifact must survive installation failure')
 def test_failed_dependency_install_does_not_start_build(self):
  self.env['HICS_INSTALL_DENY_SUDO']='1'
  result,commands=self.run_script('--install')
  self.assertNotEqual(result.returncode,0);self.assertFalse(any(c[0] in ('rsync','makepkg') for c in commands))
