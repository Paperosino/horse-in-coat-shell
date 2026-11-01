import json,os,shutil,subprocess,tempfile,time,signal
from pathlib import Path
from integration_support import require_wayland_session,resize_nested_compositor,snapshot_qml_runtime
require_wayland_session()
R=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-shell-force-') as d:
 b=Path(d); (b/'config/hics').mkdir(parents=True);(b/'data/native').mkdir(parents=True)
 (b/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
 (b/'config/hics/dock.json').write_text('{"enabled":true,"position":"bottom"}')
 for name in ('hics-bars.so','hics-motion.so','libhics-render-dispatch.so','libspatialoverview.so'):
  src=Path(os.environ['HICS_TEST_NATIVE_DIR'])/name if os.environ.get('HICS_TEST_NATIVE_DIR') else next((p for p in [R/'build'/name,R/'build/third_party/phantomat'/name,Path('/usr/share/hics/native')/name] if p.exists()));shutil.copy2(src,b/'data/native'/name)
 shell=b/'shell';shutil.copytree(R/'shell',shell,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 source=shell/'shell.qml'
 qml=source.read_text().replace('import qs.services\n','import qs.services\nimport qs.modules.nexus\nimport Quickshell.Hyprland\n',1)
 qml=qml.replace('    Component.onCompleted: AnimationClock.activate()','''
    function findItems(item, name, result) {if (!item) return; if(item.objectName===name)result.push(item); for(const child of item.children??[])findItems(child,name,result);}
    IpcHandler {target:"forceQuitTest"
      function open():void {WindowFactory.openPage("appearance");}
      function menu():bool {const dock=ShellState.componentsFor(Quickshell.screens[0])?.panels?.dock;if(!dock)return false;let items=[];root.findItems(dock,"dockTaskButton",items);const task=items.find(t=>t.windows.some(w=>Number(w?.lastIpcObject?.pid)===Quickshell.processId));if(!task)return false;task.showMenu();return true;}
      function menuState():string {const dock=ShellState.componentsFor(Quickshell.screens[0])?.panels?.dock;let items=[];root.findItems(dock,"dockForceQuit",items);return JSON.stringify({count:items.length,visible:items.some(i=>i.visible)});}
      function force():bool {const w=Hyprland.toplevels.values.find(t=>Number(t?.lastIpcObject?.pid)===Quickshell.processId);if(!w)return false;Hypr.windowAction("force-quit",w);return true;}
    }
    Component.onCompleted: AnimationClock.activate()''')
 source.write_text(qml)
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
  def ipc(*args):return subprocess.check_output(['/usr/share/hics/qs/bin/hics-qs','ipc','-p',str(shell),'call','forceQuitTest',*args],env=env,text=True,timeout=5).strip()
  def windows():return json.loads(ctl('-j','clients'))
  def own():return next((w for w in windows() if w['pid']==qs.pid and w['class']=='org.hics.Shell'),None)
  def open_settings():
   ipc('open');wait(own,'settings did not open');return own()
  wait(lambda:subprocess.run(['/usr/share/hics/qs/bin/hics-qs','ipc','-p',str(shell),'call','sessionHealth','ready'],env=env,capture_output=True,text=True).stdout.strip()=='true','shell did not start')
  w=open_settings()
  wait(lambda:ipc('menu')=='true','settings did not appear in dock')
  def menu_state():
   value=ipc('menuState');return json.loads(value)
  wait(lambda:menu_state()['count']>0,'window menu did not appear')
  assert not menu_state()['visible'],menu_state()
  print('PASS: dock does not offer force quit for its own settings window',flush=True)
  address=w['address'];stable=w['stableId']
  ctl('repl','hyprstack_layouts.action("force-quit",'+json.dumps(address)+','+json.dumps(stable)+')')
  wait(lambda:not any(x['address']==address for x in windows()),'settings did not close')
  assert qs.poll() is None,'shell process died with its settings window'
  print('PASS: compositor force-quit request closes only the shell window',flush=True)
  w=open_settings();address=w['address']
  assert ipc('force')=='true'
  wait(lambda:not any(x['address']==address for x in windows()),'QML force request did not close settings')
  assert qs.poll() is None
  print('PASS: shell-side force request closes only its own window',flush=True)
  w=open_settings();address=w['address'];stable=w['stableId']
  qs.send_signal(signal.SIGSTOP)
  try:
   deadline=time.monotonic()+15
   while time.monotonic()<deadline:
    rows=json.loads(ctl('repl','return hl.plugin.hyprbars.unresponsive()'))
    if any(row['address']==address for row in rows):break
    time.sleep(.1)
   else:raise AssertionError('stopped shell was not detected as unresponsive')
   result=ctl('repl','return hl.plugin.hyprbars.animate_window('+json.dumps(address)+','+json.dumps(stable)+',"terminate-unresponsive")')
   assert result=='false' and qs.poll() is None,('unresponsive recovery accepted shell kill',result)
  finally:qs.send_signal(signal.SIGCONT)
  print('PASS: unresponsive recovery refuses to kill the shell process',flush=True)
  app=subprocess.Popen(['kitty','--class','org.hics.IndependentFixture','-o','confirm_os_window_close=0','sleep','60'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);process.append(app)
  def client():return next((w for w in windows() if w['pid']==app.pid),None)
  wait(client,'independent app did not open');w=client()
  ctl('repl','hyprstack_layouts.action("force-quit",'+json.dumps(w['address'])+',"ffffffff")');time.sleep(.2);assert app.poll() is None
  ctl('repl','hyprstack_layouts.action("force-quit",'+json.dumps(w['address'])+','+json.dumps(w['stableId'])+')')
  app.wait(timeout=5);assert app.returncode==-signal.SIGKILL and qs.poll() is None
  print('PASS: independent application still force quits and stale identity is rejected',flush=True)
 finally:
  for p in reversed(process):
   if p.poll() is None:
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait()
