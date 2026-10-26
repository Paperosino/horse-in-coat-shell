#!/usr/bin/env python3
"""Measure full-shell QML startup in an isolated nested compositor (warm/cold cache).
No real session services or hardware writes: both D-Bus buses are private.
"""
import json,os,shutil,signal,subprocess,tempfile,time,argparse
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=ROOT/'shell');parser.add_argument('--check-ui',action='store_true');parser.add_argument('--fresh-cache',action='store_true');parser.add_argument('--probe-frame',action='store_true');parser.add_argument('--evict-source',action='store_true');args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='hics-startup-') as tmp:
 base=Path(tmp);shell=base/'shell'
 shutil.copytree(args.source,shell,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 if args.probe_frame:
  qml=(shell/'shell.qml').read_text().replace('import QtQuick\n','import QtQuick\nimport Hyprstack.Services\n',1)
  qml=qml.replace('Component.onCompleted: AnimationClock.activate()','Component.onCompleted: { StartupPerformance; AnimationClock.activate(); }')
  (shell/'shell.qml').write_text(qml)
 if args.check_ui:
  qml=(shell/'shell.qml').read_text().replace('import QtQuick\n','import QtQuick\nimport Quickshell.Io\nimport qs.modules.nexus\n',1)
  qml=qml.replace('ShortcutHelp { authenticationActive:', 'ShortcutHelp { id:shortcutsHelp; authenticationActive:')
  qml=qml.replace('active: Onboarding.running','id: startupTour; active: Onboarding.running',1)
  index=qml.rfind('}')
  qml=qml[:index]+'''    IpcHandler {target:"startupTest";function settings():void {WindowFactory.openPage("network");}function help():void {shortcutsHelp.toggle();}function tour():void {Onboarding.open();}function skip():void {Onboarding.skip();}function state():string {return JSON.stringify({running:Onboarding.running,status:startupTour.status,source:startupTour.source,model:startupTour.item?.model});}}
'''+qml[index:]
  (shell/'shell.qml').write_text(qml)
 (base/'config/hics').mkdir(parents=True)
 (base/'config/hics/shell.json').write_text('{"appearance":{"reducedMotion":true}}')
 (base/'config/hics/onboarding.json').write_text('{"state":"skipped","autoShow":false}')
 (base/'test.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
 env=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),HICS_NO_ONBOARDING='1',HICS_DATA_DIR=str(base/'missing-data'),HYPRSTACK_DATA_DIR=str(base/'missing-data'))
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 logs=[];processes=[]
 try:
  log=(base/'compositor.log').open('w');logs.append(log)
  compositor=subprocess.Popen(['Hyprland','--config',str(base/'test.lua')],env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(compositor)
  instance=None
  for _ in range(100):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
   if instance:break
   if compositor.poll() is not None:raise RuntimeError((base/'compositor.log').read_text()[-2000:])
   time.sleep(.1)
  assert instance
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland')
  runner=base/'run.py';runner.write_text('import os,sys\nos.environ["DBUS_SYSTEM_BUS_ADDRESS"]=os.environ["DBUS_SESSION_BUS_ADDRESS"]\nos.execvp(sys.argv[1],sys.argv[1:])\n')
  for iteration in range(3):
   path=base/f'shell{iteration}.log';log=path.open('w');logs.append(log)
   if args.fresh_cache:env['XDG_CACHE_HOME']=str(base/f'cold-cache{iteration}')
   if args.evict_source:
    # Only discard our copied files, never global caches or mapped host libraries.
    for file in shell.rglob('*'):
     if file.is_file() and not file.is_symlink():
      with file.open('rb') as copied:
       os.fsync(copied.fileno());os.posix_fadvise(copied.fileno(),0,0,os.POSIX_FADV_DONTNEED)
   instrumented=args.probe_frame or 'StartupPerformance' in (shell/'modules/ServiceLoader.qml').read_text()
   qml_elapsed=None
   started=time.monotonic()
   proc=subprocess.Popen(['dbus-run-session','--','python3',str(runner),'/usr/share/hics/qs/bin/hics-qs','-p',str(shell)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(proc)
   while time.monotonic()-started<30:
    data=path.read_text()
    if 'Configuration Loaded' in data and qml_elapsed is None:qml_elapsed=time.monotonic()-started
    if qml_elapsed is not None and (not instrumented or 'hics startup: first visible frame submitted' in data):break
    if proc.poll() is not None:raise AssertionError(data[-6000:])
    time.sleep(.02)
   else:raise AssertionError(data[-6000:])
   print(json.dumps({'iteration':iteration,'freshCache':args.fresh_cache,'evictedCopiedFiles':args.evict_source,'qmlLoadedSeconds':round(qml_elapsed,3),'firstFrameSeconds':round(time.monotonic()-started,3) if instrumented else None}),flush=True)
   time.sleep(.4)
   if args.check_ui and iteration==2:
    qs='/usr/share/hics/qs/bin/hics-qs'
    # IPC uses the process's private runtime socket, not the host shell.
    subprocess.run([qs,'ipc','-p',str(shell),'call','startupTest','settings'],env=env,check=True,capture_output=True,timeout=15)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
     clients=json.loads(subprocess.check_output(['hyprctl','-i',instance['instance'],'clients','-j']))
     if any('Nexus' in c.get('title','') or 'Настройки' in c.get('title','') for c in clients):break
     time.sleep(.1)
    else:raise AssertionError('Deferred settings window failed: '+str(clients)+path.read_text()[-10000:])
    subprocess.run([qs,'ipc','-p',str(shell),'call','startupTest','help'],env=env,check=True,capture_output=True,timeout=15)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
     layers=subprocess.check_output(['hyprctl','-i',instance['instance'],'layers','-j'],text=True)
     if 'shortcut-help' in layers:break
     time.sleep(.1)
    else:raise AssertionError('Deferred shortcut help failed: '+path.read_text()[-5000:])
    subprocess.run([qs,'ipc','-p',str(shell),'call','startupTest','help'],env=env,check=True,capture_output=True,timeout=15)
    subprocess.run([qs,'ipc','-p',str(shell),'call','startupTest','tour'],env=env,check=True,capture_output=True,timeout=15)
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
     layers=subprocess.check_output(['hyprctl','-i',instance['instance'],'layers','-j'],text=True)
     if 'onboarding' in layers:break
     time.sleep(.1)
    else:
     print(subprocess.run([qs,'ipc','-p',str(shell),'call','startupTest','state'],env=env,capture_output=True,text=True).stdout,flush=True)
     Path('/tmp/hics-startup-ui-debug.log').write_text(path.read_text())
     raise AssertionError('Deferred tour failed: '+layers+path.read_text()[-5000:])
    subprocess.run([qs,'ipc','-p',str(shell),'call','startupTest','skip'],env=env,check=True,capture_output=True,timeout=15)
    print('PASS: deferred settings, shortcut help and tour open on first request',flush=True)
   assert 'TypeError:' not in path.read_text() and 'ReferenceError:' not in path.read_text(),path.read_text()[-5000:]
   os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10)
 finally:
  for proc in reversed(processes):
   if proc is not compositor:
    try:os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError:pass
   elif proc.poll() is None:proc.terminate()
  for proc in reversed(processes):
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
  for log in logs:log.close()
