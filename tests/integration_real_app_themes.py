#!/usr/bin/env python3
"""Real Kate automatic editor mode and Swappy chrome, in an isolated compositor."""
import os,json,subprocess,sys,tempfile,time,shutil
from pathlib import Path
from PIL import Image
from integration_support import require_wayland_session
require_wayland_session();ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'shell/assets'))
from gtk_theme import apply_palette
with tempfile.TemporaryDirectory(prefix='hics-real-theme-') as directory:
 base=Path(directory);config=base/'config';runtime=Path(os.environ['XDG_RUNTIME_DIR'])
 colours=dict(surface='101018',onSurface='e0e0e0',surfaceContainer='202028',primary='aaccee',onPrimary='102030',outlineVariant='505060')
 apply_palette(colours,config,'dark')
 # Reproduce Kate's existing automatic selection with a stale light editor theme.
 (config/'katerc').write_text('[KTextEditor Renderer]\nAuto Color Theme Selection=true\nColor Theme=Breeze Light\n')
 fixture=base/'fixture.cpp';fixture.write_text('// A dark editor must be chosen automatically.\nint main() { return 0; }\n')
 picture=base/'picture.png';Image.new('RGB',(640,400),(24,160,56)).save(picture)
 parent=os.environ.get('WAYLAND_DISPLAY','wayland-1');parent=parent if parent.startswith('/') else str(Path(os.environ['XDG_RUNTIME_DIR'])/parent)
 env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY=parent,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(config),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent/hics-theme-test')
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);env.pop('LD_LIBRARY_PATH',None)
 lua=base/'test.lua';lua.write_text('hl.monitor({output="WAYLAND-1",mode="1000x760@60",position="0x0",scale=1})\n')
 compositor=app=None
 try:
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
  instance=None
  for _ in range(80):
   rows=json.loads(subprocess.check_output(['hyprctl','instances','-j'],text=True))
   instance=next((r for r in rows if r['pid']==compositor.pid),None)
   if instance:break
   if compositor.poll() is not None:raise RuntimeError((base/'compositor.log').read_text())
   time.sleep(.1)
  assert instance,'No compositor IPC instance'
  controlenv=dict(os.environ,HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland',GDK_BACKEND='wayland')
  for name,command,extra in [
   ('kate',['kate','-n','--startanon',str(fixture)],{'QT_QPA_PLATFORMTHEME':'hics','QT_PLUGIN_PATH':str(ROOT/'build/qt-themes/qt6')}),
   ('swappy',['swappy','-f',str(picture)],{'GTK_THEME':'Adwaita:dark'})]:
   with (base/(name+'.log')).open('w') as log:app=subprocess.Popen(command,env=dict(env,**extra),stdout=log,stderr=subprocess.STDOUT)
   time.sleep(3)
   assert app.poll() is None,(name,(base/(name+'.log')).read_text())
   screenshot=Path('/tmp/hics-theme-'+name+'.png')
   subprocess.run(['grim',str(screenshot)],env=env,check=True,capture_output=True,timeout=5)
   image=Image.open(screenshot).convert('RGB')
   clients=json.loads(subprocess.check_output(['hyprctl','-j','clients'],env=controlenv,text=True))
   window=next(c for c in clients if c.get('mapped'))
   x,y=window['at'];w,h=window['size'];image=image.crop((x,y,x+w,y+h));image.save(screenshot)
   pixels=[p for p in image.getdata() if not (p[0]<50 and p[1]>100 and p[2]<80)]
   dark=sum(max(p)<85 for p in pixels)
   assert pixels and dark>len(pixels)*.65,(name,dark,len(pixels),image.size)
   print('PASS:',name,'dark real window and controls',dark,flush=True)
   app.terminate();app.wait(timeout=5);app=None
 finally:
  if app and app.poll() is None:app.kill();app.wait()
  if compositor:compositor.terminate();compositor.wait(timeout=5)
