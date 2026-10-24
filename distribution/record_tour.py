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
  if 'interactions' in only:
   originals=Path.home()/'Изображения/Wallpapers/hics-collection/.originals';target=base/'wallpapers/hics-collection/.originals';target.mkdir(parents=True)
   for image in originals.glob('*.jxl'):shutil.copy2(image,target/image.name)
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
   if(c.inspectMenuValue!==undefined){
    const win=onboardingWizard.instances.find(w=>w.primary);
    function findValue(node){if(node.modelData?.value===c.inspectMenuValue&&node.modelData?.text!==undefined&&node.visible)return node;for(const child of node.children??[]){const found=findValue(child);if(found)return found;}return null;}
    const item=findValue(win.contentItem);let view=item?.parent;while(view&&view.contentHeight===undefined)view=view.parent;
    const p=item?.mapToItem(win.contentItem,0,0);const v=view?.mapToItem(win.contentItem,0,0);
    demoProbe.setText(JSON.stringify({exists:!!item,x:p?.x,y:p?.y,width:item?.width,height:item?.height,vx:v?.x,vy:v?.y,vw:view?.width,vh:view?.height}));
   }
   if(c.inspectText){
    const win=onboardingWizard.instances.find(w=>w.primary);
    function findText(item){if(item.text===c.inspectText&&item.visible)return item;for(const child of item.children??[]){const found=findText(child);if(found)return found;}return null;}
    const label=findText(win.contentItem);const item=label?.parent?.parent;const point=item?.mapToItem(win.contentItem,0,0);
    demoProbe.setText(JSON.stringify({exists:!!item,x:point?.x,y:point?.y,width:item?.width,height:item?.height}));
   }
   if(c.inspectControl){
    const win=onboardingWizard.instances.find(w=>w.primary);const item=findDemo(win.contentItem,c.inspectControl);const region=findDemo(win.contentItem,"onboarding-region");const loader=findDemo(win.contentItem,"onboarding-body");const f=loader?.item?.flickable;
    if(item&&c.revealControl&&f){const point=item.mapToItem(f.contentItem,0,0);f.cancelFlick();f.contentY=Math.max(-f.topMargin,Math.min(f.contentHeight-f.height+f.bottomMargin,point.y-24));loader.item.preferredContentY=f.contentY;}
    function dropdown(node){if(node.expandBtn&&node.menuItems!==undefined)return node;for(const child of node.children??[]){const found=dropdown(child);if(found)return found;}return null;}
    const hit=item?.field??(item?.spec?.type==="choice"?dropdown(item)?.expandBtn:null)??(item?.settingsCard&&item.collapsible?item.frame?.children[0]:null)??item;const p=hit?.mapToItem(win.contentItem,0,0);demoProbe.setText(JSON.stringify({exists:!!item,x:p?.x,y:p?.y,width:hit?.width,height:hit?.height,text:item?.field?.text,focus:item?.field?.activeFocus,query:region?.query,matches:region?.matches?.map(l=>l.id),selected:region?.selected,current:region?.currentLocale,busy:region?.busy,error:region?.error,succeeded:region?.succeeded,expanded:item?.expanded,menuExpanded:item?.spec?.type==="choice"?dropdown(item)?.expanded:undefined,memoryTotal:findDemo(win.contentItem,"storage-memory-settings")?.live?.total??0,wallpapers:Onboarding.data.wallpapers??[],downloading:Onboarding.downloading,step:Onboarding.step,language:Tr.language,keyboardError:KeyboardConf.error,keyboardBusy:KeyboardConf.busy,layouts:KeyboardConf.layoutCodes,variants:KeyboardConf.variantByLayout,usVariants:KeyboardConf.variantsFor("us"),switchOption:KeyboardConf.switchOption,mode:LayoutModes.mode,theme:Colours.scheme,light:Colours.currentLight}));
   }
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
  if 'onboarding' not in only:
   a=injection.index('   if(c.inspectMenuValue');b=injection.index('   if(c.probe)',a);injection=injection[:a]+injection[b:]
   injection=injection.replace('if(c.probe)root.reportSetup();','').replace(next(l for l in injection.splitlines() if l.startswith(' function reportSetup()')),'')
  shell=shell[:shell.rfind('}')]+injection+'\n}';(source/'shell.qml').write_text(shell)
  lua=base/'hyprland.lua';lua.write_text('package.path='+json.dumps(str(ASSETS/'hyprland/config/?.lua')+';')+'..package.path\npackage.preload["scheme.current"]=function() return require("scheme.default") end\nhl.monitor({output="",mode="1280x720@60",position="auto",scale=1})\nhl.config({input={kb_layout="us",follow_mouse=0},misc={disable_watchdog_warning=true,disable_hyprland_logo=true,disable_splash_rendering=true}})\ndofile('+json.dumps(str(ASSETS/'hyprland/config/hyprland/animations.lua'))+')\ndofile('+json.dumps(str(ASSETS/'hyprland/config/hyprland/gestures.lua'))+')\ndofile('+json.dumps(str(ASSETS/'hyprland/layouts.lua'))+')\n')
  with lua.open('a') as output:output.write('local p='+json.dumps(str(cfg/'keyboard.lua'))+';local f=io.open(p);if f then f:close();dofile(p) end'+chr(10))
  env=dict(os.environ,HOME=str(home),AQ_BACKEND='headless',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),XDG_CURRENT_DESKTOP='Hyprland',HYPRSTACK_DATA_DIR=str(base),HICS_DATA_DIR=str(base),HYPRSTACK_NESTED='1',HICS_NO_ONBOARDING='1',HICS_CONFIG_NO_SYSTEMD='1',HICS_DISPLAY_NO_SYSTEMD='1',QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'),QT_QPA_PLATFORM='wayland',LANG='ru_RU.UTF-8' if language=='ru_RU' else 'en_US.UTF-8',HYPRSTACK_LANGUAGE=language,HICS_WORKSPACE_HELPER=str(ROOT/'build/lib/hics-workspace'))
  env['HICS_RECORD_SYSTEM_BUS']=os.environ.get('DBUS_SYSTEM_BUS_ADDRESS','unix:path=/run/dbus/system_bus_socket')
  if 'interactions' in only:
   assert os.environ.get('HICS_TEST_REGION_PROXY'),'Provide the scoped privileged test proxy'
   tools=base/'tools';tools.mkdir();shutil.copy2(os.environ['HICS_TEST_REGION_PROXY'],tools/'hics-systemctl');(tools/'hics-systemctl').chmod(0o700);env['PATH']=str(tools)+':'+env['PATH']
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
   # Keep this test-owned Wayland backend window out of the parent's tiling.
   # Resizing a parent tiled viewport otherwise invalidates pointer coordinates.
   host_signature=os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
   if host_signature:
    for _ in range(30):
     host_clients=json.loads(subprocess.check_output(['hyprctl','-i',host_signature,'-j','clients'],text=True))
     parent=next((w for w in host_clients if w.get('pid')==compositor.pid),None)
     if parent:break
     time.sleep(.1)
    if parent:
     address=json.dumps('address:'+parent['address'])
     subprocess.run(['hyprctl','-i',host_signature,'eval','local w=hl.get_window('+address+');if w then hl.dispatch(hl.dsp.window.float({window=w,action="enable"}));hl.dispatch(hl.dsp.window.resize({window=w,x=1280,y=720,relative=false})) end'],capture_output=True,check=True)

   time.sleep(.5)
   active=[m for m in json.loads(ctl('-j','monitors')) if m.get('width',0)>0 and not m.get('disabled')]
   if not active:ctl('output','create','headless','HICS-DEMO');time.sleep(.8)
   active=[m for m in json.loads(ctl('-j','monitors')) if m.get('width',0)>0 and not m.get('disabled')]
   assert active,'No usable recording output'
   recording_output=active[0]['name']
   canvas_plugin=base/'native/libspatialoverview.so'
   if canvas_plugin.is_file():
    result=ctl('plugin','load',str(canvas_plugin));assert 'error' not in result.lower(),result;time.sleep(.6)
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
    if 'interactions' in only:
     for flag,name in [('client-header','virtual-keyboard.h'),('private-code','virtual-keyboard-protocol.c')]:subprocess.run(['wayland-scanner',flag,str(fixtures/'virtual-keyboard.xml'),str(base/name)],check=True)
     keyboard_source=(fixtures/'virtual-keyboard.c').read_text().replace('1u<<xkb_keymap_mod_get_index(map,XKB_MOD_NAME_LOGO)','0')
     (base/'keyboard.c').write_text(keyboard_source)
     flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client','xkbcommon'],text=True))
     subprocess.run(['cc',str(base/'keyboard.c'),str(base/'virtual-keyboard-protocol.c'),'-I',str(base),*flags,'-o',str(base/'keyboard')],check=True)
     def key(code):subprocess.run([str(base/'keyboard'),str(code)],env=env,check=True)
     def inspectControl(name,reveal=True):
      command(inspectControl=name,revealControl=reveal);time.sleep(.2);command(inspectControl=name);return json.loads(probe.read_text())
     def click(name):
      c=inspectControl(name);assert c['exists'],(name,c);point('move',c['x']+c['width']/2,c['y']+c['height']/2);point('button',272,1);point('button',272,0);time.sleep(.2)
     command(setup=1);time.sleep(1)
     click('locale-search')
     for code in (18,49,34,38,23,31,35):key(code)
     c=inspectControl('locale-search',False);assert c['query']=='english' and 'en_US.UTF-8' in c['matches'],c
     print(language,'REAL_LOCALE_TEXT_SEARCH_OK',flush=True)
     click('locale-choice-en_US.UTF-8');c=inspectControl('locale-selection');assert c['selected']=='en_US.UTF-8',c
     Path(os.environ['HICS_TEST_REGION_MODE']).write_text('denied')
     click('locale-apply')
     for _ in range(30):
      c=inspectControl('locale-selection',False)
      if c.get('error'):break
      time.sleep(.1)
     assert c.get('error') and c['selected']=='en_US.UTF-8' and c['step']==1,c
     Path(os.environ['HICS_TEST_REGION_MODE']).write_text('')
     print(language,'LOCALE_DENIAL_PRESERVES_SELECTION_OK',flush=True)
     # The root test bridge permits only the original locale, so use the
     # current locale for a real, idempotent system-generation request.
     click('locale-search')
     key(107)
     for _ in range(7):key(14)
     for code in (19,22):key(code)
     c=inspectControl('locale-search',False);assert c['query']=='ru' and 'ru_RU.UTF-8' in c['matches'],c
     click('locale-choice-ru_RU.UTF-8');click('locale-apply')
     for _ in range(120):
      c=inspectControl('locale-selection',False)
      if c.get('succeeded') or c.get('error'):break
      time.sleep(.1)
     assert c.get('succeeded') and c.get('current')=='ru_RU.UTF-8',c
     print(language,'REAL_NATIVE_LOCALE_APPLY_OK',flush=True)
     click('tour-language-en');c=inspectControl('locale-selection',False);assert c['language']=='en_US',c
     click('tour-language-ru');c=inspectControl('locale-selection',False);assert c['language']=='ru_RU',c
     if language=='en_US':
      click('tour-language-en');click('locale-choice-ru_RU.UTF-8')
     assert json.loads((cfg/'shell.json').read_text())['general']['language']==language
     print(language,'SHELL_LANGUAGE_CLICK_PERSISTENCE_OK',flush=True)
     click('onboarding-next')
     for _ in range(60):
      c=inspectControl('tour-layout-switch',False)
      if c['step']==2:break
      time.sleep(.1)
     assert c['step']==2,c
     print(language,'LOCALE_CONTINUE_AFTER_SUCCESS_OK',flush=True)
     command(setup=2);time.sleep(.7)
     click('tour-add-layout-ru');time.sleep(.5);c=inspectControl('tour-layout-switch',False);assert c['layouts']==['us','ru'],c
     click('tour-layout-switch')
     time.sleep(.2)
     # Pick the actual menu row by its label; do not invoke the setting method.
     command(inspectText='Alt+Shift');row=json.loads(probe.read_text());assert row['exists'],row
     point('move',row['x']+row['width']/2,row['y']+row['height']/2);point('button',272,1);point('button',272,0);time.sleep(.8)
     c=inspectControl('tour-layout-switch',False);assert c['switchOption']=='grp:alt_shift_toggle',c
     assert 'grp:alt_shift_toggle' in (cfg/'keyboard.lua').read_text()
     assert 'grp:alt_shift_toggle' in ctl('repl','return hl.get_config("input.kb_options")')
     assert 'us,ru' in ctl('repl','return hl.get_config("input.kb_layout")')
     variants=c['usVariants'];assert variants,'No US keyboard variants'
     last_variant=variants[-1]['code']
     click('tour-layout-variant-us');key(1);c=inspectControl('tour-layout-variant-us',False);assert c['step']==2 and not c.get('menuExpanded'),c
     click('tour-layout-variant-us')
     for _ in range(12):
      command(inspectMenuValue=last_variant);option=json.loads(probe.read_text());assert option['exists'],option
      if option['y']>=option['vy'] and option['y']+option['height']<=option['vy']+option['vh']:break
      point('move',option['vx']+option['vw']/2,option['vy']+option['vh']/2)
      for _ in range(15):point('wheel',0,1)
     assert option['y']>=option['vy'] and option['y']+option['height']<=option['vy']+option['vh'],option
     point('move',option['x']+option['width']/2,option['y']+option['height']/2);point('button',272,1);point('button',272,0);time.sleep(.5)
     c=inspectControl('tour-layout-variant-us',False);assert c['variants'].get('us')==last_variant,c
     assert last_variant in (cfg/'keyboard.lua').read_text()
     click('tour-layout-variant-us')
     command(inspectMenuValue='');option=json.loads(probe.read_text())
     point('move',option['vx']+option['vw']/2,option['vy']+option['vh']/2)
     for _ in range(100):point('wheel',0,-1)
     command(inspectMenuValue='');option=json.loads(probe.read_text())
     point('move',option['x']+option['width']/2,option['y']+option['height']/2);point('button',272,1);point('button',272,0);time.sleep(.5)
     c=inspectControl('tour-layout-variant-us',False);assert not c['variants'].get('us'),c
     print(language,'LONG_VARIANT_MENU_REAL_SCROLL_SELECTION_RESET_OK',flush=True)
     before_keyboard=(cfg/'keyboard.lua').read_bytes()
     cfg.chmod(0o500)
     try:
      click('tour-add-layout-de')
      for _ in range(40):
       c=inspectControl('tour-keyboard-retry',False)
       if c.get('keyboardError'):break
       time.sleep(.1)
      assert c.get('keyboardError') and (cfg/'keyboard.lua').read_bytes()==before_keyboard,c
     finally:cfg.chmod(0o700)
     click('tour-keyboard-retry')
     for _ in range(40):
      c=inspectControl('tour-layout-switch',False)
      if not c.get('keyboardBusy') and not c.get('keyboardError') and 'us,ru,de' in (cfg/'keyboard.lua').read_text():break
      time.sleep(.1)
     assert not c.get('keyboardError') and 'us,ru,de' in (cfg/'keyboard.lua').read_text(),c
     click('tour-remove-layout-de');time.sleep(.6)
     print(language,'KEYBOARD_SAVE_FAILURE_PRESERVES_FILE_AND_RETRY_OK',flush=True)
     click('tour-remove-layout-ru');time.sleep(.5);c=inspectControl('tour-layout-switch',False);assert c['layouts']==['us'],c
     print(language,'MULTI_LAYOUT_ADD_SWITCH_REMOVE_PERSISTENCE_OK',flush=True)
     command(setup=4);time.sleep(.4)
     for mode in ('tiling','scrolling','canvas','stacking'):
      click('tour-mode-'+mode)
      for _ in range(30):
       c=inspectControl('tour-mode-'+mode,False)
       if c['mode']==mode:break
       time.sleep(.1)
      assert c['mode']==mode,c
      assert json.loads((cfg/'layouts.json').read_text())['mode']==mode
     print(language,'FOUR_WINDOW_MODE_REAL_BUTTONS_PERSISTENCE_OK',flush=True)
     command(setup=5);time.sleep(.6)
     for name,light in [('light',True),('dark',False)]:
      click('tour-theme-'+name)
      for _ in range(50):
       c=inspectControl('tour-theme-'+name,False)
       if c['light']==light:break
       time.sleep(.1)
      assert c['light']==light,c
      assert json.loads((state/'scheme.json').read_text())['mode']==name
     print(language,'LIGHT_DARK_REAL_BUTTONS_PERSISTENCE_OK',flush=True)
     command(setup=6);time.sleep(.5);click('tour-wallpaper-download')
     for _ in range(150):
      c=inspectControl('tour-wallpaper-download',False)
      if len(c['wallpapers'])==14 and not c['downloading']:break
      time.sleep(.1)
     assert len(c['wallpapers'])==14 and not c['downloading'],c
     wallpaper=c['wallpapers'][0];click('tour-wallpaper-'+wallpaper['name'])
     for _ in range(50):
      if (state/'wallpaper/path.txt').read_text().strip()==wallpaper['path']:break
      time.sleep(.1)
     assert (state/'wallpaper/path.txt').read_text().strip()==wallpaper['path']
     assert (base/'wallpapers/hics-collection/LICENSE.txt').is_file()
     print(language,'WALLPAPER_COLLECTION_CONVERSION_SELECTION_PERSISTENCE_OK',flush=True)
     command(setup=7);time.sleep(.6);click('storage-memory-compression');time.sleep(.5)
     c=inspectControl('storage-memory-compression',False);assert c.get('expanded') and c.get('memoryTotal',0)>0,c
     click('storage-memory-compression');time.sleep(.4)
     c=inspectControl('storage-memory-compression',False);assert c.get('expanded') is False,c
     print(language,'STORAGE_MEMORY_EXPAND_METRICS_COLLAPSE_OK',flush=True)
     command(setup=0)
     for step in range(1,10):
      click('onboarding-next')
      for _ in range(30):
       c=inspectControl('onboarding-next',False)
       if c['step']==step:break
       time.sleep(.1)
      assert c['step']==step,c
      if step==8:
       click('tour-feature-clipboard');c=inspectControl('tour-inspection',False);assert c['exists'],c
       click('onboarding-back');c=inspectControl('tour-feature-clipboard',False);assert c['exists'] and c['step']==8,c
     click('onboarding-next');time.sleep(.5)
     assert json.loads((cfg/'onboarding.json').read_text())['state']=='completed'
     assert 'hyprstack-onboarding' not in ctl('-j','layers')
     print(language,'REAL_NEXT_BACK_INSPECTION_FINISH_OK',flush=True)
     os.killpg(qs.pid,signal.SIGTERM);qs.wait(timeout=8)
     ctl('reload');time.sleep(.5);control.write_text('{}')
     log_size=(base/'shell.log').stat().st_size
     with (base/'shell.log').open('a') as log:qs=subprocess.Popen(['dbus-run-session','--','python3',str(runner),os.environ.get('HICS_TOUR_QS','/usr/share/hics/qs/bin/hics-qs'),'-p',str(source)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
     for _ in range(120):
      if 'Configuration Loaded' in (base/'shell.log').read_text()[log_size:]:break
      if qs.poll() is not None:raise AssertionError((base/'shell.log').read_text()[log_size:])
      time.sleep(.1)
     time.sleep(.8);command(setup=2);time.sleep(.6)
     c=inspectControl('tour-layout-switch',False)
     assert c['layouts']==['us'] and c['switchOption']=='grp:alt_shift_toggle' and c['light'] is False,c
     assert (state/'wallpaper/path.txt').read_text().strip()==wallpaper['path']
     print(language,'RESTART_RELOAD_RESTORES_SAVED_CHOICES_OK',flush=True)
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
   if compositor and compositor.poll() is None:
    try:subprocess.run(['grim','/tmp/hics-onboarding-actions-failure.png'],env=env,capture_output=True,timeout=5)
    except Exception:pass
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
