#!/usr/bin/env python3
"""Exercise persistent previews and actual Lua rules in an isolated compositor."""
import json,os,signal,socket,subprocess,tempfile,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ASSETS=ROOT/'shell/assets'
with tempfile.TemporaryDirectory(prefix='hics-configuration-test-') as directory:
 base=Path(directory);cfg=base/'config/hics';cfg.mkdir(parents=True)
 (cfg/'shell.json').write_text('{"appearance":{"scale":1}}')
 (cfg/'hypr-user.lua').write_text('-- private rules\n')
 lua=base/'hyprland.lua';lua.write_text('package.path='+json.dumps(str(ASSETS/'hyprland/config/?.lua')+';')+'..package.path\n'+
  'package.preload["scheme.current"]=function() return require("scheme.default") end\n'+
  'hl.monitor({output="",mode="preferred",position="auto",scale=1})\n'+
  'dofile('+json.dumps(str(ASSETS/'hyprland/config/hyprland/animations.lua'))+')\n'+
  'dofile('+json.dumps(str(ASSETS/'hyprland/config/hyprland/gestures.lua'))+')\n'+
  'dofile('+json.dumps(str(ASSETS/'hyprland/layouts.lua'))+')\n'+
  'dofile('+json.dumps(str(cfg/'hypr-user.lua'))+')\n')
 env=dict(os.environ,AQ_BACKEND='wayland,headless',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),HICS_CONFIG_NO_SYSTEMD='1',HICS_DISPLAY_NO_SYSTEMD='1');env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=worker=app=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  for _ in range(100):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
  def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],env=env,text=True,timeout=10).strip()
  def call(helper,op,value=None):
   r=subprocess.run([sys.executable,str(ASSETS/helper),op],env=env,input=json.dumps(value or {}),capture_output=True,text=True,timeout=45);d=json.loads(r.stdout);assert r.returncode==0,(op,d);return d
  def start():
   log=(base/'worker.log').open('a');return subprocess.Popen([sys.executable,str(ASSETS/'configuration_manager.py'),'watch'],env=env,stdout=log,stderr=subprocess.STDOUT)
  def wait(check,timeout=7):
   end=time.monotonic()+timeout
   while time.monotonic()<end:
    value=check()
    if value:return value
    time.sleep(.1)
   raise AssertionError('Timed out')
  worker=start();state=call('configuration_manager.py','status');assert state['history']
  call('configuration_manager.py','save-profile',{'name':'Original'});profile=call('configuration_manager.py','status')['profiles'][0]
  (cfg/'shell.json').write_text('{"appearance":{"scale":1.25}}')
  wait(lambda:len(call('configuration_manager.py','status')['history'])>=2)
  state=call('configuration_manager.py','preview-profile',{'id':profile['id'],'sections':['shell.json']});assert json.loads((cfg/'shell.json').read_text())['appearance']['scale']==1
  # Crash the guard, then verify the durable journal restores the previous config.
  worker.kill();worker.wait();worker=start();wait(lambda:not call('configuration_manager.py','status')['pending']);assert json.loads((cfg/'shell.json').read_text())['appearance']['scale']==1.25
  print('PASS: automatic capture, real preview and guard crash recovery',flush=True)
  state=call('configuration_manager.py','preview-profile',{'id':profile['id'],'sections':['shell.json']});call('configuration_manager.py','confirm',{'token':state['pending']['token']});assert json.loads((cfg/'shell.json').read_text())['appearance']['scale']==1
  state=call('configuration_manager.py','preview-profile',{'id':profile['id'],'sections':['shell.json']})
  journal=base/'state/hics/configuration-preview.json';j=json.loads(journal.read_text());j['deadlineMonotonic']=time.monotonic()-.1;journal.write_text(json.dumps(j));wait(lambda:not call('configuration_manager.py','status')['pending'])
  print('PASS: explicit confirmation and timer rollback',flush=True)
  # A trickling local client must not keep the independent rollback guard
  # inside recv() indefinitely. Socket timeout must bound the whole request.
  import threading
  state=call('configuration_manager.py','preview-profile',{'id':profile['id'],'sections':['shell.json']})
  endpoint=Path(state['statePath']).parent/'control.sock'
  slow=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);slow.connect(str(endpoint))
  stopping=threading.Event()
  def trickle():
   while not stopping.wait(.1):
    try:slow.sendall(b' ')
    except OSError:return
  sender=threading.Thread(target=trickle);sender.start()
  try:
   time.sleep(.15)
   j=json.loads(journal.read_text());j['deadlineMonotonic']=time.monotonic()+.1;journal.write_text(json.dumps(j))
   wait(lambda:not journal.exists(),timeout=2.7)
   print('PASS: trickling IPC client cannot postpone the independent rollback deadline',flush=True)
  finally:
   stopping.set();slow.close();sender.join(timeout=1)
  (cfg/'shell.json').write_text('{broken JSON')
  wait(lambda:(cfg/'shell.json').read_text()!='{broken JSON')
  assert json.loads((cfg/'shell.json').read_text())['appearance']['scale']==1
  assert list((base/'state/hics/configuration-recovery').glob('*.invalid'))
  print('PASS: malformed JSON is quarantined and restored without crashing the guard',flush=True)
  shell_process=subprocess.Popen(['sleep','60'])
  try:
   (cfg/'shell.json').write_text('{"appearance":{"scale":1.2}}')
   endpoint=Path(call('configuration_manager.py','status')['statePath']).parent/'control.sock'
   with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client_socket:
    client_socket.settimeout(8);client_socket.connect(str(endpoint));client_socket.sendall((json.dumps({'operation':'preview-profile','value':{'id':profile['id'],'sections':['shell.json']},'shellPid':shell_process.pid})+'\n').encode())
    response=b''
    while b'\n' not in response:
     part=client_socket.recv(65536)
     assert part,'Guard disconnected before replying'
     response+=part
    assert not json.loads(response).get('error'),response
   shell_process.terminate();shell_process.wait()
   wait(lambda:not call('configuration_manager.py','status')['pending'])
   assert json.loads((cfg/'shell.json').read_text())['appearance']['scale']==1.2
   print('PASS: shell process termination immediately restores an unconfirmed preview',flush=True)
  finally:
   if shell_process.poll() is None:shell_process.terminate();shell_process.wait()
  # Rule must be accepted by the real compositor and affect a newly mapped client.
  call('desktop_rules.py','save-rule',{'application':'hics.rules.test','name':'Fixture','floating':True,'width':680,'height':420,'opacity':.85})
  call('desktop_rules.py','save-rule',{'application':'hics.rules.test','name':'Window kind','initialTitle':'Private rules fixture','noShadow':True})
  app=subprocess.Popen(['kitty','--class','hics.rules.test','--title','Private rules fixture','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  client=wait(lambda:next((w for w in json.loads(ctl('-j','clients')) if w.get('class')=='hics.rules.test'),None))
  assert client['floating'] and client['size']==[680,420],client
  devices=json.loads(ctl('-j','devices'))
  if devices.get('mice'):
   name=devices['mice'][0]['name'];call('desktop_rules.py','save-device',{'name':name,'values':{'sensitivity':.25,'natural_scroll':True}})
  call('desktop_rules.py','save-device',{'name':'hics-fixture-tablet','values':{'output':'current','transform':0,'relative_input':False,'active_area_size':[152,95],'active_area_position':[0,0],'region_size':[800,600],'region_position':[0,0]}})
  assert not ctl('configerrors'),ctl('configerrors')
  print('PASS: actual application geometry and per-device Lua rules',flush=True)
 finally:
  for process in (worker,app,compositor):
   if process and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=8)
    except subprocess.TimeoutExpired:process.kill();process.wait()
