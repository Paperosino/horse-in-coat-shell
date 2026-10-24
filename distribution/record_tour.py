#!/usr/bin/env python3
"""Record production hics UI in isolated real Hyprland sessions (RU and EN).

No fabricated window animation is rendered. Public service actions drive the
production shell, real kitty windows and the normal settings components.
"""
import argparse,hashlib,json,os,shutil,signal,subprocess,tempfile,time,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'shell/assets';DEST=ASSETS/'tour'

def record(language,only):
 with tempfile.TemporaryDirectory(prefix='hics-tour-record-') as directory:
  base=Path(directory);home=base/'home';home.mkdir();cfg=base/'config/hics';cfg.mkdir(parents=True);state=base/'state/hics';state.mkdir(parents=True);(base/'data/applications').mkdir(parents=True);(base/'native').mkdir()
  for name in ('hics-bars.so','libspatialoverview.so','hics-capture.so','hics-motion.so'):
   choices=[ROOT/'build'/name,ROOT/'build/third_party/phantomat'/name,Path('/usr/share/hics/native')/name]
   source=next((p for p in choices if p.is_file()),None)
   if source:shutil.copy2(source,base/'native'/name)
  wallpaper=next((Path.home()/'Изображения/Wallpapers/hics-collection').glob('glass-chip-d.jpg'),None)
  if not wallpaper:wallpaper=next((Path.home()/'Pictures/Wallpapers/hics-collection').glob('*.jpg'),None)
  if not wallpaper:raise RuntimeError('Download the wallpaper collection first')
  (base/'wallpapers').mkdir();shutil.copy2(wallpaper,base/'wallpapers/background.jpg');(state/'wallpaper').mkdir();(state/'wallpaper/path.txt').write_text(str(base/'wallpapers/background.jpg'))
  (cfg/'shell.json').write_text(json.dumps({'general':{'language':language},'paths':{'wallpaperDir':str(base/'wallpapers')},'services':{'weatherEnabled':False},'dashboard':{'enabled':False},'utilities':{'enabled':True,'toasts':{'configLoaded':False}}}))
  (cfg/'layouts.json').write_text(json.dumps({'mode':'stacking','canvasMinimap':True,'canvasZoom':.72,'canvasGrid':True}))
  (cfg/'dock.json').write_text(json.dumps({'enabled':True,'position':'bottom','animations':True,'windowAnimations':True,'iconSize':44}))
  (cfg/'workspace.json').write_text(json.dumps({'clipboard':{'enabled':True},'session':{'enabled':False}}))
  (cfg/'onboarding.json').write_text(json.dumps({'state':'skipped','autoShow':False,'step':0}))
  source=base/'shell';shutil.copytree(ROOT/'shell',source,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
  control=base/'control.json';control.write_text('{}');probe=base/'probe.json'
  shell=(source/'shell.qml').read_text().replace('import "modules/configuration" as Configuration','import Hyprstack.I18n\nimport Hyprstack.Config\nimport Quickshell.Io\nimport qs.modules.nexus as NexusModule\nimport qs.modules.nexus.common as DemoCommon\nimport "modules/configuration" as Configuration')
  if 'onboarding' in only:shell=shell.replace('OnboardingModule.Wizard {}','OnboardingModule.Wizard {id:onboardingWizard}')
  injection='''
 property int demoSequence:0
 FileView {id:demoProbe;path:__PROBE_PATH__;printErrors:false}
 function findDemo(item,name){if(item.objectName===name)return item;for(const child of item.children??[]){const found=findDemo(child,name);if(found)return found;}return null;}
 function reportSetup(){const win=onboardingWizard.instances.find(w=>w.primary);if(!win)return;const loader=findDemo(win.contentItem,"onboarding-body");const flick=loader?.item?.flickable;const skip=findDemo(win.contentItem,"onboarding-skip");const movie=findDemo(win.contentItem,"onboarding-demo");const point=flick?.mapToItem(win.contentItem,20,Math.min(flick.height-10,100));demoProbe.setText(JSON.stringify({width:win.width,height:win.height,scroll:flick?.contentY??0,content:flick?.contentHeight??0,viewport:flick?.height??0,x:point?.x,y:point?.y,movieFrames:movie?.renderedFrames()??0,movieError:movie?.playbackError??"",skipVisible:skip?.visible,skipForeground:skip?.onColour.toString(),skipBackground:skip?.color.toString(),skipX:skip?.mapToItem(win.contentItem,0,0).x,skipWidth:skip?.width,skipY:skip?.mapToItem(win.contentItem,0,0).y,skipHeight:skip?.height}));}
 FloatingWindow {
  id:demoSettings;visible:false;title:Tr.tr("Settings");implicitWidth:940;implicitHeight:620;color:Colours.palette.m3surface
  contentItem.Config.screen:screen.name;contentItem.Tokens.screen:screen.name
  NexusModule.Nexus {id:demoNexus;anchors.fill:parent;nState.screen:demoSettings.screen;nState.isWindow:true;onClose:demoSettings.visible=false}
 }
 function closeDemoDrawers():void {for(const screen of Quickshell.screens){const s=ShellState.forScreen(screen);if(s){s.launcher=false;s.clipboard=false;s.dashboard=false;}}}
 FileView {
  path:__CONTROL_PATH__;watchChanges:true;printErrors:false;onFileChanged:reload()
  onLoaded:{try{
   const c=JSON.parse(text());if(!c.sequence||c.sequence<=root.demoSequence)return;root.demoSequence=c.sequence;
   if(c.probe)root.reportSetup();
   if(c.setup!==undefined){demoSettings.visible=false;Onboarding.open(c.setup);}
   if(c.setupSkip){Onboarding.skip();console.log("ONBOARDING_SKIP_OK",Onboarding.running);}
   if(c.language)Tr.language=c.language;
   if(c.mode){demoSettings.visible=false;root.closeDemoDrawers();LayoutModes.select(c.mode);}
   if(c.page){demoNexus.nState.openPage(c.page);demoSettings.visible=true;}
   if(c.closeSettings)demoSettings.visible=false;
   if(c.expandMemory){function visit(item){if(item.title===Tr.tr("Memory compression")&&item.collapsible!==undefined)item.expanded=true;for(const child of item.children??[])visit(child);}visit(demoNexus);}
   if(c.layout)KeyboardConf.addLayout(c.layout);
   if(c.switchLayout)KeyboardConf.setSwitchOption(c.switchLayout);
   if(c.theme)Colours.setMode(c.theme);
   if(c.display){Monitors.stagePosition(Quickshell.screens[0].name,c.display,0);Monitors.apply();}
   if(c.revertDisplay)DisplayProfiles.revert();
   if(c.drawer){root.closeDemoDrawers();ShellState.forScreen(Quickshell.screens[0])[c.drawer]=true;}
   if(c.closeDrawers)root.closeDemoDrawers();
  }catch(e){console.error("DEMO_CONTROL_ERROR",e);}}
 }
'''.replace('__CONTROL_PATH__',json.dumps(str(control))).replace('__PROBE_PATH__',json.dumps(str(probe)))
  if 'onboarding' not in only:injection=injection.replace('if(c.probe)root.reportSetup();','').replace(next(l for l in injection.splitlines() if l.startswith(' function reportSetup()')),'')
  shell=shell[:shell.rfind('}')]+injection+'\n}';(source/'shell.qml').write_text(shell)
  lua=base/'hyprland.lua';lua.write_text('package.path='+json.dumps(str(ASSETS/'hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function() return require("scheme.default") end\nhl.monitor({output="",mode="1280x720@60",position="auto",scale=1})\nhl.config({input={kb_layout="us",follow_mouse=0},misc={disable_watchdog_warning=true,disable_hyprland_logo=true,disable_splash_rendering=true}})\ndofile('+json.dumps(str(ASSETS/'hyprland/config/hyprland/animations.lua'))+')\ndofile('+json.dumps(str(ASSETS/'hyprland/config/hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(ASSETS/'hyprland/layouts.lua'))+')\n')
  env=dict(os.environ,HOME=str(home),AQ_BACKEND='headless',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),XDG_CURRENT_DESKTOP='Hyprland',HYPRSTACK_DATA_DIR=str(base),HICS_DATA_DIR=str(base),HYPRSTACK_NESTED='1',HICS_NO_ONBOARDING='1',HICS_CONFIG_NO_SYSTEMD='1',HICS_DISPLAY_NO_SYSTEMD='1',QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland',LANG='ru_RU.UTF-8' if language=='ru_RU' else 'en_US.UTF-8',HYPRSTACK_LANGUAGE=language,HICS_WORKSPACE_HELPER=str(ROOT/'build/lib/hics-workspace'))
  env['HICS_RECORD_SYSTEM_BUS']=os.environ.get('DBUS_SYSTEM_BUS_ADDRESS','unix:path=/run/dbus/system_bus_socket')
  env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);env.pop('DISPLAY',None)
  compositor=qs=recorder=pointer=None;apps=[];manifest=[]
  try:
   with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(lua)],env=env,stdout=log,stderr=subprocess.STDOUT)
   instance=None
   for _ in range(100):
    instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==compositor.pid),None)
    if instance:break
    if compositor.poll() is not None:raise RuntimeError((base/'compositor.log').read_text()[-6000:])
    time.sleep(.1)
   assert instance,'No recording compositor';env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
   def ctl(*args):return subprocess.check_output(['hyprctl','-i',instance['instance'],*args],env=env,text=True,timeout=10).strip()
   time.sleep(.5)
   active=[m for m in json.loads(ctl('-j','monitors')) if m.get('width',0)>0 and not m.get('disabled')]
   if not active:ctl('output','create','headless','HICS-DEMO');time.sleep(.8)
   active=[m for m in json.loads(ctl('-j','monitors')) if m.get('width',0)>0 and not m.get('disabled')]
   assert active,'No usable recording output'
   recording_output=active[0]['name']
   errors=ctl('configerrors');assert not errors,errors
   # A private bus prevents notifications or settings calls from reaching the user's bus.
   runner=base/'runner.py';runner.write_text('import os,sys\nos.environ["DBUS_SYSTEM_BUS_ADDRESS"]=os.environ.get("HICS_RECORD_SYSTEM_BUS",os.environ["DBUS_SESSION_BUS_ADDRESS"])\nos.execvp(sys.argv[1],sys.argv[1:])\n')
   with (base/'shell.log').open('w') as log:qs=subprocess.Popen(['dbus-run-session','--','python3',str(runner),os.environ.get('HICS_TOUR_QS','/usr/share/hics/qs/bin/hics-qs' if Path('/usr/share/hics/qs/bin/hics-qs').is_file() else 'quickshell'),'-p',str(source)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   for _ in range(120):
    if 'Configuration Loaded' in (base/'shell.log').read_text():break
    if qs.poll() is not None:raise RuntimeError((base/'shell.log').read_text()[-10000:])
    time.sleep(.1)
   time.sleep(2)
   notes=['Заметки','Задачи','Терминал'] if language=='ru_RU' else ['Notes','Tasks','Terminal']
   content=['Проект hics\n\nОкна — там, где удобно.\nНастройки можно вернуть.\n\n• Панель и док\n• Рабочие проекты\n• История буфера','Сегодня\n\n✓ Настроить рабочий стол\n✓ Выбрать раскладки\n✓ Сохранить профиль\n\nМожно начинать работу.','hics\n\nДобро пожаловать!\n\nЧетыре режима окон,\nодин рабочий стол.'] if language=='ru_RU' else ['The hics project\n\nWindows where you need them.\nSettings you can recover.\n\n• Panel and dock\n• Workspace projects\n• Clipboard history','Today\n\n✓ Set up the desktop\n✓ Choose keyboard layouts\n✓ Save a profile\n\nReady to start working.','hics\n\nWelcome!\n\nFour window modes,\none desktop.']
   for i in range(3):
    script='printf %s '+__import__('shlex').quote(content[i])+'; sleep 600'
    app=subprocess.Popen(['kitty','--class','hics.demo.'+str(i),'--title',notes[i],'-o','confirm_os_window_close=0','-o','font_size=16','-o','background=#211f2b','-o','foreground=#e6e0f4','bash','-c',script],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);apps.append(app)
   for _ in range(80):
    windows=[w for w in json.loads(ctl('-j','clients')) if w['class'].startswith('hics.demo.')]
    if len(windows)==3:break
    time.sleep(.1)
   assert len(windows)==3,'Real demo applications did not map'
   sequence=0
   def command(**values):
    nonlocal sequence
    sequence+=1;tmp=control.with_suffix('.tmp');tmp.write_text(json.dumps({'sequence':sequence,**values}));os.replace(tmp,control);time.sleep(.2)
   def focus(index):ctl('eval','hl.dispatch(hl.dsp.focus({window=hl.get_window('+json.dumps('address:'+windows[index]['address'])+')}))')
   def positions():
    for i,w in enumerate(windows):ctl('eval','local w=hl.get_window('+json.dumps('address:'+w['address'])+');hl.dispatch(hl.dsp.window.resize({window=w,x=650,y=420,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x='+str(80+i*170)+',y='+str(90+i*45)+',relative=false}))')
   def settings(page):
    command(page=page);time.sleep(.5)
    client=next((w for w in json.loads(ctl('-j','clients')) if w.get('title') in ('Настройки','Settings')),None)
    if client:
     address=json.dumps('address:'+client['address'])
     ctl('eval','local w=hl.get_window('+address+');hl.dispatch(hl.dsp.window.resize({window=w,x=1120,y=620,relative=false}));hl.dispatch(hl.dsp.window.move({window=w,x=80,y=52,relative=false}))')
    time.sleep(.3)
   def shoot(name,action):
    nonlocal recorder
    path=base/name;path.mkdir();command(mode='stacking');time.sleep(.4);positions();focus(0);time.sleep(.3)
    stop=threading.Event();frames=[];capture_errors=[]
    def capture():
     while not stop.is_set():
      started=time.monotonic();image=path/(f'{len(frames):05d}.png')
      try:subprocess.run(['grim','-o',recording_output,str(image)],env=env,capture_output=True,check=True,timeout=4);frames.append((image,time.monotonic()))
      except Exception as error:capture_errors.append(str(error));return
      stop.wait(max(0,1/24-(time.monotonic()-started)))
    thread=threading.Thread(target=capture);thread.start()
    try:time.sleep(.3);action();time.sleep(.5)
    finally:stop.set();thread.join(timeout=6)
    assert not thread.is_alive() and not capture_errors and len(frames)>5,(capture_errors,len(frames))
    concat=path/'frames.txt';lines=[]
    for i,(image,stamp) in enumerate(frames):
     lines.append("file '"+str(image)+"'")
     lines.append('duration '+str((frames[i+1][1]-stamp) if i+1<len(frames) else .1))
    lines.append("file '"+str(frames[-1][0])+"'");concat.write_text('\n'.join(lines))
    dest=DEST/language/(name+'.gif');dest.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-filter_complex','fps=20,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192[p];[b][p]paletteuse=dither=sierra2_4a','-loop','0','-y',str(dest)],check=True,timeout=60)
    movie=dest.with_suffix('.mp4')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-vf','fps=24,scale=960:-2:flags=lanczos','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-an','-movflags','+faststart','-y',str(movie)],check=True,timeout=60)
    poster=movie.with_suffix('.jpg')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss','1','-i',str(movie),'-frames:v','1','-q:v','2','-y',str(poster)],check=True,timeout=20)
    manifest.append({'poster':str(poster.relative_to(ASSETS)),'posterSha256':hashlib.sha256(poster.read_bytes()).hexdigest(),'video':str(movie.relative_to(ASSETS)),'videoSha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'width':960,'fps':24,'id':name,'file':str(dest.relative_to(ASSETS)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'language':language,'source':'Production hics UI + real kitty windows in isolated Hyprland','size':dest.stat().st_size,'framesCaptured':len(frames),'capture':'Wayland screencopy via grim; timestamps retained'})
    print(language,name,dest.stat().st_size,flush=True)
   def mode_demo(mode):
    command(mode=mode);time.sleep(.8)
    for i in (1,2,0):focus(i);time.sleep(.55)
    if mode=='stacking':
     ctl('eval','hyprstack_layouts.action("minimize",'+json.dumps(windows[0]['address'])+')');time.sleep(.6);ctl('eval','hyprstack_layouts.action("focus",'+json.dumps(windows[0]['address'])+')');time.sleep(.5)
   def keyboard_demo():settings('keyboard');command(layout='ru',switchLayout='grp:alt_shift_toggle');time.sleep(1.5)
   def displays_demo():settings('display');command(display=24);time.sleep(1);command(revertDisplay=True);time.sleep(.6)
   def themes_demo():settings('themes');command(theme='light');time.sleep(1);command(theme='dark');time.sleep(1)
   def storage_demo():settings('storage');command(expandMemory=True);time.sleep(2)
   def features_demo():
    for text in content[:2]:subprocess.run([str(ROOT/'build/lib/hics-workspace'),'clipboard-store','text/plain'],input=text,env=env,text=True,check=True,capture_output=True)
    command(drawer='launcher');time.sleep(1);command(drawer='clipboard');time.sleep(1.5);command(closeDrawers=True)
   demos={**{mode:lambda mode=mode:mode_demo(mode) for mode in ('stacking','tiling','scrolling','canvas')},'keyboard':keyboard_demo,'displays':displays_demo,'themes':themes_demo,'storage':storage_demo,'features':features_demo}
   if 'onboarding' in only:
    import shlex
    fixtures=ROOT/'tests/fixtures'
    for flag,name in [('client-header','virtual-pointer.h'),('private-code','virtual-pointer-protocol.c')]:subprocess.run(['wayland-scanner',flag,str(fixtures/'wlr-virtual-pointer-unstable-v1.xml'),str(base/name)],check=True)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
    subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(base/'virtual-pointer-protocol.c'),'-I',str(base),*flags,'-o',str(base/'pointer')],check=True)
    pointer=subprocess.Popen([str(base/'pointer')],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert pointer.stdout.readline().strip()=='ready'
    def point(op,x,y):
     import select
     pointer.stdin.write(f'{op} {int(x)} {int(y)}'+chr(10));pointer.stdin.flush()
     assert select.select([pointer.stdout],[],[],4)[0],'Virtual pointer did not respond'
     assert pointer.stdout.readline().strip()=='ok'
    def inspect():
     command(probe=True);return json.loads(probe.read_text())
    for step in (2,3,7):
     command(setup=step);time.sleep(.9);before=inspect();assert before['height']>=700 and before['width']>=1200,before
     assert before['movieFrames']>0 and not before['movieError'],before
     assert before['skipVisible'] and before['skipForeground']!=before['skipBackground'],before
     assert before['skipY']>=0 and before['skipY']+before['skipHeight']<=before['height'],before
     if before['content']>before['viewport']+20:
      point('move',before['x'],before['y']);time.sleep(.2)
      for _ in range(3):point('wheel',0,1)
      time.sleep(.3);after=inspect();assert after['scroll']>before['scroll'],(step,before,after)
    print(language,'FULLSCREEN_CONTRAST_REAL_WHEEL_OK',flush=True)
    if language=='ru_RU':
     ctl('output','create','headless','HICS-TOUR-SECOND');time.sleep(.8)
     assert ctl('-j','layers').count('hyprstack-onboarding')>=2,'Secondary output was not covered'
     ctl('output','remove','HICS-TOUR-SECOND');time.sleep(.5)
     ctl('reload');time.sleep(.8);assert ctl('submap')=='hics-onboarding','Config reload disabled shortcut isolation'
     command(setup=3);command(display=24);time.sleep(.6)
     assert 'hyprstack-display-confirmation' in ctl('-j','layers'),'Protected display confirmation is inaccessible'
     command(revertDisplay=True);time.sleep(.6)
     print(language,'MULTI_OUTPUT_RELOAD_DISPLAY_CONFIRMATION_OK',flush=True)
    if os.environ.get('HICS_TOUR_PREVIEW'):subprocess.run(['grim','-o',recording_output,os.environ['HICS_TOUR_PREVIEW']+'-'+language+'.png'],env=env,check=True)
    for step in range(10):command(setup=step);time.sleep(.7)
    layers=ctl('-j','layers')
    assert 'hyprstack-onboarding' in layers,'Fullscreen setup layer did not map'
    assert ctl('submap')=='hics-onboarding','Compositor shortcuts were not isolated'
    assert 'hyprstack-drawers' not in layers,'Shell panels remained visible during setup'
    button=inspect();point('move',button['skipX']+button['skipWidth']/2,button['skipY']+button['skipHeight']/2);point('button',272,1);point('button',272,0);time.sleep(.5)
    for _ in range(30):
     if ctl('submap') in ('default','reset'):break
     time.sleep(.1)
    assert ctl('submap') in ('default','reset'),'Shortcut guard did not restore normal bindings'
    prefs=json.loads((cfg/'onboarding.json').read_text());assert prefs['state']=='skipped' and prefs['autoShow'] is False,prefs
    command(setup=2);time.sleep(.5);command(setupSkip=True);time.sleep(.5)
    print(language,'ONBOARDING_STEPS_SKIP_REPLAY_OK',flush=True)
    command(setup=0);time.sleep(.7);os.killpg(qs.pid,signal.SIGKILL);qs.wait()
    for _ in range(40):
     if ctl('submap') in ('default','reset'):break
     time.sleep(.1)
    assert ctl('submap') in ('default','reset'),'Shell crash left shortcuts blocked'
    print(language,'HARD_SHELL_CRASH_SHORTCUT_RECOVERY_OK',flush=True)
   for name,action in demos.items():
    if not only or name in only:shoot(name,action)
   if manifest:
    output=DEST/language/'manifest.json';old=json.loads(output.read_text()) if output.exists() else {'recordings':[]};old['recordings']=[r for r in old['recordings'] if r['id'] not in {m['id'] for m in manifest}]+manifest;old['version']=1;old['recorded']=int(time.time());output.write_text(json.dumps(old,ensure_ascii=False,indent=2))
   logs=(base/'shell.log').read_text();errors=[line for line in logs.splitlines() if any(s in line for s in ('TypeError:','ReferenceError:','DEMO_CONTROL_ERROR','Failed to load configuration'))]
   if errors:raise RuntimeError('\n'.join(errors[-20:]))
  except Exception:
   for name in ('compositor','shell','recorder'):
    path=base/(name+'.log')
    if path.exists():shutil.copy2(path,Path('/tmp')/('hics-tour-record-'+name+'.log'))
   raise
  finally:
   if pointer and pointer.poll() is None:pointer.terminate();pointer.wait(timeout=5)
   if recorder and recorder.poll() is None:recorder.kill();recorder.wait(timeout=5)
   if qs and qs.poll() is None:
    os.killpg(qs.pid,signal.SIGTERM)
    try:qs.wait(timeout=8)
    except subprocess.TimeoutExpired:os.killpg(qs.pid,signal.SIGKILL);qs.wait()
   for app in apps:
    if app.poll() is None:app.terminate()
   if compositor and compositor.poll() is None:
    compositor.terminate()
    try:compositor.wait(timeout=10)
    except subprocess.TimeoutExpired:compositor.kill();compositor.wait()

def main():
 p=argparse.ArgumentParser();p.add_argument('--languages',nargs='+',default=['ru_RU','en_US']);p.add_argument('--only',nargs='*',default=[]);args=p.parse_args()
 for language in args.languages:
  if language not in ('ru_RU','en_US'):raise ValueError('Unsupported recording language')
  record(language,args.only)
if __name__=='__main__':main()
