#!/usr/bin/env python3
"""Exercise decoration negotiation and manual overrides with actual clients."""
import json, os, shutil, subprocess, tempfile, time, sys
from pathlib import Path
from integration_support import require_wayland_session, resize_nested_compositor
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
helper=ROOT/'build/lib/hics-workspace'
sys.path.insert(0,str(ROOT/'shell/assets'))
from desktop_rules import regenerate
with tempfile.TemporaryDirectory(prefix='hics-decoration-integration-') as temp:
 base=Path(temp);config=base/'config';(config/'hics').mkdir(parents=True);(base/'data/applications').mkdir(parents=True);(base/'native').mkdir()
 for name in ['libhics-render-dispatch.so','hics-bars.so','libspatialoverview.so']:
  source=next(p for p in [ROOT/'build'/name,ROOT/'build/third_party/phantomat'/name,Path('/usr/share/hics/native')/name] if p.is_file());shutil.copy2(source,base/'native'/name)
 lua=base/'test.lua'
 lua.write_text('package.path='+json.dumps(str(ROOT/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\n'+
  'package.preload["scheme.current"]=function() return require("scheme.default") end\n'+
  'dofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/animations.lua'))+')\n'+
  'hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n'+
  'dofile('+json.dumps(str(ROOT/'shell/assets/hyprland/config/hyprland/gestures.lua'))+')\n'+
  'dofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
 scoped=regenerate([
  {'id':'stacking-title','application':'org.hics.Scoped','mode':'stacking','titlebar':'hide','borderSize':3},
  {'id':'scrolling-title','application':'org.hics.Scoped','mode':'scrolling','borderSize':1},
  {'id':'force-title','application':'code-oss','mode':'stacking','titlebar':'show'},
  {'id':'no-decoration','application':'org.hics.NoDecoration','mode':'stacking','decorate':False}
 ],[])
 (config/'hics/rules.lua').write_text(scoped)
 lua.write_text(lua.read_text()+'dofile('+json.dumps(str(config/'hics/rules.lua'))+')\n')
 (config/'hics/layouts.json').write_text(json.dumps({'mode':'stacking'}))
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(config),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),HYPRSTACK_DATA_DIR=str(base),XDG_CURRENT_DESKTOP='Hyprland',HICS_WORKSPACE_HELPER=str(helper));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 compositor=None;terminal=None;fixtures=[]
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(100):
   instances=json.loads(subprocess.check_output(['hyprctl','instances','-j']));instance=next((i for i in instances if i['pid']==compositor.pid),None)
   if instance:break
   if compositor.poll() is not None:raise RuntimeError((base/'compositor.log').read_text())
   time.sleep(.1)
  assert instance,'No nested compositor';resize_nested_compositor(compositor.pid);env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance']);time.sleep(1)
  def ctl(*args):
   result=subprocess.run(['hyprctl','-i',instance['instance'],*args],env=env,capture_output=True,text=True,timeout=10)
   assert result.returncode==0,result.stdout+result.stderr;return result.stdout.strip()
  ctl('plugin','load',str(base/'native/libspatialoverview.so'));time.sleep(1)
  assert not ctl('configerrors'),ctl('configerrors')
  import re,shlex
  protocols=Path('/usr/share/wayland-protocols')
  for short,xml in [('xdg-shell',protocols/'stable/xdg-shell/xdg-shell.xml'),('xdg-decoration',protocols/'unstable/xdg-decoration/xdg-decoration-unstable-v1.xml'),('server-decoration',ROOT/'tests/fixtures/server-decoration.xml')]:
   for flag,suffix in [('client-header','.h'),('private-code','.c')]:
    subprocess.run(['wayland-scanner',flag,str(xml),str(base/(short+suffix))],check=True)
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
  subprocess.run(['cc',str(ROOT/'tests/fixtures/wayland-decoration.c'),str(base/'xdg-shell.c'),str(base/'xdg-decoration.c'),str(base/'server-decoration.c'),'-I',str(base),*flags,'-o',str(base/'wayland-fixture')],check=True)
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','xcb'],text=True))
  subprocess.run(['cc',str(ROOT/'tests/fixtures/x11-csd-drag.c'),*flags,'-o',str(base/'x11-fixture')],check=True)
  def window(process):return next((w for w in json.loads(ctl('clients','-j')) if w['pid']==process.pid),None)
  def launch(command,extras=None):
   process=subprocess.Popen(command,env=dict(env,**(extras or {})),stdin=subprocess.PIPE,stdout=(base/('client-'+str(len(fixtures))+'.log')).open('w'),stderr=subprocess.STDOUT,text=True);fixtures.append(process)
   for _ in range(80):
    if window(process):return process
    assert process.poll() is None,command
    time.sleep(.05)
   raise AssertionError(('No client',command,(base/'compositor.log').read_text()[-3000:]))
  def policy(process):
   w=window(process);assert w,('client disappeared',process.poll())
   return json.loads(ctl('repl','return hl.plugin.hyprbars.decoration_policy('+json.dumps(w['address'])+','+json.dumps(w['stableId'])+')'))
  def expect(process,mode,source=None,header=None):
   for _ in range(70):
    value=policy(process)
    if value['mode']==mode and (source is None or value['source']==source) and (header is None or (value['height']>0)==header):return value
    time.sleep(.04)
   raise AssertionError((mode,source,header,value))
  def command(process,text):process.stdin.write(text+'\n');process.stdin.flush();time.sleep(.12)
  def stop(process):
   process.terminate();process.wait(timeout=4)
  # An arbitrary app ID, including a former exception, must not determine CSD.
  for name in ['org.gnome.Nautilus','Code','ai.storyteller.photocraft']:
   process=launch([str(base/'wayland-fixture'),'server',name]);expect(process,'server','xdg-decoration',True);stop(process)
  print('PASS: real SSD negotiation wins over former class-name exceptions',flush=True)
  process=launch([str(base/'wayland-fixture'),'none','org.hics.NoProtocol'])
  expect(process,'client','wayland-self-decoration',False)
  command(process,'geometry');expect(process,'client','wayland-self-decoration',False);stop(process)
  process=launch([str(base/'wayland-fixture'),'client','org.hics.Csd'])
  expect(process,'client','xdg-decoration',False)
  command(process,'hold');command(process,'server');expect(process,'client','xdg-decoration',False)
  command(process,'ack');expect(process,'server','xdg-decoration',True)
  command(process,'geometry');expect(process,'server','xdg-decoration',True)
  command(process,'client');expect(process,'client','xdg-decoration',False)
  command(process,'unset');expect(process,'server','xdg-decoration',True)
  command(process,'destroy');expect(process,'client','wayland-self-decoration',False);stop(process)
  print('PASS: CSD/SSD negotiation, ack-before-commit, geometry independence, unset and destruction',flush=True)
  process=launch([str(base/'wayland-fixture'),'kde-server','org.hics.Legacy'])
  expect(process,'server','kde-decoration',True)
  for _ in range(5):
   command(process,'client');command(process,'geometry');expect(process,'client','kde-decoration',False)
   command(process,'server');command(process,'geometry');expect(process,'server','kde-decoration',True)
  command(process,'legacy-none');command(process,'geometry');expect(process,'none','kde-decoration',False)
  command(process,'destroy');expect(process,'client','wayland-self-decoration',False);stop(process)
  process=launch([str(base/'wayland-fixture'),'both','org.hics.DualProtocol'])
  expect(process,'client','xdg-decoration',False)
  command(process,'legacy-server');command(process,'geometry');expect(process,'client','xdg-decoration',False)
  command(process,'destroy');expect(process,'server','kde-decoration',True)
  command(process,'destroy');expect(process,'client','wayland-self-decoration',False);stop(process)
  print('PASS: legacy KDE negotiation, repeated switches, destruction and xdg precedence',flush=True)
  # User preferences remain orthogonal to what the toolkit negotiated.
  for name,mode,source in [('code-oss','client','user-show'),('org.hics.Scoped','server','user-hide'),('org.hics.NoDecoration','server','decoration-rule')]:
   process=launch([str(base/'wayland-fixture'),mode,name]);expect(process,'server' if source=='user-show' else 'none',source,source=='user-show');stop(process)
  print('PASS: manual show/hide and decoration rules override protocol defaults',flush=True)
  gtk=launch(['python3',str(ROOT/'tests/fixtures/canvas-input-app.py')],{'HICS_TEST_APPLICATION_ID':'org.hics.ActualGtk'})
  expect(gtk,'client',header=False);stop(gtk)
  qt=launch(['python3',str(ROOT/'tests/fixtures/canvas-qt-input-app.py')])
  expect(qt,'server',header=True);stop(qt)
  print('PASS: real GTK4 HeaderBar and Qt Widgets choose their own decoration policy',flush=True)
  for _ in range(60):
   children=subprocess.run(['ps','--ppid',str(compositor.pid),'-o','args='],capture_output=True,text=True).stdout
   display=re.search(r'Xwayland\s+(:\d+)',children)
   if display:break
   time.sleep(.1)
  assert display,children
  env['DISPLAY']=display.group(1)
  process=launch([str(base/'x11-fixture')],{'HICS_TEST_MOTIF':'none'})
  expect(process,'server','x11-default',True)
  # Read the fixture XID from its log without blocking its event loop.
  xid=(base/('client-'+str(len(fixtures)-1)+'.log')).read_text().splitlines()[0]
  for value,mode,source in [('0','client','motif-hints'),('1','server','motif-hints'),('8','server','motif-hints'),('9','client','motif-hints'),('2','client','motif-hints'),('functions','server','x11-default'),('invalid','server','x11-default'),('delete','server','x11-default')]:
   subprocess.run([str(base/'x11-fixture'),'motif',xid,value],env=env,check=True)
   expect(process,mode,source,mode=='server')
  subprocess.run([str(base/'x11-fixture'),'motif',xid,'0'],env=env,check=True)
  expect(process,'client','motif-hints',False)
  ctl('eval','hics_policy_override=hl.window_rule({name="hics-policy-x11-manual",match={class="org.hics.X11CsdFixture"},["hyprbars:no_bar"]=false})')
  expect(process,'server','user-show',True)
  ctl('eval','hics_policy_override:set_enabled(false)')
  expect(process,'client','motif-hints',False)
  stop(process)
  for _ in range(4):
   never_mapped=subprocess.Popen([str(base/'x11-fixture')],env=dict(env,HICS_TEST_NO_MAP='1'),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);fixtures.append(never_mapped)
   time.sleep(.12);stop(never_mapped)
  for _ in range(8):
   process=launch([str(base/'x11-fixture')]);expect(process,'client','motif-hints',False);stop(process)
  print('PASS: X11 default, Motif bits/exclusions, live changes/deletion, malformed hints and window lifetime',flush=True)
  for _ in range(60):
   stats=json.loads(ctl('repl','return hl.plugin.hyprbars.decoration_stats()'))
   if all(value==0 for value in stats.values()):break
   time.sleep(.05)
  assert all(value==0 for value in stats.values()),stats
  print('PASS: all protocol, callback and X11 request registries empty after client teardown',flush=True)
  assert not ctl('configerrors'),ctl('configerrors')
 except Exception:
  for log in base.glob('*.log'):
   Path('/tmp/hics-policy-'+log.name).write_text(log.read_text(errors='replace'))
  raise
 finally:
  for process in fixtures:
   if process.poll() is None:process.kill();process.wait()
  if compositor:compositor.terminate();compositor.wait(timeout=5)
