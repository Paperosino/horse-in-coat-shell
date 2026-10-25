import ast,json,os,subprocess,tempfile,time,sys
if "--fixture" not in sys.argv:
 raise SystemExit(subprocess.run(["dbus-run-session","--",sys.executable,__file__,"--fixture"]).returncode)
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-backup57-') as temp:
 b=Path(temp);(b/'home').mkdir();(b/'runtime').mkdir(mode=0o700);(b/'src').mkdir();(b/'src/document.txt').write_text('backup fixture content');(b/'src/[draft]?.txt').write_text('literal restore fixture')
 env=dict(os.environ,HOME=str(b/'home'),XDG_CONFIG_HOME=str(b/'config'),XDG_DATA_HOME=str(b/'data'),XDG_STATE_HOME=str(b/'state'),XDG_RUNTIME_DIR=str(b/'runtime'),PATH=os.environ.get('HICS_TEST_RESTIC_BIN','/usr/bin')+':'+os.environ['PATH'])
 env.pop('GNOME_KEYRING_CONTROL',None)
 keyring=subprocess.Popen(['gnome-keyring-daemon','--foreground','--unlock','--components=secrets','--control-directory='+str(b/'runtime/keyring')],env=env,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 keyring.stdin.write(b'fixture-keyring-password');keyring.stdin.close()
 daemon=subprocess.Popen([str(root/'build/native/desktop/hics-desktopd')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
 def call(method,*args):
  text=subprocess.check_output(['gdbus','call','--session','--dest','org.hics.Desktop1','--object-path','/org/hics/Desktop1','--method','org.hics.Desktop1.'+method,*args],text=True,stderr=subprocess.DEVNULL)
  return json.loads(ast.literal_eval(text)[0])
 def job(op,**args):
  ident=call('Start',op,json.dumps(args))['id']
  for _ in range(400):
   value=call('Result',ident)
   if value.get('finished'):
    assert not value['error'],(op,value)
    return value['result']
   time.sleep(.05)
  raise AssertionError('timeout '+op)
 try:
  for _ in range(60):
   try:call('Status');break
   except subprocess.CalledProcessError:time.sleep(.1)
  time.sleep(.5)
  job('backup.configure',repository=str(b/'repository'),folders=[str(b/'src')],password='fixture-backup-password',intervalHours=0)
  job('backup.init');job('backup.run');snapshots=job('backup.snapshots')['items'];assert len(snapshots)==1,snapshots
  listing=job('backup.files',snapshot=snapshots[0]['id'],folder=str(b/'src'))['items'];assert any(item['name']=='document.txt' for item in listing),listing
  (b/'src/document.txt').write_text('modified live file')
  job('backup.restore',snapshot=snapshots[0]['id'],target=str(b/'restored'))
  matches=list((b/'restored').rglob('document.txt'));assert len(matches)==1 and matches[0].read_text()=='backup fixture content',matches
  assert (b/'src/document.txt').read_text()=='modified live file'
  job('backup.restore',snapshot=snapshots[0]['id'],target=str(b/'single'),include=str(b/'src/[draft]?.txt'),literal=True)
  single=list((b/'single').rglob('*.txt'));assert len(single)==1 and single[0].read_text()=='literal restore fixture',single
  job('backup.check')
  ident=call('Start','backup.configure',json.dumps(dict(repository=str(b/'repository'),folders=[str(b/'src')],password='wrong-fixture-password',intervalHours=0)))['id']
  for _ in range(300):
   result=call('Result',ident)
   if result.get('finished'):break
   time.sleep(.03)
  assert 'saved credential was kept' in result['error'],result
  assert job('backup.snapshots')['items'], 'the previous keyring credential was overwritten'

  for file in (b/'state').rglob('*'):
   if file.is_file():assert b'fixture-backup-password' not in file.read_bytes(),file
  # Exercise the real minute scheduler without reducing production intervals.
  initial_ids={row['id'] for row in call('Status')['jobs'] if row['operation']=='backup.run'}
  job('backup.configure',repository=str(b/'repository'),folders=[str(b/'src')],intervalHours=1)
  deadline=time.monotonic()+70
  while time.monotonic()<deadline:
   scheduled=[row for row in call('Status')['jobs'] if row['operation']=='backup.run' and row['id'] not in initial_ids and row.get('finished')]
   if scheduled:break
   time.sleep(.5)
  assert scheduled and scheduled[0]['phase']=='completed',scheduled
  job('backup.configure',repository=str(b/'repository'),folders=[str(b/'src')],intervalHours=0)
  print('BACKUP_SCHEDULER_OK')
  config_path=b/'state/hics/desktop/backup.json' 
  config=json.loads(config_path.read_text());config['device']='offline-fixture';config['deviceUuid']='offline-fixture';config_path.write_text(json.dumps(config))
  ident=call('Start','backup.run','{}')['id']
  for _ in range(100):
   result=call('Result',ident)
   if result.get('finished'):break
   time.sleep(.03)
  assert 'not mounted' in result['error'],result
  print('BACKUP_ROUNDTRIP_OK')
 finally:
  daemon.terminate();daemon.wait(timeout=5);keyring.terminate();keyring.wait(timeout=5)
