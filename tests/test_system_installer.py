"""Validate the privileged helper's installation plan without writing host files."""
import importlib.util,tempfile,unittest,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('system_installer',ROOT/'distribution/install_system_helper.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
class SystemInstaller(unittest.TestCase):
 def test_service_never_executes_user_owned_build(self):
  with tempfile.TemporaryDirectory() as directory:
   prefix=Path(directory);(prefix/'bin').mkdir()
   for name in ('hics-systemd','hics-systemctl','hics-memory'):(prefix/'bin'/name).write_bytes(b'fixture')
   plan={str(path):(content,mode) for path,content,mode in installer.deployment(prefix)}
   self.assertEqual(len(plan),8)
   for path,(content,mode) in plan.items():
    self.assertNotIn(directory,path)
    if path.endswith('.service'):
     self.assertNotIn(directory,content.decode());self.assertIn('/usr/local/bin/hics-memory' if path.endswith('hics-memory.service') else '/usr/local/bin/hics-systemd',content.decode())
    self.assertEqual(mode,0o755 if path.startswith('/usr/local/bin/') else 0o644)
 def test_package_wires_system_service_post_install(self):
  pkg=(ROOT/'packaging/arch/PKGBUILD').read_text()
  script=(ROOT/'packaging/arch/build-package.sh').read_text()
  self.assertIn('install=hic-shell.install',pkg);self.assertIn('"$here/hic-shell.install"',script)

 def test_fresh_checkout_includes_installer_dependencies(self):
  if not (ROOT/'.git').exists():self.skipTest('archive checkout')
  required=['native/system/CMakeLists.txt','third_party/phantomat/main.cpp','distribution/install_system_helper.py','distribution/native_plugins.py','shell/assets/gtk_theme.py','packaging/arch/hic-shell.install','tests/fixtures/virtual-pointer.c']
  result=subprocess.run(['git','check-ignore',*required],cwd=ROOT,text=True,capture_output=True)
  self.assertEqual(result.stdout,'',result.stdout)

class ArchSessionRestart(unittest.TestCase):
 def setUp(self):
  import os, sys
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.directory=Path(self.temp.name);self.log=self.directory/'systemctl.jsonl'
  command=self.directory/'systemctl'
  command.write_text('#!'+sys.executable+'\n'+'''import json, os, sys
args=sys.argv[1:]
with open(os.environ['HICS_TEST_LOG'],'a') as stream:
 stream.write(json.dumps(args)+'\\n')
if args and args[0]=='list-units':
 print(os.environ.get('HICS_TEST_UNITS',''))
elif args and args[-1]=='show-environment':
 print(os.environ.get('HICS_TEST_MANAGER_ENV',''))
elif os.environ.get('HICS_TEST_FAIL_MACHINE') in args and args[-1]==os.environ.get('HICS_TEST_FAIL_COMMAND'):
 sys.exit(1)
''')
  command.chmod(0o755)
  (self.directory/'install').write_text('#!/bin/sh\nexit 0\n');(self.directory/'install').chmod(0o755)
  self.env=dict(os.environ,PATH=str(self.directory)+':'+os.environ['PATH'],HICS_TEST_LOG=str(self.log),HICS_TEST_UNITS='user@1000.service loaded active running User Manager\nuser@1001.service loaded active running User Manager')
 def run_hook(self):
  import json
  result=subprocess.run(['bash','-c','. "$1"; hics_restart_user_sessions','hook-test',str(ROOT/'packaging/arch/hic-shell.install')],env=self.env,text=True,capture_output=True)
  commands=[json.loads(line) for line in self.log.read_text().splitlines()]
  self.assertEqual(result.returncode,0,result.stderr)
  return result,commands
 def test_reload_and_try_restart_each_running_user_manager(self):
  self.env['HICS_TEST_UNITS']+='\nuser@invalid.service loaded active running invalid\nunrelated.service loaded active running other'
  result,commands=self.run_hook()
  self.assertEqual([c for c in commands[1:] if c[-1]!='show-environment'],[['--user','--machine=1000@.host','daemon-reload'],['--user','--machine=1000@.host','try-restart','hic-session.service'],['--user','--machine=1001@.host','daemon-reload'],['--user','--machine=1001@.host','try-restart','hic-session.service']])
  # A plain restart/start would also launch shells in inactive or TTY sessions.
  self.assertFalse(any('restart' in command or 'start' in command for command in commands))
  self.assertEqual(result.stderr,'')
 def test_unreachable_user_does_not_block_other_sessions(self):
  self.env.update(HICS_TEST_FAIL_MACHINE='--machine=1000@.host',HICS_TEST_FAIL_COMMAND='daemon-reload')
  result,commands=self.run_hook()
  self.assertNotIn(['--user','--machine=1000@.host','try-restart','hic-session.service'],commands)
  self.assertIn(['--user','--machine=1001@.host','try-restart','hic-session.service'],commands)
  self.assertIn('could not reload user manager 1000',result.stderr)
 def test_failed_restart_does_not_abort_package_or_other_users(self):
  # Match the final argument (unit name) for this simulated transport failure.
  self.env.update(HICS_TEST_FAIL_MACHINE='--machine=1000@.host',HICS_TEST_FAIL_COMMAND='hic-session.service')
  result,commands=self.run_hook()
  self.assertIn(['--user','--machine=1001@.host','try-restart','hic-session.service'],commands)
  self.assertIn('could not restart the active shell for user 1000',result.stderr)
 def test_package_enables_and_starts_system_and_session_units(self):
  import json
  if not Path('/run/systemd/system').is_dir():self.skipTest('requires systemd installation paths')
  if not Path('/usr/share/hyprstack').is_symlink():self.skipTest('legacy compatibility link must already exist')
  result=subprocess.run(['bash','-c','. "$1"; post_install','hook-test',str(ROOT/'packaging/arch/hic-shell.install')],env=self.env,text=True,capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr)
  commands=[json.loads(line) for line in self.log.read_text().splitlines()]
  self.assertIn(['enable','hics-system.service'],commands)
  self.assertIn(['enable','hics-memory.service'],commands)
  self.assertIn(['restart','hics-memory.service'],commands)
  memory_unit=(ROOT/'distribution/systemd/system/hics-memory.service').read_text()
  self.assertIn('RuntimeDirectoryPreserve=yes',memory_unit)
  self.assertIn(['restart','hics-system.service'],commands)
  self.assertIn(['--global','enable','hic-session.service'],commands)

 def test_first_install_starts_shell_only_with_hyprland_environment(self):
  self.env['HICS_TEST_MANAGER_ENV']='HYPRLAND_INSTANCE_SIGNATURE=fixture\nWAYLAND_DISPLAY=wayland-1'
  result,commands=self.run_hook()
  self.assertIn(['--user','--machine=1000@.host','restart','hic-session.service'],commands)
  self.assertIn(['--user','--machine=1001@.host','restart','hic-session.service'],commands)

 def test_no_running_user_managers_do_not_start_a_shell(self):
  self.env['HICS_TEST_UNITS']=''
  result,commands=self.run_hook()
  self.assertEqual(len(commands),1)
  self.assertEqual(commands[0][0],'list-units')
