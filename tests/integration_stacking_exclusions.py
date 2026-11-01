import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session,resize_nested_compositor,snapshot_qml_runtime
require_wayland_session()
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-frame-probe-') as d:
 b=Path(d); (b/'config/hics').mkdir(parents=True);(b/'data/native').mkdir(parents=True)
 (b/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
 (b/'config/hics/dock.json').write_text('{"enabled":true,"position":"bottom"}')
 for name in ('hics-bars.so','hics-motion.so','libhics-render-dispatch.so','libspatialoverview.so'):
  src=Path(os.environ['HICS_TEST_NATIVE_DIR'])/name if os.environ.get('HICS_TEST_NATIVE_DIR') else next((p for p in [R/'build'/name,R/'build/third_party/phantomat'/name,Path('/usr/share/hics/native')/name] if p.exists()));shutil.copy2(src,b/'data/native'/name)
 shell=b/'shell';shutil.copytree(R/'shell',shell,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 config=b/'test.lua';config.write_text('package.path='+json.dumps(str(R/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\nhl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n'+''.join('dofile('+json.dumps(str(p))+')\n' for p in (R/'shell/assets/hyprland/config/hyprland/animations.lua',R/'shell/assets/hyprland/config/hyprland/gestures.lua',R/'shell/assets/hyprland/layouts.lua')))
 buscfg=b/'bus.conf';buscfg.write_text('<busconfig><type>session</type><listen>unix:path='+str(b/'bus')+'</listen><auth>EXTERNAL</auth><policy context="default"><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
 env=dict(os.environ,HOME=str(b/'home'),AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(b/'config'),XDG_STATE_HOME=str(b/'state'),XDG_DATA_HOME=str(b/'user-data'),XDG_CACHE_HOME=str(b/'cache'),HYPRSTACK_DATA_DIR=str(b/'data'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(b/'absent-system'),HICS_NO_ONBOARDING='1',PIPEWIRE_REMOTE='hics-fixture-absent',PULSE_SERVER='unix:'+str(b/'absent-pulse'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);(b/'home').mkdir()
 env.update(snapshot_qml_runtime(R,b) if not os.environ.get('HICS_TEST_INSTALLED_RUNTIME') else {'QML_IMPORT_PATH':'/usr/share/hics/qml','QML2_IMPORT_PATH':'/usr/share/hics/qml','LD_LIBRARY_PATH':'/usr/share/hics/qs/lib'});process=[]
 try:
  bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(buscfg)],stdout=subprocess.PIPE,text=True);process.append(bus);env['DBUS_SESSION_BUS_ADDRESS']=bus.stdout.readline().strip()
  with open(b/'compositor.log','w') as out:c=subprocess.Popen(['Hyprland','--config',str(config)],env=env,stdout=out,stderr=subprocess.STDOUT);process.append(c)
  for i in range(100):
   ins=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==c.pid),None)
   if ins:break
   time.sleep(.1)
  assert ins;resize_nested_compositor(c.pid);env.update(WAYLAND_DISPLAY=ins['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=ins['instance'],QT_QPA_PLATFORM='wayland')
  with open(b/'shell.log','w') as out:qs=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(shell)],env=env,stdout=out,stderr=subprocess.STDOUT);process.append(qs)
  def ctl(*args):return subprocess.check_output(['hyprctl','-i',ins['instance'],*args],env=env,text=True).strip()
  def monitor():return json.loads(ctl('-j','monitors'))[0]['reserved']
  def wait(check,description):
   deadline=time.monotonic()+12
   while time.monotonic()<deadline:
    assert qs.poll() is None,(b/'shell.log').read_text()[-3000:]
    if check():return
    time.sleep(.1)
   raise AssertionError(description+'; reserved='+str(monitor())+'; layers='+ctl('-j','layers'))
  def edges():
   data=json.loads(ctl('-j','layers'))
   return [layer for output in data.values() for layers in output['levels'].values() for layer in layers if layer['namespace']=='hyprstack-border-exclusion']
  wait(lambda:monitor()[1]>0 and monitor()[3]>0,'panel and dock did not reserve space')
  wait(lambda:monitor()[0]==0 and monitor()[2]==0,'stacking kept a side frame')
  assert all(layer['x'] not in (0,1279) for layer in edges()),edges()
  print('PASS: stacking starts without side frame surfaces',flush=True)
  for mode in ('scrolling','stacking','scrolling','stacking'):
   ctl('repl','hyprstack_layouts.set_mode('+json.dumps(mode)+')')
   if mode=='scrolling':wait(lambda:monitor()[0]>=10 and monitor()[2]>=10,'scrolling frame disappeared')
   else:
    wait(lambda:monitor()[0]==0 and monitor()[2]==0,'switching to stacking left a side reservation')
    wait(lambda:all(layer['x'] not in (0,1279) for layer in edges()),'zero-reservation side surface remained mapped')
  print('PASS: repeated layout changes unmap unused frame surfaces',flush=True)
  dock=b/'config/hics/dock.json';temp=dock.with_suffix('.tmp');temp.write_text('{"enabled":true,"position":"left"}');temp.replace(dock)
  wait(lambda:monitor()[0]>=40 and monitor()[2]==0,'left dock reservation not respected')
  app=subprocess.Popen(['kitty','--class','org.hics.FrameFixture','-o','confirm_os_window_close=0','sleep','60'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);process.append(app)
  def window():return next((w for w in json.loads(ctl('-j','clients')) if w['pid']==app.pid),None)
  wait(window,'test window did not open')
  ctl('repl','hyprstack_layouts.action("maximize-set",'+json.dumps(window()['address'])+')')
  wait(lambda:window()['at'][0]==monitor()[0] and window()['at'][0]+window()['size'][0]==1280,'maximized window did not fit left dock and right edge')
  temp.write_text('{"enabled":true,"position":"bottom"}');temp.replace(dock)
  wait(lambda:monitor()[0]==0,'old dock reservation remained')
  wait(lambda:window()['at'][0]==0 and window()['size'][0]==1280,'maximized window did not expand to screen edges')
  print('PASS: real dock reservations remain respected; maximized window fills free width',flush=True)
 finally:
  for p in reversed(process):
   if p.poll() is None:
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
