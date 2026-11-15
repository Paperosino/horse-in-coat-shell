"""Verify real compositor startup and cookie authentication in a separate session."""
import os,sys,tempfile,shutil,subprocess,time,json,signal
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'shell/assets'))
from integration_support import require_wayland_session
require_wayland_session()
import session_bootstrap,xwayland_auth
with tempfile.TemporaryDirectory(prefix='hics-auth-check-') as temp:
 b=Path(temp);data=b/'data';data.mkdir()
 shutil.copytree(root/'shell/assets/hyprland',data/'shell/assets/hyprland')
 shutil.copy2(root/'shell/assets/xwayland_auth.py',data/'shell/assets/xwayland_auth.py')
 shutil.copytree(root/'distribution/xwayland',data/'xwayland')
 (data/'defaults').symlink_to(root/'distribution/defaults')
 env,config=session_bootstrap.prepare(data,b/'config')
 env=dict(os.environ,**env,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(b/'config'),XDG_STATE_HOME=str(b/'state'),XDG_DATA_HOME=str(b/'xdg-data'),XDG_CACHE_HOME=str(b/'cache'),HYPRSTACK_NESTED='1')
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 env.update(xwayland_auth.prepare(data))
 with (b/'log').open('w') as log:
  p=subprocess.Popen(['Hyprland','--config',str(config)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  instance=None
  for _ in range(100):
   items=json.loads(subprocess.check_output(['hyprctl','instances','-j']))
   instance=next((i for i in items if i['pid']==p.pid),None)
   if instance:break
   if p.poll() is not None:raise RuntimeError((b/'log').read_text()[-5000:])
   time.sleep(.1)
  assert instance
  # Find this compositor's Xwayland child, without printing cookies.
  server=None
  for _ in range(100):
   for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
     argv=(proc/'cmdline').read_bytes().split(b'\0')
     if argv[0]==b'/usr/bin/Xwayland' and os.fsencode(env['XAUTHORITY']) in argv:server=argv;break
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
   if server:break
   time.sleep(.1)
  assert server,'Authenticated XWayland did not start: '+(b/'log').read_text()[-5000:]
  env['DISPLAY']=server[1].decode()
  probe='import ctypes; x=ctypes.CDLL("libX11.so.6"); x.XOpenDisplay.restype=ctypes.c_void_p; d=x.XOpenDisplay(None); assert d, "Cannot open display"'
  for _ in range(50):
   result=subprocess.run([sys.executable,'-c',probe],env=env,capture_output=True)
   if result.returncode==0:break
   time.sleep(.1)
  assert result.returncode==0,result.stderr.decode()
  subprocess.run([sys.executable,str(data/'shell/assets/xwayland_auth.py')],env=env,check=True,timeout=5)
  print('PASS: real nested Hyprland 0.56.2 started XWayland with -auth, client authenticated with session cookie, root ACL applied; private Xauthority mode',oct(Path(env['XAUTHORITY']).stat().st_mode & 0o777))
 finally:
  os.killpg(p.pid,signal.SIGTERM)
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  shutil.rmtree(Path(env['XAUTHORITY']).parent)
