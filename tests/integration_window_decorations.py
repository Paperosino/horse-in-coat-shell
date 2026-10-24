#!/usr/bin/env python3
"""Render stacking titlebars for server- and client-decorated app classes."""
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
  from PIL import Image
  for klass,expected in [('org.hics.WindowFixture',True),('org.telegram.desktop',True),('com.ayugram.desktop',True),('ai.storyteller.photocraft',False),('org.gnome.Nautilus',False),('Code',False),('code-oss',True),('helium',True),('org.hics.Scoped',False),('org.hics.NoDecoration',False)]:
   terminal=subprocess.Popen(['kitty','--class',klass,'--title','Decoration fixture','-o','confirm_os_window_close=0','sleep','60'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);fixtures.append(terminal)
   for _ in range(50):
    clients=json.loads(ctl('-j','clients'))
    window=next((w for w in clients if w['pid']==terminal.pid),None)
    if window:break
    time.sleep(.1)
   assert window,klass
   address=window['address']
   ctl('eval','local w=hl.get_window("address:'+address+'");hl.dispatch(hl.dsp.window.resize({window=w,x=600,y=400,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=220,y=200,relative=false}))')
   time.sleep(.8)
   window=next(w for w in json.loads(ctl('-j','clients')) if w['pid']==terminal.pid)
   image=base/'frame.png';subprocess.run(['grim',str(image)],env=env,check=True,capture_output=True)
   image=Image.open(image).convert('RGB');x,y=window['at'];width,height=window['size']
   strip=image.crop((x+30,y-24,x+width-30,y-8))
   # A server titlebar has a solid themed surface across the width. The
   # compositor wallpaper above a client-owned header is outside that surface.
   from collections import Counter
   pixels=Counter(strip.getdata());colour,count=pixels.most_common(1)[0]
   background=image.getpixel((x+width//2,y-60))
   has_bar=colour!=background and count>strip.width*strip.height*.60
   assert has_bar==expected,(klass,expected,colour,count,window['at'])
   print('PASS:',klass,'server titlebar' if has_bar else 'client-owned header',flush=True)
   if klass=='org.hics.Scoped':
    def bar_height():return json.loads(ctl('repl','local w=hl.get_window("address:'+address+'");return hl.plugin.hyprbars.animate_window(w.address,string.format("%x",w.stable_id),"titlebar-height")'))
    ctl('eval','hics_test_gate=hyprstack_layouts.application_rule("tiling",{name="hics-test-mode-gate",match={class="org.hics.Scoped"},no_shadow=true})')
    def gate_enabled():return json.loads(ctl('repl','return hics_test_gate:is_enabled()'))
    assert bar_height()==0 and not gate_enabled()
    ctl('eval','hyprstack_layouts.set_mode("scrolling")');time.sleep(.4)
    ctl('eval','hyprstack_layouts.set_mode("stacking")');time.sleep(.4)
    assert bar_height()==0,'Mode-scoped rule did not return'
    ctl('eval','hyprstack_layouts.set_mode("tiling")');time.sleep(.4)
    assert gate_enabled(),'Tiling rule did not activate'
    ctl('eval','hyprstack_layouts.set_mode("stacking")');time.sleep(.4)
    assert bar_height()==0 and not gate_enabled(),'Tiling round trip lost rule scope'
    ctl('eval','hyprstack_layouts.set_mode("canvas")');time.sleep(.5)
    assert not gate_enabled(),'Tiling rule leaked into canvas'
    ctl('eval','hyprstack_layouts.set_mode("stacking")');time.sleep(.5)
    assert bar_height()==0 and not gate_enabled()
    print('PASS: mode-scoped titlebar survives scrolling/tiling round trips',flush=True)
   terminal.terminate();terminal.wait(timeout=5);terminal=None
  pip=subprocess.Popen(['kitty','--class','helium','-o','confirm_os_window_close=0','sh','-c',"printf '\\033]2;Video fixture\\007'; sleep 2; printf '\\033]2;Picture-in-Picture\\007'; sleep 30"],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);fixtures.append(pip)
  for _ in range(60):
   window=next((w for w in json.loads(ctl('-j','clients')) if w['pid']==pip.pid and w['title']=='Picture-in-Picture'),None)
   if window and window['floating'] and window['pinned']:break
   time.sleep(.1)
  assert window and window['floating'] and window['pinned'],window
  print('PASS: late browser PiP title becomes a pinned floating window',flush=True)
 finally:
  for process in fixtures:
   if process.poll() is None:process.kill();process.wait()
  if compositor:compositor.terminate();compositor.wait(timeout=5)
