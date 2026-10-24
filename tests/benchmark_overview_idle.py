#!/usr/bin/env python3
"""Compare compositor CPU for an unchanged overview, using isolated native sets.
Run after building: python3 tests/benchmark_overview_idle.py --baseline DIR
DIR contains matching-ABI hics-bars.so and libhics-render-dispatch.so.
No FPS/game latency claim is inferred from this one idle scene.
"""
import argparse,json,os,shutil,subprocess,tempfile,time,statistics,math
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
def run(native,seconds):
 with tempfile.TemporaryDirectory(prefix='hics-overview-benchmark-') as directory:
  base=Path(directory);(base/'data/native').mkdir(parents=True);(base/'config/hics').mkdir(parents=True)
  for name in ('hics-bars.so','libhics-render-dispatch.so'):shutil.copy2(native/name,base/'data/native'/name)
  config=ROOT/'shell/assets/hyprland/config'
  (base/'test.lua').write_text('package.path='+json.dumps(str(config/'?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function()return require("scheme.default")end\nhl.monitor({output="WAYLAND-1",mode="1280x720@60",position="0x0",scale=1})\ndofile('+json.dumps(str(ROOT/'shell/assets/hyprland/layouts.lua'))+')\n')
  (base/'wall.qml').write_text('import QtQuick\nimport Quickshell\nimport Quickshell.Wayland\nPanelWindow {anchors{top:true;bottom:true;left:true;right:true}exclusionMode:ExclusionMode.Ignore;WlrLayershell.layer:WlrLayer.Background;color:"#28405a"}')
  env=dict(os.environ,AQ_BACKEND='wayland',HYPRSTACK_DATA_DIR=str(base/'data'),XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'user-data'),XDG_CACHE_HOME=str(base/'cache'));env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
  compositor=wallpaper=None
  try:
   with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'test.lua')],env=env,stdout=log,stderr=subprocess.STDOUT)
   for _ in range(80):
    instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
    if instance:break
    time.sleep(.1)
   assert instance,'Nested compositor did not start'
   def ctl(lua):return subprocess.check_output(['hyprctl','-i',instance['instance'],'repl',lua],text=True,timeout=5).strip()
   appenv=dict(env,WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
   wallpaper=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'wall.qml')],env=appenv,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   time.sleep(.8)
   scene={'monitor':'WAYLAND-1','mode':'scrolling','workspace':1,'originalWorkspace':1,'camera':{'x':0,'y':0,'zoom':.5},'originCamera':{'x':0,'y':0,'zoom':1},'colour':[.5,.3,.8],'windows':[],'worldRows':[]}
   ctl('hyprstack_layouts.set_overview(true);return hyprstack_layouts.overview_scene("show",'+json.dumps(json.dumps(scene))+')')
   time.sleep(.6)
   def cpu():
    fields=Path(f'/proc/{compositor.pid}/stat').read_text().rsplit(')',1)[1].split();return int(fields[11])+int(fields[12])
   start=time.monotonic();ticks=cpu()
   for _ in range(math.ceil(seconds/.4)):ctl('hyprstack_layouts.set_overview(true);hyprstack_layouts.overview_scene("heartbeat")');time.sleep(.4)
   seconds=time.monotonic()-start
   result={'seconds':round(seconds,3),'cpuPercentOneCore':round((cpu()-ticks)/os.sysconf('SC_CLK_TCK')/seconds*100,3)}
   state=json.loads(ctl('return hyprstack_layouts.overview_scene("status")'));assert state['active'],state
   result.update({key:state[key] for key in ('backgroundRenders','syntheticFrames') if key in state})
   return result
  finally:
   for process in (wallpaper,compositor):
    if process and process.poll() is None:
     process.terminate()
     try:process.wait(timeout=5)
     except subprocess.TimeoutExpired:process.kill();process.wait()
parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path);parser.add_argument('--seconds',type=float,default=3.2);parser.add_argument('--rounds',type=int,default=1);args=parser.parse_args()
assert 1<=args.rounds<=5 and 1<=args.seconds<=20
results={'before':[],'after':[]}
for iteration in range(args.rounds):
 order=[('before',args.baseline),('after',ROOT/'build')]
 if iteration%2:order.reverse()
 for name,path in order:
  if path:results[name].append(run(path,args.seconds))
for name,rows in list(results.items()):
 if rows:results[name]={'samples':rows,'medianCpuPercentOneCore':statistics.median(x['cpuPercentOneCore'] for x in rows)}
 else:del results[name]
print(json.dumps(results,indent=2))
