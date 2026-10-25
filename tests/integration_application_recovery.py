#!/usr/bin/env python3
"""Real compositor ping recovery; only SIGSTOP/SIGKILL our own fixture client."""
import json,os,shutil,signal,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session,resize_nested_compositor
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-app-recovery-') as temporary:
 base=Path(temporary);(base/'native').mkdir()
 for name in ['hics-bars.so','libhics-render-dispatch.so']:shutil.copy2(ROOT/'build'/name,base/'native'/name)
 config=base/'hyprland.lua';config.write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\nhl.config({misc={enable_anr_dialog=true,anr_missed_pings=1}})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 app=None;compositor=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(config)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(80):
   instance=next((item for item in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if item['pid']==compositor.pid),None)
   if instance:break
   assert compositor.poll() is None,(base/'compositor.log').read_text()[-4000:]
   time.sleep(.1)
  assert instance,'nested compositor did not start';resize_nested_compositor(compositor.pid)
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
  def ctl(*args):
   value=subprocess.run(['hyprctl','-i',instance['instance'],*args],env=env,text=True,capture_output=True,timeout=10)
   assert value.returncode==0,value.stdout+value.stderr
   return value.stdout.strip()
  ctl('plugin','load',str(base/'native/hics-bars.so'))
  app=subprocess.Popen(['kitty','--class','org.hics.RecoveryFixture','--title','Recovery fixture','-o','confirm_os_window_close=0','sleep','120'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  def wait(check,message):
   deadline=time.monotonic()+15
   while time.monotonic()<deadline:
    if check():return
    assert compositor.poll() is None,(base/'compositor.log').read_text()[-4000:]
    time.sleep(.1)
   raise AssertionError(message)
  def own():return next((window for window in json.loads(ctl('clients','-j')) if window['pid']==app.pid),None)
  wait(lambda:own() is not None,'fixture window did not appear');window=own();address=window['address']
  stable=ctl('repl','return string.format("%x",hl.get_window('+json.dumps('address:'+address)+').stable_id)')
  def action(identity):return ctl('repl','return hl.plugin.hyprbars.animate_window('+json.dumps(address)+','+json.dumps(identity)+',"terminate-unresponsive")')
  assert action(stable)=='false','healthy application was eligible for termination'
  def hanging():return json.loads(ctl('repl','return hl.plugin.hyprbars.unresponsive()'))
  app.send_signal(signal.SIGSTOP);wait(lambda:any(item['address']==address for item in hanging()),'missed protocol pings were not detected')
  assert action('ffffffffffffffff')=='false','a stale window identity was accepted'
  app.send_signal(signal.SIGCONT);wait(lambda:not any(item['address']==address for item in hanging()),'application did not recover after Wait')
  assert app.poll() is None,'recovered application was killed'
  app.send_signal(signal.SIGSTOP);wait(lambda:any(item['address']==address for item in hanging()),'second hang was not detected')
  assert action(stable)=='true','explicit force quit was not accepted'
  app.wait(timeout=5);assert app.returncode==-signal.SIGKILL,app.returncode
  print('PASS: compositor ping detection, recovery after Wait, stale identity rejection, explicit force quit')
 finally:
  if app and app.poll() is None:
   app.send_signal(signal.SIGCONT);app.terminate()
   try:app.wait(timeout=5)
   except subprocess.TimeoutExpired:app.kill();app.wait()
  if compositor:
   compositor.terminate()
   try:compositor.wait(timeout=8)
   except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
