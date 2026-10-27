"""Crash-loop decisions and known-good startup checkpoints use private storage."""
import importlib, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shell/assets'))
class RecoveryTests(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.base=Path(tmp.name)
  env=patch.dict(os.environ,{f'XDG_{name}_HOME':str(self.base/name.lower()) for name in ('CONFIG','STATE','DATA')}|{'HYPRLAND_INSTANCE_SIGNATURE':'fixture'})
  env.start();self.addCleanup(env.stop)
  for name in ('feature_common','shell_recovery','configuration_manager'):
   setattr(self,name,importlib.reload(importlib.import_module(name)))
  self.r=self.shell_recovery
 def test_third_start_is_safe_and_clean_restart_is_not_a_crash(self):
  r=self.r
  self.assertFalse(r.begin(10));r.finish(1,11)
  self.assertFalse(r.begin(12));r.finish(-11,13)
  self.assertTrue(r.begin(14));r.finish(0,15)
  self.assertFalse(r.begin(200));r.finish(0,201)
  self.assertFalse(r.begin(202))
 def test_killed_runner_and_session_change(self):
  r=self.r;r.begin(10);self.assertFalse(r.begin(11));self.assertTrue(r.begin(12))
  with patch.dict(os.environ,HYPRLAND_INSTANCE_SIGNATURE='different'):
   self.assertFalse(r.begin(13))
 def test_corrupt_crash_record_cannot_block_login(self):
  r=self.r;r.RECORD.parent.mkdir(parents=True);r.RECORD.write_text('{invalid')
  self.assertFalse(r.begin(10))
  r.RECORD.write_text(json.dumps({'boot':r.boot(),'session':'fixture','failures':{'invalid':1}}))
  self.assertFalse(r.begin(11))
 def test_changed_candidate_is_never_promoted(self):
  r=self.r;r.begin(10);r.CONFIG.mkdir(parents=True,exist_ok=True)
  f=r.CONFIG/'shell.json';f.write_text('{"appearance":{"scale":1}}')
  before=r.candidate();f.write_text('{"appearance":{"scale":2}}')
  self.assertFalse(r.healthy(before));self.assertFalse(r.GOOD.exists())
  self.assertTrue(r.healthy(r.candidate()));self.assertEqual(set(r.good()['files']),set(r.CORE))
  self.assertEqual(r.GOOD.stat().st_mode&0o777,0o600)
 def test_non_object_and_symlink_never_become_checkpoint(self):
  r=self.r;r.CONFIG.mkdir(parents=True);f=r.CONFIG/'shell.json';f.write_text('[]')
  with self.assertRaises(ValueError):r.candidate()
  f.unlink();f.symlink_to(self.base/'external')
  (self.base/'external').write_text('{}')
  with self.assertRaises(ValueError):r.candidate()
 def test_restore_uses_existing_timed_guard_and_never_rewrites_displays(self):
  r=self.r;m=self.configuration_manager;r.begin(10);r.CONFIG.mkdir(parents=True,exist_ok=True)
  f=r.CONFIG/'shell.json';f.write_text('{"appearance":{"scale":1}}');self.assertTrue(r.healthy(r.candidate()))
  f.write_text('{"appearance":{"scale":2}}');display=r.CONFIG/'display-profiles.json';display.write_text('{"keep":true}')
  with patch.object(m,'apply_files',side_effect=lambda files,*args: [m.write_text(m.target(k),v) for k,v in files.items()]),patch.object(m,'runtime',return_value=self.base/'runtime'):
   state=m.dispatch('restore-startup',{},shell_pid=123)
   self.assertTrue(state['pending']);self.assertIsNone(m.read_json(m.JOURNAL)['shellPid'])
   self.assertEqual(json.loads(f.read_text())['appearance']['scale'],1)
   m.rollback(False)
  self.assertEqual(json.loads(f.read_text())['appearance']['scale'],2)
  self.assertEqual(display.read_text(),'{"keep":true}')
 def test_real_runner_switches_to_safe_shell_after_two_child_crashes(self):
  import socket
  import session_runner as runner
  import extension_recovery
  importlib.reload(extension_recovery)
  runtime=self.base/'run';endpoint=runtime/'hypr/fixture/.socket2.sock';endpoint.parent.mkdir(parents=True)
  server=socket.socket(socket.AF_UNIX);server.bind(str(endpoint));server.listen(8)
  self.addCleanup(server.close)
  binpath=self.base/'bin';binpath.mkdir();trace=self.base/'attempts'
  executable=binpath/'hics-shell'
  executable.write_text('#!'+sys.executable+'\nimport os,sys\nwith open('+repr(str(trace))+',"a") as f:f.write(os.environ.get("HICS_SAFE_MODE","0")+"\\n")\nsys.exit(0 if os.environ.get("HICS_SAFE_MODE")=="1" else 1)\n');executable.chmod(0o700)
  with patch.dict(os.environ,{'XDG_RUNTIME_DIR':str(runtime),'PATH':str(binpath)+':'+os.environ['PATH']}),patch.object(runner,'prepare_session'),patch.object(runner,'load_capture_plugin'):
   self.assertEqual(runner.run_session(),1)
   self.assertEqual(runner.run_session(),1)
   self.assertEqual(runner.run_session(),0)
   for code in (75,76):
    executable.write_text('#!'+sys.executable+'\nimport sys\nsys.exit('+str(code)+')\n')
    self.assertEqual(runner.run_session(),code)
    record=self.r.read(self.r.RECORD)
    self.assertEqual(record['requested'],code==75)
    self.assertFalse(record['active']);self.assertEqual(record['failures'],[])
  self.assertEqual(trace.read_text().splitlines(),['0','0','1'])
 def test_runner_mode_loop_restores_original_environment(self):
  import session_runner as runner
  seen=[]
  def run():
   seen.append(os.environ.get('FONTCONFIG_FILE'))
   if len(seen)==1:
    os.environ['FONTCONFIG_FILE']='safe-only';os.environ['HICS_SAFE_MODE']='1'
    return 76
   return 0
  with patch.dict(os.environ,{'FONTCONFIG_FILE':'user-fonts'}),patch.object(sys,'argv',['runner','run']),patch.object(runner,'paths',return_value=(self.base/'lock',self.base/'event')),patch.object(runner,'run_session',side_effect=run):
   self.assertEqual(runner.main(),0)
   self.assertEqual(seen,['user-fonts','user-fonts'])
 def test_invalid_json_recovers_from_startup_checkpoint_instead_of_unproven_history(self):
  r=self.r;m=self.configuration_manager;r.begin(10);r.CONFIG.mkdir(parents=True,exist_ok=True)
  f=r.CONFIG/'shell.json';f.write_text('{"appearance":{"scale":1}}');r.healthy(r.candidate())
  f.write_text('{"appearance":{"scale":2}}')
  m.snapshot('Unproven edit',False)
  f.write_bytes(b'{invalid\xff')
  m.repair_invalid_json()
  self.assertEqual(json.loads(f.read_text())['appearance']['scale'],1)
  backups=list((r.STATE/'configuration-recovery').glob('*.invalid'))
  self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),b'{invalid\xff')
 def test_actual_shell_wrapper_uses_independent_root_and_skips_migration(self):
  import subprocess
  data=self.base/'installed';qs=data/'qs/bin/hics-qs';qs.parent.mkdir(parents=True)
  qs.write_text('#!'+sys.executable+'\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n');qs.chmod(0o700)
  migration=data/'shell/assets/migrate_branding.py';migration.parent.mkdir(parents=True)
  migration.write_text('raise RuntimeError("migration must not run in safe mode")')
  env=dict(os.environ,HICS_DATA_DIR=str(data),HICS_SAFE_MODE='1',HYPRSTACK_SHELL_DIR='/wrong/root')
  result=subprocess.run([str(ROOT/'distribution/bin/hics-shell')],env=env,text=True,capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(json.loads(result.stdout)[:2],['--path',str(data/'shell/recovery')])
 def test_damaged_history_metadata_is_ignored(self):
  import gzip
  m=self.configuration_manager;m.HISTORY.mkdir(parents=True)
  invalid={'version':1,'id':'x','files':{'shell.json':'{}'},'created':None}
  (m.HISTORY/'bad.json.gz').write_bytes(gzip.compress(json.dumps(invalid).encode()))
  self.assertEqual(m.history(),[])
 def test_manual_recovery_uses_owner_ipc_without_systemctl(self):
  import subprocess
  r=self.r
  with patch.object(r.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'true','')) as run:
   self.assertTrue(r.command('on')['restarting'])
  self.assertEqual(run.call_count,1)
  self.assertEqual(run.call_args.args[0][-4:],['call','sessionControl','transition','on'])
  self.assertFalse(r.RECORD.exists())
 def test_locked_owner_denies_without_fallback_or_journal_mutation(self):
  import subprocess
  r=self.r;r.STATE.mkdir(parents=True,exist_ok=True);r.RECORD.write_bytes(b'{invalid\xff')
  with patch.object(r.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'false','')) as run:
   with self.assertRaisesRegex(ValueError,'Unlock'):r.command('on')
  self.assertEqual(run.call_count,1)
  self.assertEqual(r.RECORD.read_bytes(),b'{invalid\xff')
 def test_safe_root_fallback_and_old_shell_fail_closed(self):
  import subprocess
  r=self.r
  with patch.object(r.subprocess,'run',side_effect=[subprocess.CompletedProcess([],1,'','missing'),subprocess.CompletedProcess([],0,'true','')]) as run:
   self.assertTrue(r.command('resume')['restarting'])
  self.assertTrue(run.call_args_list[1].args[0][3].endswith('/shell/recovery'))
  with patch.object(r.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','missing')) as run:
   with self.assertRaisesRegex(ValueError,'coordinated'):r.command('on')
  self.assertEqual(run.call_count,2)
 def test_status_keeps_guard_actions_available_with_damaged_crash_journal(self):
  r=self.r;m=self.configuration_manager;r.STATE.mkdir(parents=True,exist_ok=True)
  original=b'{invalid\xff';r.RECORD.write_bytes(original)
  guard={'startupCheckpoint':{'available':True},'pending':{'token':'fixture'},'recoveryWarning':'Existing warning'}
  with patch.object(m,'request',return_value=guard):result=r.command('status')
  self.assertEqual(result['startupCheckpoint'],guard['startupCheckpoint'])
  self.assertEqual(result['pending'],guard['pending'])
  self.assertIn('Existing warning',result['recoveryWarning'])
  self.assertIn('state is unknown',result['recoveryWarning'])
  self.assertEqual(r.RECORD.read_bytes(),original)
 def test_startup_ack_does_not_erase_recent_crashes(self):
  r=self.r;r.begin(10);r.finish(1,11);self.assertFalse(r.begin(12))
  r.healthy(r.candidate());r.finish(1,50)
  self.assertTrue(r.begin(51))
 def test_safe_runner_sleeps_on_events_even_after_days(self):
  import session_runner as runner
  self.assertIsNone(runner.session_wait_timeout(True,30,3,None,1e9))
  self.assertEqual(runner.session_wait_timeout(False,60,40,30,10),20)
 def test_unconfirmed_preview_is_never_promoted_to_working_checkpoint(self):
  r=self.r;r.STATE.mkdir(parents=True,exist_ok=True)
  (r.STATE/'configuration-preview.json').write_text('{}')
  self.assertFalse(r.healthy(r.candidate()));self.assertFalse(r.GOOD.exists())

 def test_nonregular_recovery_record_never_blocks_startup(self):
  r=self.r;r.RECORD.parent.mkdir(parents=True)
  os.mkfifo(r.RECORD)
  self.assertFalse(r.begin(10))
  self.assertTrue(r.RECORD.is_file())
 def test_checkpoint_rejects_nonfinite_configuration(self):
  r=self.r;r.STATE.mkdir(parents=True,exist_ok=True)
  files={name:'{}' for name in r.CORE};files['shell.json']='{"scale":NaN}'
  r.GOOD.write_text(json.dumps({'version':1,'files':files}))
  with self.assertRaises(ValueError):r.good()
 def test_record_symlink_does_not_read_external_content(self):
  r=self.r;r.STATE.mkdir(parents=True,exist_ok=True)
  external=self.base/'external';external.write_text('{"requested":true}')
  r.RECORD.symlink_to(external)
  self.assertFalse(r.begin(10))
  self.assertEqual(external.read_text(),'{"requested":true}')

 def test_oversized_snapshot_section_is_rejected_before_reading(self):
  m=self.configuration_manager;m.CONFIG.mkdir(parents=True,exist_ok=True)
  path=m.CONFIG/'shell.json'
  with path.open('wb') as stream:stream.truncate(64*1024*1024)
  with patch.object(Path,'open',side_effect=AssertionError('Oversized file must not be read')):
   with self.assertRaisesRegex(ValueError,'too large'):m.gather()

 def test_candidate_rejects_fifo_without_blocking(self):
  r=self.r;r.CONFIG.mkdir(parents=True);os.mkfifo(r.CONFIG/'shell.json')
  with self.assertRaisesRegex(ValueError,'regular file'):r.candidate()
 def test_candidate_rejects_replacement_symlink_at_open(self):
  r=self.r;r.CONFIG.mkdir(parents=True);path=r.CONFIG/'shell.json';path.write_text('{}')
  external=self.base/'private';external.write_text('{"private":true}')
  original=os.open
  def replaced(name,flags,*args,**kwargs):
   if Path(name)==path:
    path.unlink();path.symlink_to(external)
   return original(name,flags,*args,**kwargs)
  with patch.object(r.os,'open',side_effect=replaced):
   with self.assertRaisesRegex(ValueError,"Symlinked"):r.candidate()
  self.assertEqual(external.read_text(),'{"private":true}')
 def test_candidate_caps_read_even_if_file_grows_after_fstat(self):
  r=self.r;r.CONFIG.mkdir(parents=True);path=r.CONFIG/'shell.json';path.write_text('{}')
  original=os.fstat
  def grow(fd):
   info=original(fd)
   if info.st_ino==path.stat().st_ino:
    with path.open('ab') as stream:stream.write(b' '*(1024*1024))
   return info
  with patch.object(r.os,'fstat',side_effect=grow):
   with self.assertRaisesRegex(ValueError,'too large'):r.candidate()

 def test_exit_with_malformed_failure_entries_still_records_crash(self):
  r=self.r
  for failures in ([None,{},'bad',True,9,10,10**400],{'bad':1},'bad',None):
   with self.subTest(failures=failures):
    r.begin(10);record=r.read(r.RECORD);record['failures']=failures;record['safe']=False
    self.feature_common.atomic_json(r.RECORD,record,private=True)
    r.finish(1,11)
    saved=r.read(r.RECORD)
    self.assertFalse(saved['active']);self.assertEqual(saved['failures'][-1],11)
    self.assertTrue(all(type(x) in (int,float) for x in saved['failures']))

 def test_failure_window_handles_large_numbers_without_float_conversion(self):
  r=self.r
  self.assertEqual(r.recent_failures({'failures':[True,None,{},'x',-10**400,10**400,float('nan'),float('inf'),-float('inf'),-1,0,119,120,121]},120.0),[0,119,120])
  self.assertEqual(r.recent_failures({'failures':list(range(20))},20),list(range(13,20)))
  r.begin(10);record=r.read(r.RECORD);record['active']=False;record['failures']=[10**400,9,10]
  self.feature_common.atomic_json(r.RECORD,record,private=True)
  self.assertTrue(r.begin(11.0))

 def test_strict_object_depth_limit_checks_after_null_leaves(self):
  r=self.r
  self.assertEqual(r.strict_object('{"a":null,"b":[null,{"c":1}]}'),{'a':None,'b':[None,{'c':1}]})
  with self.assertRaisesRegex(ValueError,'nesting limit'):
   r.strict_object('{"a":null,"deep":'+'['*200+'0'+']'*200+'}')

 def test_broken_preview_symlink_never_promotes_working_checkpoint(self):
  r=self.r;r.STATE.mkdir(parents=True,exist_ok=True)
  (r.STATE/'configuration-preview.json').symlink_to(self.base/'missing-journal')
  self.assertFalse(r.healthy(r.candidate()));self.assertFalse(r.GOOD.exists())
