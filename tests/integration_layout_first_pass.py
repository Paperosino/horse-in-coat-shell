#!/usr/bin/env python3
"""Parse production rules before the deferred titlebar plugin is available."""
import os,json,subprocess,tempfile,time
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
r=Path(__file__).resolve().parents[1];b=Path(tempfile.mkdtemp(prefix='hics-firstpass-'));(b/'config/hics').mkdir(parents=True);(b/'config/hics/layouts.json').write_text('{"mode":"stacking"}')
lua=b/'test.lua';lua.write_text('package.path='+json.dumps(str(r/'shell/assets/hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\nhl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\ndofile('+json.dumps(str(r/'shell/assets/hyprland/config/hyprland/animations.lua'))+')\ndofile('+json.dumps(str(r/'shell/assets/hyprland/config/hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(r/'shell/assets/hyprland/layouts.lua'))+')\n')
env=dict(os.environ,HOME=str(b/'home'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(b/'absent-bus'),DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(b/'absent-system-bus'),PIPEWIRE_REMOTE='hics-firstpass-absent',AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(b/'config'),XDG_DATA_HOME=str(b/'data'),XDG_STATE_HOME=str(b/'state'),HYPRSTACK_TITLEBAR_PLUGIN=str(b/'absent.so'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
with (b/'log').open('w') as log:p=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
try:
 for _ in range(150):
  i=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==p.pid),None)
  if i:break
  assert p.poll() is None,(b/'log').read_text()
  time.sleep(.1)
 assert i,'Nested compositor did not start'
 def ctl(*a):return subprocess.check_output(['hyprctl','-i',i['instance'],*a],text=True).strip()
 time.sleep(1);errors=ctl('configerrors');assert not errors,errors
 assert ctl('repl','return hl.plugin.hyprbars ~= nil')=='false'
 assert 'bool: true' in ctl('getoption','misc:disable_xdg_env_checks')
 assert ctl('repl','return os.getenv("XDG_CURRENT_DESKTOP")')=='HICS:Hyprland'
 print('PASS: complete production layouts parses without titlebar plugin',flush=True)
finally:
 p.terminate();p.wait(timeout=10)
print('Artifacts:',b)
