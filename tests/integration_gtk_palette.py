"""Check real GTK 2/3 styles and rendered GTK4 pixels with private config."""
import os,subprocess,tempfile,shlex,sys,time,shutil
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shell/assets'))
from gtk_theme import apply_palette
with tempfile.TemporaryDirectory(prefix='hics-gtk-palette-') as directory:
 base=Path(directory);config=base/'config';runtime=base/'runtime';runtime.mkdir(mode=0o700)
 colours=dict(surface='101018',onSurface='e0e0e0',surfaceContainer='202028',primary='aaccee',onPrimary='102030',outlineVariant='505060',error='ee3344',onError='ffffff')
 apply_palette(colours,config)
 env=dict(os.environ,XDG_CONFIG_HOME=str(config),GTK2_RC_FILES=str(config/'gtk-2.0/gtkrc'),GTK_A11Y='none',GTK_PROBE_IMAGE=str(base/'gtk4.png'))
 env.pop('GTK_THEME',None)
 # Obtain this session's Xwayland environment rather than a stale inherited DISPLAY.
 pid=subprocess.check_output(['systemctl','--user','show','hic-session.service','--property=MainPID','--value'],text=True).strip()
 if pid!='0':
  for pair in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
   key,_,value=pair.partition(b'=')
   if key in (b'DISPLAY',b'XAUTHORITY'):env[key.decode()]=value.decode()
 for version in (2,3,4,5):
  binary=base/f'gtk{version}'
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',f'gtk+-{version}.0' if version<4 else ('libadwaita-1' if version==5 else 'gtk4')],text=True))
  if version==5:flags.append('-DADWAITA_PROBE')
  subprocess.run(['cc',str(ROOT/f'tests/fixtures/{"gtk4-colour-probe.c" if version>=4 else "gtk-colour-probe.c"}'),*flags,'-o',str(binary)],check=True,capture_output=True)
  if version<4:
   run=subprocess.run([str(binary)],env=dict(env,GDK_BACKEND='x11'),capture_output=True,text=True,check=True,timeout=10)
   assert 'window #101018 #e0e0e0' in run.stdout,run.stdout
   assert '#e0e0e0' in run.stdout,run.stdout
   print(f'GTK{version}:',run.stdout.strip())
 parent=os.environ.get('WAYLAND_DISPLAY','wayland-1');parent=parent if parent.startswith('/') else str(Path(os.environ['XDG_RUNTIME_DIR'])/parent)
 compositor_config=base/'compositor.lua';compositor_config.write_text('hl.monitor({output="WAYLAND-1",mode="800x600@60",position="0x0",scale=1})\n')
 with (base/'compositor.log').open('w') as log:
  compositor=subprocess.Popen(['Hyprland','--config',str(compositor_config)],env=dict(env,XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY=parent,AQ_BACKEND='wayland'),stdout=log,stderr=subprocess.STDOUT)
 try:
  sockets=[]
  for _ in range(80):
   sockets=[p for p in runtime.glob('wayland-*') if p.is_socket()]
   if sockets or compositor.poll() is not None:break
   time.sleep(.1)
  assert sockets,(base/'compositor.log').read_text()[-3000:]
  for binary in ("gtk4","gtk5"):
   run=subprocess.run([str(base/binary)],env=dict(env,XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY=str(sockets[0]),GDK_BACKEND='wayland',GSK_RENDERER='cairo'),capture_output=True,text=True,timeout=12)
   assert run.returncode==0,run.stderr
   assert 'Theme parsing error' not in run.stderr,run.stderr
   image=Image.open(base/'gtk4.png').convert('RGB');pixels=list(image.getdata())
   for colour in ('101018','202028','aaccee','ee3344'):
    rgb=tuple(bytes.fromhex(colour));count=pixels.count(rgb)
    assert count>100,(colour,count,run.stderr)
    print(binary+' rendered:',colour,count,'pixels')
  # A search bar's child container has its own stock GTK background. Force
  # the light base theme to catch a missing palette rule even in a dark DE.
  binary=base/'searchbar';flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-3.0'],text=True))
  subprocess.run(['cc',str(ROOT/'tests/fixtures/gtk-header-probe.c'),'-DSEARCHBAR_PROBE',*flags,'-o',str(binary)],check=True,capture_output=True)
  search_env=dict(env,XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY=str(sockets[0]),GDK_BACKEND='wayland',GTK_THEME='Adwaita:light',GTK_PROBE_IMAGE=str(base/'searchbar.png'))
  run=subprocess.run([str(binary)],env=search_env,capture_output=True,text=True,timeout=15);assert run.returncode==0,run.stderr
  image=Image.open(base/'searchbar.png').convert('RGB');image.save('/tmp/hics-gtk-searchbar.png')
  for y in range(5,min(90,image.height)):
   line=[image.getpixel((x,y)) for x in range(20,image.width-20)]
   assert sum(min(pixel)>190 for pixel in line)<len(line)*.5,('Search bar retained a bright stripe',y)
  print('PASS: GTK3 search bar follows the shell palette even over a light base theme')
  if shutil.which('remmina'):
   # Load the installed application's real GtkBuilder UI, without starting
   # networking, reading saved connections, or reusing the user's process.
   remmina=Path(shutil.which('remmina'))
   resources=subprocess.check_output(['gresource','list',str(remmina)],text=True).splitlines()
   resource=next(path for path in resources if path.endswith('/remmina_main.glade'))
   (base/'remmina.glade').write_bytes(subprocess.check_output(['gresource','extract',str(remmina),resource]))
   binary=base/'remmina-ui';subprocess.run(['cc',str(ROOT/'tests/fixtures/gtk-header-probe.c'),'-DREMMINA_PROBE',*flags,'-o',str(binary)],check=True,capture_output=True)
   run=subprocess.run([str(binary)],env=dict(search_env,REMMINA_PROBE_UI=str(base/'remmina.glade'),GTK_PROBE_IMAGE=str(base/'remmina.png')),capture_output=True,text=True,timeout=15);assert run.returncode==0,run.stderr
   image=Image.open(base/'remmina.png').convert('RGB');image.save('/tmp/hics-remmina-palette.png')
   # A one-pixel separator is legitimate; a light container is a band.
   bright_rows=[]
   for y in range(8,min(95,image.height)):
    line=[image.getpixel((x,y)) for x in range(20,image.width-20)]
    if sum(min(pixel)>190 for pixel in line)>=len(line)*.6:bright_rows.append(y)
   assert not any(b-a==1 for a,b in zip(bright_rows,bright_rows[1:])),('Remmina retained a bright band',bright_rows)
   print('PASS: installed Remmina UI has no bright quick-connect band')
  # Exercise actual file chooser and libadwaita header nodes, not just buttons.
  (config/'hics').mkdir(exist_ok=True)
  (config/'hics/window-controls.json').write_text('{"side":"left","order":["close","minimize"]}')
  apply_palette(colours,config,"dark")
  (base/'files').mkdir()
  (base/'files/example.txt').write_text('File chooser fixture')
  for version,pkg in ((3,'gtk+-3.0'),(4,'gtk4'),(5,'libadwaita-1')):
   binary=base/f'header{version}'
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',pkg],text=True))
   if version==5:flags.append('-DADWAITA_PROBE')
   subprocess.run(['cc',str(ROOT/'tests/fixtures/gtk-header-probe.c'),*flags,'-o',str(binary)],check=True,capture_output=True)
   header_env=dict(env,XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY=str(sockets[0]),GDK_BACKEND='wayland',GSK_RENDERER='cairo',GSETTINGS_BACKEND='keyfile',XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),GTK_PROBE_FOLDER=str(base/'files'),GTK_PROBE_IMAGE=str(base/f'header{version}.png'))
   script='import subprocess,sys;subprocess.run(["gsettings","set","org.gnome.desktop.wm.preferences","button-layout","close,minimize:"],check=True);sys.exit(subprocess.run([sys.argv[1]]).returncode)'
   run=subprocess.run(['dbus-run-session','--',sys.executable,'-c',script,str(binary)],env=header_env,capture_output=True,text=True,timeout=20)
   assert run.returncode==0,run.stderr
   assert 'LAYOUT=close,minimize:' in run.stdout,run.stdout+run.stderr
   assert 'Theme parsing error' not in run.stderr,run.stderr
   image=Image.open(base/f'header{version}.png').convert('RGB')
   image.save(f'/tmp/hics-gtk-header{version}.png')
   # Reject bright horizontal stripes spanning most of the dialog below its header.
   for y in range(30,min(110,image.height)):
    line=[image.getpixel((x,y)) for x in range(30,image.width-30)]
    bright=sum(min(pixel)>190 for pixel in line)
    assert bright<len(line)*.70,(version,y,bright,len(line))
   image.save(f'/tmp/hics-gtk-header{version}.png')
   print(f'PASS: GTK {version} header/file chooser honours button order without a bright header stripe')
 finally:
  compositor.terminate();compositor.wait(timeout=10)
print('PASS: GTK2/3 widget colours and GTK4 rendered button states follow the shell palette')
