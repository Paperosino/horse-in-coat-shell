#!/usr/bin/env python3
"""Exercise real Lua callbacks and application restore in a nested compositor."""
import json, os, shutil, shlex, subprocess, tempfile, time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
helper=ROOT/'build/lib/hics-workspace'
with tempfile.TemporaryDirectory(prefix='hics-workspace-integration-') as temp:
 base=Path(temp);config=base/'config';(config/'hics').mkdir(parents=True);(base/'data/applications').mkdir(parents=True);(base/'native').mkdir()
 for name in ['hics-bars.so','libspatialoverview.so']:
  source=next(p for p in [ROOT/'build'/name,ROOT/'build/third_party/phantomat'/name,Path('/usr/share/hics/native')/name] if p.is_file());shutil.copy2(source,base/'native'/name)
 fixture=ROOT/'tests/fixtures'
 for flag,name in [('client-header','virtual-keyboard.h'),('private-code','virtual-keyboard.c')]:
  subprocess.run(['wayland-scanner',flag,str(fixture/'virtual-keyboard.xml'),str(base/name)],check=True)
 flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client','xkbcommon'],text=True))
 subprocess.run(['cc',str(fixture/'virtual-keyboard.c'),str(base/'virtual-keyboard.c'),'-I',str(base),*flags,'-o',str(base/'keyboard')],check=True)
 marker=base/'callback'
 lua=base/'test.lua'
 lua.write_text('package.path='+json.dumps(str(ROOT/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\n'+
  'package.preload["scheme.current"]=function() return require("scheme.default") end\n'+
  'dofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/animations.lua'))+')\n'+
  'hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n'+
  'dofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/gestures.lua'))+')\n'+
  'hics_shortcuts=dofile('+json.dumps(str(ROOT/'shell/assets/hyprland/shortcuts.lua'))+').install()\n'+
  'hl.bind("SUPER + F8",function() local f=assert(io.open('+json.dumps(str(marker))+',"w"));f:write("callback");f:close() end,{description="Test: Preserve callback"})\n'+
  'dofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
 (config/'hics/layouts.json').write_text(json.dumps({'mode':'stacking'}))
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(config),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),HYPRSTACK_DATA_DIR=str(base),XDG_CURRENT_DESKTOP='Hyprland',HICS_WORKSPACE_HELPER=str(helper));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=None;terminal=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(100):
   instances=json.loads(subprocess.check_output(['hyprctl','instances','-j']));instance=next((i for i in instances if i['pid']==compositor.pid),None)
   if instance:break
   if compositor.poll() is not None:raise RuntimeError((base/'compositor.log').read_text())
   time.sleep(.1)
  assert instance,'No nested compositor';env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance']);time.sleep(1)
  def ctl(*args):
   result=subprocess.run(['hyprctl','-i',instance['instance'],*args],env=env,capture_output=True,text=True,timeout=10)
   assert result.returncode==0,result.stderr;return result.stdout.strip()
  assert not ctl('configerrors'),ctl('configerrors')
  catalogue=Path(env['XDG_RUNTIME_DIR'])/('hics-shortcuts-'+instance['instance']+'.json')
  assert catalogue.exists(),'Shortcut catalogue not written'
  actions=json.loads(catalogue.read_text())['actions'];action=next(a for a in actions if a['description']=='Test: Preserve callback')
  action['keys']=['SUPER + F9']
  # Write the same validated settings format used by the native editor.
  (config/'hics/workspace.json').write_text(json.dumps({'shortcuts':{'overrides':{action['id']:action}},'session':{'windowTimeout':5,'launchDelay':0}}))
  ctl('reload');time.sleep(.5);assert not ctl('configerrors'),ctl('configerrors')
  binds=json.loads(ctl('-j','binds'));match=[b for b in binds if b['description']=='Test: Preserve callback'];assert len(match)==1 and match[0]['key']=='F9',match
  subprocess.run([str(base/'keyboard'),'66'],env=env,check=True);time.sleep(.2);assert not marker.exists(),'Old key still active'
  subprocess.run([str(base/'keyboard'),'67'],env=env,check=True);time.sleep(.2);assert marker.read_text()=='callback'
  print('PASS: remapped shortcut preserves its real Lua callback after reload',flush=True)
  desktop=base/'data/applications/org.hics.WorkspaceFixture.desktop'
  desktop.write_text('[Desktop Entry]\nType=Application\nName=Session fixture\nStartupWMClass=org.hics.WorkspaceFixture\nExec=kitty --class org.hics.WorkspaceFixture --title "Session fixture" -o confirm_os_window_close=0 sleep 60\n')
  terminal=subprocess.Popen(['kitty','--class','org.hics.WorkspaceFixture','--title','Session fixture','-o','confirm_os_window_close=0','sleep','60'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  def windows():return [c for c in json.loads(ctl('-j','clients')) if c['class']=='org.hics.WorkspaceFixture']
  for _ in range(50):
   if windows():break
   time.sleep(.1)
  assert windows(),'Fixture did not map';address=windows()[0]['address']
  ctl('eval','local w=hl.get_window("address:'+address+'");hl.dispatch(hl.dsp.window.resize({window=w,x=600,y=400,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=180,y=160,relative=false}))');time.sleep(.3)
  subprocess.run([str(helper),'capture','Integration'],env=env,check=True,timeout=15)
  files=list((base/'state/hics/workspace/sessions').glob('*.json'));assert len(files)==1
  snapshot=json.loads(files[0].read_text());assert snapshot['windows'][0]['enabled'],snapshot
  before=windows()[0];ctl('eval','hl.dispatch(hl.dsp.window.close({window=hl.get_window("address:'+address+'" )}))');terminal.wait(timeout=5)
  subprocess.run([str(helper),'restore',files[0].stem],env=env,check=True,timeout=20)
  after=windows();assert len(after)==1,after
  assert all(abs(a-b)<=5 for a,b in zip(before['size'],after[0]['size'])),(before,after)
  assert all(abs(a-b)<=5 for a,b in zip(before['at'],after[0]['at'])),(before,after)
  subprocess.run([str(helper),'restore',files[0].stem],env=env,check=True,timeout=20);assert len(windows())==1
  print('PASS: session restore relaunches and places a real application; repeat restore avoids duplicates',flush=True)
  subprocess.run([str(helper),'project','Integration project','3','stacking'],env=env,check=True,timeout=15)
  project=next(p for p in files[0].parent.glob('*.json') if json.loads(p.read_text()).get('project',{}).get('enabled'))
  definition=json.loads(project.read_text());assert definition['project']['workspace']==3
  assert len(definition['windows'])==1 and definition['windows'][0]['workspace']==3
  subprocess.run([str(helper),'restore',project.stem],env=env,check=True,timeout=20)
  assert len(windows())==1 and windows()[0]['workspace']['id']==3,windows()
  print('PASS: workspace project capture, existing-window reuse and placement on named target workspace',flush=True)

  for window in windows():ctl('eval','hl.dispatch(hl.dsp.window.close({window=hl.get_window("address:'+window['address']+'" )}))')
 finally:
  if terminal and terminal.poll() is None:terminal.terminate()
  if compositor and compositor.poll() is None:
   compositor.terminate()
   try:compositor.wait(timeout=5)
   except subprocess.TimeoutExpired:compositor.kill();compositor.wait()
  if compositor and compositor.returncode not in (0,-15):raise RuntimeError((base/'compositor.log').read_text()[-3000:])
