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
   for name in ('hics-systemd','hics-systemctl','hics-memory','hics-region','hics-game-lease','hics-crash-report','hics-prefetch','hics-gpu-monitor'):(prefix/'bin'/name).write_bytes(b'fixture')
   plan={str(path):(content,mode) for path,content,mode in installer.deployment(prefix)}
   self.assertEqual(len(plan),13)
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
  required=['install.sh','native/system/CMakeLists.txt','third_party/phantomat/main.cpp','distribution/install_system_helper.py','distribution/native_plugins.py','shell/assets/gtk_theme.py','packaging/arch/hic-shell.install','tests/fixtures/virtual-pointer.c']
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
 def test_no_graphical_session_only_reloads_managers(self):
  self.env['HICS_TEST_UNITS']+='\nuser@invalid.service loaded active running invalid\nunrelated.service loaded active running other'
  _,commands=self.run_hook()
  self.assertEqual([c for c in commands[1:] if c[-1]!='show-environment'],[
   ['--user','--machine=1000@.host','daemon-reload'],
   ['--user','--machine=1001@.host','daemon-reload']])
  self.assertFalse(any(action in c for c in commands for action in ('start','restart','try-restart','stop')))
 def test_unreachable_user_does_not_block_other_sessions(self):
  self.env.update(HICS_TEST_FAIL_MACHINE='--machine=1000@.host',HICS_TEST_FAIL_COMMAND='daemon-reload')
  result,commands=self.run_hook()
  self.assertIn(['--user','--machine=1001@.host','daemon-reload'],commands)
  self.assertIn('could not reload user manager 1000',result.stderr)
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
  self.assertIn(['--global','enable','hics-desktop.service'],commands)

 def test_first_install_starts_shell_only_with_hyprland_environment(self):
  import socket
  runtime=self.directory/'runtime';(runtime/'hypr/fixture').mkdir(parents=True)
  sockets=[]
  for name in ('hypr/fixture/.socket.sock','wayland-1'):
   sock=socket.socket(socket.AF_UNIX);sock.bind(str(runtime/name));sockets.append(sock);self.addCleanup(sock.close)
  self.env['HICS_TEST_MANAGER_ENV']='HYPRLAND_INSTANCE_SIGNATURE=fixture\nWAYLAND_DISPLAY=wayland-1\nXDG_RUNTIME_DIR='+str(runtime)
  result,commands=self.run_hook()
  self.assertIn(['--user','--machine=1000@.host','start','hic-session.service'],commands)
  self.assertIn(['--user','--machine=1001@.host','start','hic-session.service'],commands)
  for unit in ('hics-configuration.service','hics-displays.service','hics-desktop.service'):
   self.assertIn(['--user','--machine=1000@.host','start',unit],commands)
  self.assertFalse(any(action in c for c in commands for action in ('restart','try-restart','stop')))
  self.assertIn('log out and back in',result.stderr)

 def test_failed_activation_does_not_stop_existing_services(self):
  import socket
  runtime=self.directory/'runtime';(runtime/'hypr/fixture').mkdir(parents=True)
  for name in ('hypr/fixture/.socket.sock','wayland-1'):
   sock=socket.socket(socket.AF_UNIX);sock.bind(str(runtime/name));self.addCleanup(sock.close)
  self.env.update(HICS_TEST_MANAGER_ENV='HYPRLAND_INSTANCE_SIGNATURE=fixture\nWAYLAND_DISPLAY=wayland-1\nXDG_RUNTIME_DIR='+str(runtime),
   HICS_TEST_FAIL_MACHINE='--machine=1000@.host',HICS_TEST_FAIL_COMMAND='hic-session.service')
  result,commands=self.run_hook()
  self.assertIn('could not activate hic-session.service for user 1000',result.stderr)
  self.assertIn(['--user','--machine=1001@.host','start','hic-session.service'],commands)
  self.assertFalse(any(action in c for c in commands for action in ('restart','try-restart','stop')))

 def test_no_running_user_managers_do_not_start_a_shell(self):
  self.env['HICS_TEST_UNITS']=''
  result,commands=self.run_hook()
  self.assertEqual(len(commands),1)
  self.assertEqual(commands[0][0],'list-units')

 def test_stale_graphical_environment_without_sockets_does_not_start_services(self):
  self.env['HICS_TEST_MANAGER_ENV']='HYPRLAND_INSTANCE_SIGNATURE=gone\nWAYLAND_DISPLAY=wayland-999\nXDG_RUNTIME_DIR='+str(self.directory)
  _,commands=self.run_hook()
  self.assertFalse(any('restart' in command or 'start' in command for command in commands))
 def test_offline_install_still_enables_all_own_services(self):
  import json
  if not Path('/usr/share/hyprstack').is_symlink():self.skipTest('requires existing compatibility link')
  result=subprocess.run(['bash','-c','. "$1"; hics_systemd_running() { return 1; }; post_install','hook-test',str(ROOT/'packaging/arch/hic-shell.install')],env=self.env,text=True,capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr)
  commands=[json.loads(line) for line in self.log.read_text().splitlines()]
  for unit in ('hics-system.service','hics-memory.service'):self.assertIn(['enable',unit],commands)
  for unit in ('hic-session.service','hics-desktop.service','hics-displays.service','hics-configuration.service'):self.assertIn(['--global','enable',unit],commands)
  self.assertFalse(any('restart' in command or 'daemon-reload' in command for command in commands))
  self.assertFalse(any('hics-screen-reader.service' in command for command in commands))
