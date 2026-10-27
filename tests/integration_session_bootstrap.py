#!/usr/bin/env python3
"""Use the full shipped Lua root with isolated settings and an unrelated config."""
import ast, json, os, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path
from unittest.mock import patch
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shell/assets'))
import session_bootstrap
with tempfile.TemporaryDirectory(prefix='hics session bootstrap ') as directory:
 base=Path(directory);data=base/'data';data.mkdir()
 shutil.copytree(ROOT/'shell/assets/hyprland',data/'shell/assets/hyprland')
 (data/'defaults').symlink_to(ROOT/'distribution/defaults',target_is_directory=True)
 config=base/'config';other=config/'hypr/hyprland.lua';other.parent.mkdir(parents=True)
 original='-- unrelated compositor configuration\n';other.write_text(original)
 variables,entry=session_bootstrap.prepare(data,config)
 workspace=config/'hics/workspace.json'
 options=json.loads(workspace.read_text()) if workspace.exists() else {}
 options['shortcuts']={'overrides':{'Custom: Caps_Lock\n':{'keys':['SUPER + F10']}}}
 workspace.write_text(json.dumps(options))
 env=dict(os.environ,**variables,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(config),XDG_DATA_HOME=str(base/'xdg-data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),HYPRSTACK_NESTED='1')
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 with (base/'compositor.log').open('w') as log:
  compositor=subprocess.Popen(['Hyprland','--config',str(entry)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  instance=None
  for _ in range(100):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   if compositor.poll() is not None:raise AssertionError((base/'compositor.log').read_text()[-6000:])
   time.sleep(.1)
  assert instance,'Nested HICS compositor did not start'
  def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],env=env,text=True,timeout=8).strip()
  assert not ctl('configerrors'),ctl('configerrors')
  binding_source=(ROOT/'shell/services/KeyboardStateBindings.js').read_text()
  binding_command=ast.literal_eval(next(line for line in binding_source.splitlines() if line.startswith('var luaCommand = ')).split(' = ',1)[1].rstrip(';'))
  def keyboard_state_check(disabled=False):
   for _ in range(10):ctl('eval',binding_command.removeprefix('eval '))
   binds=json.loads(ctl('-j','binds'))
   caps=[b for b in binds if b.get('description')=='Custom: Caps_Lock']
   nums=[b for b in binds if b.get('description')=='Custom: Num_Lock']
   assert len(nums)==1,nums
   assert len(caps)==(0 if disabled else 1),caps
   if caps:assert caps[0]['key']=='F10' and caps[0]['modmask']!=0,caps
  keyboard_state_check()

  package_root=data/'shell/assets/hyprland/config/hyprland.lua'
  old_package_root=package_root.read_bytes();package_root.unlink();time.sleep(.5)
  assert not ctl('configerrors'),'Package replacement invalidated the private root: '+ctl('configerrors')
  package_root.write_bytes(old_package_root)
  palette=json.loads((ROOT/'shell/assets/feature_data/default-palette.json').read_text())
  with patch.dict(os.environ,env),patch('gtk_theme.apply_desktop_palette'):
   import theme_manager
   theme_manager.save_current(palette)
  assert (config/'hics/hypr/scheme/current.lua').exists()
  assert not (config/'hypr/scheme').exists()
  ctl('reload');assert not ctl('configerrors'),ctl('configerrors')
  (config/'hics/hypr/scheme/current.lua').unlink()
  ctl('reload');assert not ctl('configerrors'),ctl('configerrors')
  assert (config/'hics/hypr/scheme/current.lua').exists(),'Missing scheme did not recover'
  assert other.read_text()==original
  assert list(other.parent.iterdir())==[other]
  keyboard_state_check()
  options['shortcuts']['overrides']['Custom: Caps_Lock\n']={'disabled':True}
  workspace.write_text(json.dumps(options));ctl('reload');keyboard_state_check(True)
  print('PASS: full managed Lua startup, theme/scheme recovery, idempotent keyboard-state binds, remapped/disabled user override; unrelated Hyprland config untouched')
 finally:
  try:os.killpg(compositor.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:compositor.wait(timeout=5)
  except subprocess.TimeoutExpired:
   os.killpg(compositor.pid,signal.SIGKILL);compositor.wait()
