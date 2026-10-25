#!/usr/bin/env python3
"""Load a local portal in real WebKit, verify cookies are temporary, reject local URLs."""
import http.server,json,os,signal,subprocess,tempfile,threading,time
from pathlib import Path
from integration_support import require_wayland_session,resize_nested_compositor
require_wayland_session();ROOT=Path(__file__).resolve().parents[1]
requests=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  requests.append((self.path,self.headers.get('Cookie')))
  body=b'''<html><body><h1>hics portal fixture</h1><script>document.cookie='hics_test=1';fetch('/checked');</script></body></html>''' if self.path=='/' else b'OK'
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(body)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory(prefix='hics-portal-') as directory:
 base=Path(directory);(base/'compositor.lua').write_text('hl.monitor({output="WAYLAND-1",mode="800x700@60",position="0x0",scale=1})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_CACHE_HOME=str(base/'cache'),XDG_DATA_HOME=str(base/'data'),GDK_BACKEND='wayland',WEBKIT_DISABLE_DMABUF_RENDERER='1');env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);env.pop('LD_LIBRARY_PATH',None)
 compositor=None;browser=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'compositor.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance;resize_nested_compositor(compositor.pid,800,700);env['WAYLAND_DISPLAY']=instance['wl_socket']
  executable=ROOT/'build/hics-portal'
  for invalid in ('file:///etc/passwd','javascript:alert(1)'):
   assert subprocess.run([str(executable),invalid],env=env,capture_output=True).returncode==2
  for iteration in range(2):
   before=len(requests)
   with (base/'browser.log').open('w') as log:browser=subprocess.Popen([str(executable),'http://127.0.0.1:'+str(server.server_port)+'/'],env=env,stdout=log,stderr=subprocess.STDOUT)
   end=time.monotonic()+20
   while not any(p=='/checked' for p,c in requests[before:]) and time.monotonic()<end:
    assert browser.poll() is None,(base/'browser.log').read_text();time.sleep(.1)
   rows=requests[before:];assert any(p=='/checked' and c=='hics_test=1' for p,c in rows),((base/'browser.log').read_text(),rows)
   assert next(c for p,c in rows if p=='/') is None,('Cookies leaked across portal sessions',rows)
   browser.terminate();browser.wait(timeout=5);browser=None
  print('PASS: native portal renders, supports in-session cookies, discards cookies on close, rejects file/JS URLs')
 finally:
  for process in (browser,compositor):
   if process and process.poll() is None:process.terminate();process.wait(timeout=5)
  server.shutdown();server.server_close()
