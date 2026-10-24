#!/usr/bin/env python3
"""Real onboarding clicks/typing and native locale generation via a scoped test bridge.

The bridge accepts only the already configured ru_RU locale, never a command or
path. It restores /etc/locale.conf and /etc/locale.gen on exit. It emulates denied
authorization for the error scenario and uses the real sandboxed system broker
for the successful scenario. No production authorization policy is changed.
"""
import os,sys,json,socket,subprocess,tempfile,time,importlib.util,getpass
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if '--privileged' not in sys.argv:
 raise SystemExit('Use --privileged and provide the sudo password on stdin; this regenerates the already configured ru_RU locale and restores locale configuration files.')
password=getpass.getpass('sudo password for the scoped locale integration test: ') if sys.stdin.isatty() else sys.stdin.readline().rstrip(chr(10))
status=json.loads(subprocess.check_output(['/usr/bin/hics-systemctl','status','region']))
assert 'LANG=ru_RU.UTF-8' in status.get('current',[]),'Privileged test requires ru_RU.UTF-8 as the existing system locale'
with tempfile.TemporaryDirectory(prefix='hics-region-e2e-') as tmp:
 base=Path(tmp);endpoint=base/'control.sock';mode=base/'mode';mode.write_text('')
 server=base/'server.py'
 server.write_text('''import os,sys,socket,json,subprocess,signal
from pathlib import Path
root=Path(sys.argv[1]);backups={p:p.read_bytes() for p in [Path('/etc/locale.conf'),Path('/etc/locale.gen')]};stopping=False;applied={}
def stop(*_):
 global stopping
 stopping=True
signal.signal(signal.SIGTERM,stop)
try:
 with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
  server.bind(str(root/'control.sock'));os.chmod(root/'control.sock',0o600);os.chown(root/'control.sock',int(sys.argv[2]),-1);server.listen(4);server.settimeout(.5)
  while not stopping:
   try:client,_=server.accept()
   except TimeoutError:continue
   with client:
    raw=b''
    while b'\\n' not in raw:
     part=client.recv(65536)
     if not part:break
     raw+=part
    request=json.loads(raw)
    if request.get('stop'):stopping=True;continue
    options=request['payload']
    if (root/'mode').read_text()=='denied':result={'error':'Authorization was cancelled or denied','code':'denied'}
    elif options.get('locale')!='ru_RU.UTF-8':result={'error':'Test bridge accepts only the original locale','code':'invalid'}
    else:
     run=subprocess.run(['/usr/bin/hics-systemctl','apply','region','locale'],input=json.dumps(options),capture_output=True,text=True,timeout=150)
     result=json.loads(run.stdout)
     if not result.get('error'):applied={p:p.read_bytes() for p in backups}
    client.sendall((json.dumps(result)+'\\n').encode())
finally:
 for path,contents in backups.items():
  if path in applied and path.read_bytes()==applied[path] and applied[path]!=contents:path.write_bytes(contents)
''')
 proxy=base/'proxy.py';proxy.write_text('''#!/usr/bin/python3
import sys,os,socket,json
if len(sys.argv)>2 and sys.argv[1]=='apply' and sys.argv[2]!='region':
 print(json.dumps({'error':'Hardware writes are disabled in the onboarding integration test','code':'denied'}));sys.exit(1)
if sys.argv[1:]!=['apply','region','locale']:os.execv('/usr/bin/hics-systemctl',['hics-systemctl',*sys.argv[1:]])
with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
 client.connect(os.environ['HICS_TEST_REGION_SOCKET']);client.sendall((json.dumps({'payload':json.load(sys.stdin)})+'\\n').encode());raw=b''
 while b'\\n' not in raw:
  part=client.recv(65536)
  if not part:break
  raw+=part
 result=json.loads(raw);print(json.dumps(result));sys.exit(1 if result.get('error') else 0)
''');proxy.chmod(0o700)
 with (base/'server.log').open('w') as log:
  worker=subprocess.Popen(['sudo','-S','python3',str(server),str(base),str(os.getuid())],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True)
  worker.stdin.write(password+chr(10));worker.stdin.flush();password=''
  try:
   for _ in range(100):
    if endpoint.exists():break
    if worker.poll() is not None:raise RuntimeError((base/'server.log').read_text())
    time.sleep(.1)
   os.environ.update(HICS_TEST_REGION_PROXY=str(proxy),HICS_TEST_REGION_SOCKET=str(endpoint),HICS_TEST_REGION_MODE=str(mode))
   spec=importlib.util.spec_from_file_location('record',ROOT/'distribution/record_tour.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.record(sys.argv[sys.argv.index('--language')+1] if '--language' in sys.argv else 'ru_RU',['onboarding','interactions'])
  finally:
   if endpoint.exists():
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:client.connect(str(endpoint));client.sendall(b'{"stop":true}\n')
   worker.wait(timeout=15)
