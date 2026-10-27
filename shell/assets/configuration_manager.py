"""Private configuration history and portable appearance profiles.

Credentials, clipboard contents and active monitor rules are excluded. Appearance
imports contain data only; their preview is rolled back by an independent worker.
"""
from __future__ import annotations
import argparse,copy,ctypes,fcntl,gzip,hashlib,json,math,os,re,selectors,signal,socket,struct,subprocess,sys,tempfile,time,uuid
from pathlib import Path
from feature_common import CONFIG,STATE,DATA,read_json,atomic_json,output
from application_environment import application_environment
from shell_recovery import read_text as bounded_text, strict_object, read as bounded_object
from plugin_preferences import load as load_plugin_preferences
FILES={'shell-tokens.json','window-controls.json','shell.json','tokens.json','dock.json','layouts.json','effects.json','keyboard.lua','system.lua','system-controls.json','device-rules.json','application-rules.json','rules.lua','theme-automation.json','live-wallpapers.json','display-profiles.json','notification-rules.json','workspace.json'}
APPEARANCE={'window-controls.json','shell.json','tokens.json','dock.json','layouts.json','effects.json','theme-automation.json','live-wallpapers.json','panels.json','state/scheme.json','state/wallpaper/path.txt','appearance.json','taskbar.json','workspaces.json','tiling.json','theme-schedule.json','widgets.json'}
HISTORY=STATE/'configuration-history';PROFILES=DATA/'appearance-profiles';PREFS=CONFIG/'configuration-history.json';JOURNAL=STATE/'configuration-preview.json'
MAX_BYTES=8*1024*1024
MAX_PREVIEW_BYTES=32*1024*1024
ASSETS=Path(__file__).resolve().parent

def allowed(name,appearance=False):
 if name in (APPEARANCE if appearance else FILES|APPEARANCE):return True
 return bool(re.fullmatch(r'monitors/[A-Za-z0-9_.-]{1,160}/(?:shell|tokens|shell-tokens)\.json',name))
def target(name):
 if not allowed(name):raise ValueError('Unsupported configuration section')
 return STATE/name.removeprefix('state/') if name.startswith('state/') else CONFIG/name

def gather(appearance=False):
 names=set(APPEARANCE if appearance else FILES|APPEARANCE)
 names.update(str(p.relative_to(CONFIG)) for p in (CONFIG/'monitors').glob('*/*.json') if allowed(str(p.relative_to(CONFIG))))
 files={};total=0
 for name in sorted(names):
  if name=='widgets.json':continue
  p=target(name)
  if not p.resolve().is_relative_to(STATE.resolve() if name.startswith('state/') else CONFIG.resolve()):raise ValueError('Unsafe configuration path: '+name)
  try:text=bounded_text(p,1048576)
  except FileNotFoundError:continue
  except (OSError,ValueError) as error:raise ValueError('Configuration is too large or unsafe for a safe snapshot: '+name) from error
  total+=len(text.encode('utf-8'))
  if total>MAX_BYTES:raise ValueError('Configuration is too large for a safe snapshot')
  if name.endswith('.json'):strict_object(text)
  files[name]=text
 if 'state/scheme.json' not in files:files['state/scheme.json']=(ASSETS/'feature_data/default-palette.json').read_text()
 if 'appearance.json' not in files:
  from appearance_themes import current
  files['appearance.json']=json.dumps(current(),ensure_ascii=False)
 files['widgets.json']=json.dumps({'desktopLayout':load_plugin_preferences(CONFIG/'plugins.json').get('desktopLayout',{})},ensure_ascii=False,sort_keys=True)
 if appearance:
  for name in APPEARANCE:
   if name not in files and name.endswith('.json'):files[name]='{}'
 return files

def complete_snapshot(files):
 # A checkpoint also records defaults for managed sections absent at capture,
 # so restoring it clears settings created after that checkpoint.
 result=dict(files)
 for name in FILES|APPEARANCE:
  if name not in result:
   result[name]='{}' if name.endswith('.json') else '-- Restored defaults by hics\n' if name.endswith('.lua') else ''
 return result

def digest(files):return hashlib.sha256(json.dumps(files,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write_text(path,text):
 path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name)
 try:
  with os.fdopen(fd,'w') as f:f.write(text);f.flush();os.fsync(f.fileno())
  os.chmod(tmp,0o600);os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

DEFAULT_POLICY={'enabled':True,'keep':40,'maxMiB':64,'captureOnLogin':True}

def read_preferences():
 try:return strict_object(bounded_text(PREFS,65536))
 except FileNotFoundError:return {}

def validate_preferences(raw):
 p={**DEFAULT_POLICY,**raw}
 if not isinstance(p['enabled'],bool) or not isinstance(p['captureOnLogin'],bool):raise ValueError('Invalid history setting')
 for k,lo,hi in (('keep',5,200),('maxMiB',8,256)):
  if isinstance(p[k],bool) or not isinstance(p[k],int) or not lo<=p[k]<=hi:raise ValueError('Invalid history limit')
 return p

def preferences():return validate_preferences(read_preferences())

def load_snapshot(path):
 if path.stat().st_size>MAX_BYTES:raise ValueError('Snapshot is too large')
 with gzip.open(path,'rb') as f:raw=f.read(MAX_BYTES+1)
 if len(raw)>MAX_BYTES:raise ValueError('Snapshot is too large')
 d=json.loads(raw);validate_bundle(d,False)
 if not isinstance(d.get('id'),str) or not re.fullmatch('[a-f0-9-]{36}',d['id']) or type(d.get('created')) not in (int,float) or not math.isfinite(d['created']) or d['created']<0:raise ValueError('Invalid history metadata')
 if not isinstance(d.get('hash'),str) or not re.fullmatch('[a-f0-9]{64}',d['hash']):raise ValueError('Invalid history checksum')
 return d

def validate_bundle(d,appearance=True):
 if not isinstance(d,dict) or not isinstance(d.get('name',''),str) or len(d.get('name',''))>128 or d.get('version')!=1 or not isinstance(d.get('files'),dict) or len(d['files'])>256:raise ValueError('Unsupported configuration bundle')
 total=0
 for name,text in d['files'].items():
  if not allowed(name,appearance) or not isinstance(text,str):raise ValueError('Bundle contains an unsupported section')
  total+=len(text.encode())
  if len(text.encode())>1048576 or total>MAX_BYTES:raise ValueError('Configuration bundle is too large')
  if name.endswith('.json'):
   val=json.loads(text,parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite configuration value')))
   if not isinstance(val,dict):raise ValueError('Configuration sections must be JSON objects')
   if name=='state/scheme.json':
    if val.get('mode') not in ('dark','light') or not isinstance(val.get('colours'),dict) or not val['colours']:raise ValueError('Invalid desktop palette')
    for role,color in val['colours'].items():
     if not isinstance(role,str) or not isinstance(color,str) or not re.fullmatch('[0-9a-fA-F]{6}',color):raise ValueError('Invalid palette colour')
   if name=='window-controls.json':
    from gtk_theme import validate_window_controls
    validate_window_controls(val)
   if name=='widgets.json':
    layouts=val.get('desktopLayout',{})
    if not isinstance(layouts,dict) or len(layouts)>128:raise ValueError('Invalid widget layout bundle')
    for plugin,screens in layouts.items():
     if not isinstance(screens,dict) or len(screens)>64:raise ValueError('Invalid widget screen layout')
     for screen,geometry in screens.items():
      if not isinstance(geometry,dict) or len(str(screen))>256:raise ValueError('Invalid widget geometry')
      for key,value in geometry.items():
       if key in ('locked','snap'):
        if not isinstance(value,bool):raise ValueError('Invalid widget switch')
       elif key in ('x','y','width','height','grid'):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not __import__('math').isfinite(value) or abs(value)>1000000:raise ValueError('Invalid widget coordinate')
       else:raise ValueError('Unknown widget geometry option')
   if name=='layouts.json' and val.get('mode','scrolling') not in ('canvas','stacking','tiling','scrolling'):raise ValueError('Invalid window mode')
 return d

def history():
 result=[]
 for path in HISTORY.glob('*.json.gz'):
  try:
   d=load_snapshot(path);result.append({k:d.get(k) for k in ('id','name','created','automatic','hash','sections')})
  except (OSError,ValueError,EOFError):continue
 return sorted(result,key=lambda d:d['created'],reverse=True)

def snapshot(name='Automatic checkpoint',automatic=True):
 settings=preferences()
 HISTORY.mkdir(parents=True,exist_ok=True,mode=0o700);files=complete_snapshot(gather());entries=history();h=digest(files)
 if automatic and entries and entries[0]['hash']==h:return entries[0]['id']
 identifier=str(uuid.uuid4());d=dict(version=1,id=identifier,name=str(name)[:128],created=time.time(),automatic=automatic,hash=h,sections=sorted(files),files=files)
 path=HISTORY/(identifier+'.json.gz');fd,tmp=tempfile.mkstemp(dir=HISTORY,prefix='.snapshot-')
 try:
  with os.fdopen(fd,'wb') as f:f.write(gzip.compress(json.dumps(d,ensure_ascii=False).encode(),compresslevel=5))
  os.chmod(tmp,0o600);os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 paths=sorted(HISTORY.glob('*.json.gz'),key=lambda p:p.stat().st_mtime,reverse=True);size=0
 for i,p in enumerate(paths):
  size+=p.stat().st_size
  if i>=settings['keep'] or size>settings['maxMiB']*1048576:p.unlink()
 return identifier

def identifier(value):
 if not isinstance(value,str) or not re.fullmatch('[a-f0-9-]{36}',value):raise ValueError('Invalid configuration identifier')
 return value

def profiles():
 result=[]
 for path in PROFILES.glob('*.json'):
  try:
   d=validate_bundle(json.loads(path.read_text()))
   result.append({k:d.get(k) for k in ('id','name','created','description','sections')})
  except (OSError,ValueError):continue
 return sorted(result,key=lambda d:d['created'],reverse=True)

def pack_wallpaper(bundle):
 bundle=copy.deepcopy(bundle);name='state/wallpaper/path.txt'
 path=Path(bundle['files'].get(name,'').strip())
 if path.is_file() and path.suffix.lower() in ('.jpg','.jpeg','.png','.webp') and path.stat().st_size<=4*1024*1024:
  import base64
  raw=path.read_bytes();bundle['wallpaperAsset']={'extension':path.suffix.lower(),'sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(raw).decode('ascii')}
 return bundle

def unpack_wallpaper(bundle):
 asset=bundle.get('wallpaperAsset')
 if not asset:return bundle
 import base64
 if not isinstance(asset,dict) or asset.get('extension') not in ('.jpg','.jpeg','.png','.webp') or not isinstance(asset.get('data'),str) or len(asset['data'])>6*1024*1024:raise ValueError('Invalid bundled wallpaper')
 try:raw=base64.b64decode(asset['data'],validate=True)
 except ValueError as error:raise ValueError('Invalid bundled wallpaper') from error
 h=hashlib.sha256(raw).hexdigest()
 if len(raw)>4*1024*1024 or h!=asset.get('sha256'):raise ValueError('Invalid bundled wallpaper checksum')
 # Validate image signatures; no SVG, executable content or decoder commands.
 if not (raw.startswith(b'\xff\xd8\xff') and asset['extension'] in ('.jpg','.jpeg') or raw.startswith(b'\x89PNG\r\n\x1a\n') and asset['extension']=='.png' or raw.startswith(b'RIFF') and raw[8:12]==b'WEBP' and asset['extension']=='.webp'):raise ValueError('Unsupported bundled image')
 folder=DATA/'profile-wallpapers';folder.mkdir(parents=True,exist_ok=True,mode=0o700);path=folder/(h+asset['extension'])
 if not path.exists():
  fd,tmp=tempfile.mkstemp(dir=folder)
  try:
   with os.fdopen(fd,'wb') as out:out.write(raw)
   os.chmod(tmp,0o600);os.replace(tmp,path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
 bundle=copy.deepcopy(bundle);bundle['files']['state/wallpaper/path.txt']=str(path);bundle.pop('wallpaperAsset',None);return bundle

def changes(files):
 before=gather();rows=[]
 for name,text in files.items():
  if before.get(name)!=text:
   row={'section':name,'changed':True,'beforeBytes':len(before.get(name,'').encode()),'afterBytes':len(text.encode())}
   if name.endswith('.json'):
    a=json.loads(before.get(name,'{}'));b=json.loads(text);row['keys']=[k for k in sorted(set(a)|set(b)) if a.get(k)!=b.get(k)]
   rows.append(row)
 return rows

def apply_files(files,runtime_apply=True,persist=True):
 files=dict(files)
 if 'application-rules.json' in files or 'device-rules.json' in files:
  from desktop_rules import regenerate
  apps=json.loads(files.get('application-rules.json',(CONFIG/'application-rules.json').read_text() if (CONFIG/'application-rules.json').exists() else '{}')).get('rules',[])
  devs=json.loads(files.get('device-rules.json',(CONFIG/'device-rules.json').read_text() if (CONFIG/'device-rules.json').exists() else '{}')).get('devices',[])
  files['rules.lua']=regenerate(apps,devs)
 if 'window-controls.json' in files:
  from gtk_theme import validate_window_controls
  validate_window_controls(json.loads(files['window-controls.json']))
 for name,text in (files.items() if persist else ()):
  if name=='widgets.json':
   prefs=read_json(CONFIG/'plugins.json');prefs['desktopLayout']=json.loads(text).get('desktopLayout',{});atomic_json(CONFIG/'plugins.json',prefs,private=True)
  else:write_text(target(name),text)
 # The compositor owns window geometry; display profiles are restored as data
 # only. Active outputs always go through display_profiles.py confirmation.
 if not runtime_apply:return
 if 'window-controls.json' in files:
  from gtk_theme import sync_window_controls
  sync_window_controls(CONFIG.parent)
 if 'layouts.json' in files:
  mode=json.loads(files['layouts.json']).get('mode','scrolling')
  if mode:subprocess.run(['hyprctl','eval','hyprstack_layouts.set_mode('+json.dumps(mode)+')'],env=application_environment(),capture_output=True,timeout=8,check=True)
 if 'window-controls.json' in files or 'system.lua' in files or 'keyboard.lua' in files or 'rules.lua' in files or 'tiling.json' in files or 'workspaces.json' in files:
  subprocess.run(['hyprctl','reload'],env=application_environment(),capture_output=True,timeout=10,check=True)
 if 'effects.json' in files:
  subprocess.run(['hyprctl','eval','if hyprstack_layouts then hyprstack_layouts.shadows() end'],env=application_environment(),capture_output=True,timeout=8,check=True)
 if 'appearance.json' in files:
  from appearance_themes import apply
  saved=json.loads(files['appearance.json'])
  for kind in ('icons','cursors'):
   if saved.get(kind):apply(kind,saved[kind],int(saved.get('size',24)))
 if 'state/wallpaper/path.txt' in files:
  path=files['state/wallpaper/path.txt'].strip()
  if path:subprocess.run(['hics','wallpaper','-f',path,'--no-smart'],env=application_environment(),capture_output=True,check=True,timeout=30)
 if 'state/scheme.json' in files:
  from theme_manager import save_current
  save_current(json.loads(files['state/scheme.json']))

def merge_revert(before,applied,current):
 # Retain unrelated edits made while a preview was open.
 result=copy.deepcopy(current)
 for key in set(before)|set(applied):
  if key not in applied:
   if key not in current and key in before:result[key]=before[key]
  elif isinstance(applied[key],dict) and isinstance(before.get(key),dict) and isinstance(current.get(key),dict):result[key]=merge_revert(before[key],applied[key],current[key])
  elif current.get(key)==applied.get(key):
   if key in before:result[key]=before[key]
   else:result.pop(key,None)
 return result

PREVIEW_WARNING='Invalid configuration-preview.json. Original journal preserved; automatic rollback is paused.'

def read_preview():
 try:d=strict_object(bounded_text(JOURNAL,MAX_PREVIEW_BYTES))
 except FileNotFoundError:return {}
 if not isinstance(d.get('token'),str) or not 1<=len(d['token'])<=128 or not isinstance(d.get('name'),str) or len(d['name'])>128:raise ValueError(PREVIEW_WARNING)
 for key in ('deadline','deadlineMonotonic'):
  value=d.get(key)
  if type(value) not in (int,float) or not 0<=value<=1e12:raise ValueError(PREVIEW_WARNING)
 before=d.get('before');applied=d.get('applied')
 if not isinstance(before,dict) or not isinstance(applied,dict) or not applied or len(applied)>256 or set(before)!=set(applied):raise ValueError(PREVIEW_WARNING)
 total=0
 for name,text in applied.items():
  if not allowed(name) or not isinstance(text,str):raise ValueError(PREVIEW_WARNING)
  for value in (text,before[name]):
   if value is None:continue
   if not isinstance(value,str):raise ValueError(PREVIEW_WARNING)
   size=len(value.encode());total+=size
   if size>1048576 or total>2*MAX_BYTES:raise ValueError(PREVIEW_WARNING)
   if name.endswith('.json'):strict_object(value)
 absent=d.get('absent',[])
 if not isinstance(absent,list) or any(not isinstance(name,str) or name not in applied for name in absent):raise ValueError(PREVIEW_WARNING)
 pid=d.get('shellPid');start=d.get('shellStart')
 if pid is not None and (type(pid) is not int or not 0<pid<2**31):raise ValueError(PREVIEW_WARNING)
 if start is not None and (not isinstance(start,str) or not start.isascii() or not start.isdigit() or len(start)>32):raise ValueError(PREVIEW_WARNING)
 return d

def preview_present():return JOURNAL.exists() or JOURNAL.is_symlink()

WARNING_IO_FAILURES={}
PENDING_WARNINGS={}

def diagnostic_stderr(message):
 try:print(message,file=sys.stderr,flush=True)
 except OSError:pass

def io_warning(source,error):
 reason=(error.strerror or 'I/O error') if isinstance(error,OSError) else 'I/O error'
 message=source+': '+reason
 if WARNING_IO_FAILURES.get(source)!=message:diagnostic_stderr(message)
 WARNING_IO_FAILURES[source]=message

def persist_warning(message,source):
 path=STATE/'configuration-recovery-warning.json'
 try:previous=bounded_object(path)
 except (OSError,ValueError):previous={}
 try:
  if previous.get('warning')!=message:atomic_json(path,{'warning':message},private=True)
 except OSError as error:
  PENDING_WARNINGS[source]=message;io_warning(source,error)
 else:
  PENDING_WARNINGS.pop(source,None);WARNING_IO_FAILURES.pop(source,None)

def warn_preview():persist_warning(PREVIEW_WARNING,'Preview diagnostics write failed')


ROLLBACK_FAILURE=''

def report_rollback_failure(error):
 global ROLLBACK_FAILURE
 detail=error.strerror if isinstance(error,OSError) else str(error)[:256]
 message='Automatic rollback failed: '+str(detail)+'. Original journal preserved for retry.'
 if message!=ROLLBACK_FAILURE:diagnostic_stderr(message)
 ROLLBACK_FAILURE=message


def rollback(runtime_apply=True):
 global ROLLBACK_FAILURE
 d=read_preview()
 if not d:
  ROLLBACK_FAILURE=''
  return
 from shell_recovery import read_text as bounded_text, strict_object
 restored={};remove_defaults=set();warnings=[]
 absent=d.get('absent',[])
 if not isinstance(absent,list):absent=[]
 for name,applied in d['applied'].items():
  p=target(name);before=d['before'].get(name)
  try:
   if name=='widgets.json':current=gather().get(name)
   else:
    try:current=bounded_text(p,1048576)
    except FileNotFoundError:current=None
   if current is not None and name.endswith('.json'):strict_object(current)
  except (OSError,ValueError):
   warnings.append(name+': Changed section could not be read safely; left untouched')
   continue
  default=before if before is not None else '{}' if name.endswith('.json') else '-- Restored defaults by hics\n' if name.endswith('.lua') else ''
  if name!='widgets.json' and (before is None or name in absent) and current==default:
   # An earlier attempt may have persisted defaults before a later write failed.
   restored[name]=default;remove_defaults.add(name)
   continue
  if current==applied:
   if name!='widgets.json' and (before is None or name in absent):remove_defaults.add(name)
   if before is None:
    restored[name]='{}' if name.endswith('.json') else '-- Restored defaults by hics\n' if name.endswith('.lua') else ''
   else:restored[name]=before
  elif name.endswith('.json') and current is not None:
   try:restored[name]=json.dumps(merge_revert(json.loads(before or '{}'),json.loads(applied),json.loads(current)),ensure_ascii=False,indent=2)
   except ValueError:pass
 apply_files(restored,False)
 try:
  if runtime_apply:apply_files(restored,True,False)
 except (OSError,subprocess.SubprocessError,ValueError) as error:warnings.append(str(error))
 if warnings:persist_warning('; '.join(warnings),'Rollback diagnostics write failed')
 # Runtime application needs defaults, but an abandoned trial must also
 # restore the original absence of files. Keep edits made during rollback.
 for name in remove_defaults:
  path=target(name)
  try:current=bounded_text(path,1048576)
  except (OSError,ValueError):continue
  if current==restored[name]:path.unlink(missing_ok=True)
 JOURNAL.unlink(missing_ok=True)
 ROLLBACK_FAILURE=''

def presets():
 return [dict(id=k,name=n,description=desc,files={'layouts.json':json.dumps({'mode':mode}),'dock.json':json.dumps({'enabled':dock,'position':'bottom'}),'shell.json':json.dumps({'bar':{'persistent':bar},'appearance':{'reducedMotion':reduced}})}) for k,n,desc,mode,dock,bar,reduced in [
 ('laptop','Laptop','Compact controls and restrained motion','scrolling',True,True,False),('workstation','Workstation','Persistent panel and a spatial canvas','canvas',True,True,False),('classic','Classic','Stacking windows and a bottom dock','stacking',True,True,False),('minimal','Minimal','An unobtrusive panel and keyboard navigation','scrolling',False,False,False)]]

def make_preset(key):
 preset=next((p for p in presets() if p['id']==key),None)
 if not preset:raise ValueError('Unknown appearance preset')
 files={}
 for name,text in preset['files'].items():
  current=json.loads(target(name).read_text()) if target(name).is_file() else {}
  def merge(a,b):
   for k,v in b.items():
    if isinstance(v,dict):a[k]=merge(a.get(k,{}) if isinstance(a.get(k),dict) else {},v)
    else:a[k]=v
   return a
  files[name]=json.dumps(merge(current,json.loads(text)),ensure_ascii=False,indent=2)
 return dict(version=1,name=preset['name'],files=files)

def startup_checkpoint():
 try:
  from shell_recovery import good
  saved=good(STATE/'shell-startup-good.json')
  return {'available':bool(saved),'created':saved.get('created',0),'sections':list(saved.get('files',{}))}
 except (OSError,ValueError):return {'available':False,'error':'Startup checkpoint is damaged'}

def state():
 try:pending=read_preview();pending_valid=True;preview_warning=''
 except (OSError,ValueError):pending={};pending_valid=False;preview_warning=PREVIEW_WARNING
 try:settings=preferences();valid=True;policy_warning=''
 except (OSError,ValueError):
  settings={**DEFAULT_POLICY,'enabled':False};valid=False
  policy_warning='Invalid configuration-history.json; automatic checkpoints paused. Original settings preserved.'
 try:
  warning=bounded_object(STATE/'configuration-recovery-warning.json').get('warning','')
  if not isinstance(warning,str):raise ValueError('Invalid warning')
 except (OSError,ValueError):warning='Configuration recovery warning could not be read safely.'
 return {'startupCheckpoint':startup_checkpoint(),'statePath':str(runtime()/'state.json'),'settings':settings,'settingsValid':valid,'history':history(),'profiles':profiles(),'presets':[{k:v for k,v in p.items() if k!='files'} for p in presets()], 'pending':{k:v for k,v in pending.items() if k in ('token','deadline','name')},'pendingValid':pending_valid,'directory':str(HISTORY),'recoveryWarning':'; '.join(filter(None,[policy_warning,preview_warning,ROLLBACK_FAILURE,warning,*WARNING_IO_FAILURES.values()]))}

def dispatch(op,p,shell_pid=None):
 if op=='status':return state()
 if op=='configure':
  if not isinstance(p,dict) or set(p)-{'enabled','keep','maxMiB','captureOnLogin'}:raise ValueError('Unknown history setting')
  previous=read_preferences();old={**previous,**p};validate_preferences(old)
  atomic_json(PREFS,old,private=True)
 elif op=='mark-startup':
  from shell_recovery import candidate,healthy
  if not healthy(candidate()):raise ValueError('Configuration changed while recording checkpoint')
 elif op=='snapshot':snapshot(p.get('name','Checkpoint'),False)
 elif op=='delete-history':(HISTORY/(identifier(p['id'])+'.json.gz')).unlink()
 elif op=='save-profile':
  name=p.get('name','').strip()
  if not name or len(name)>128:raise ValueError('Enter a profile name')
  files=gather(True);d=dict(version=1,id=str(uuid.uuid4()),name=name,created=time.time(),sections=sorted(files),files=files)
  if len(profiles())>=64:raise ValueError('At most 64 appearance profiles are supported')
  atomic_json(PROFILES/(d['id']+'.json'),d,private=True)
 elif op in ('inspect-profile','preview-profile','inspect-history','restore-history','restore-startup','preset','inspect-import','import-profile'):
  if op=='restore-startup':
   from shell_recovery import good
   d=good(STATE/'shell-startup-good.json')
   if not d:raise ValueError('No working startup checkpoint is available')
   d={**d,'name':'Working startup configuration'}
   # The preview must survive the intentional transition from the recovery UI
   # to the normal shell. The independent 30-second deadline still applies.
   shell_pid=None
  elif op=='preset':d=make_preset(p['id'])
  elif 'import' in op:
   path=Path(p['path']).expanduser()
   if not path.is_file() or path.stat().st_size>MAX_BYTES:raise ValueError('Choose a supported local configuration bundle')
   d=validate_bundle(json.loads(path.read_text()))
   if op=='import-profile':d=unpack_wallpaper(d)
  elif 'history' in op:d=load_snapshot(HISTORY/(identifier(p['id'])+'.json.gz'))
  else:d=validate_bundle(read_json(PROFILES/(identifier(p['id'])+'.json')))
  if op.startswith('inspect'):return {**state(),'preview':{'name':d.get('name','Profile'),'sections':changes(d['files']),'files':list(d['files'])}}
  if op=='import-profile':
   d.update(id=str(uuid.uuid4()),created=time.time(),sections=sorted(d['files']));atomic_json(PROFILES/(d['id']+'.json'),d,private=True)
   return {**state(),'importedId':d['id']}
  else:
   if preview_present():raise ValueError('Confirm or revert the current appearance preview first')
   from display_profiles import paths as display_paths
   try:display_folder,_=display_paths()
   except ValueError:display_folder=None
   if display_folder and read_json(display_folder/'pending.json'):raise ValueError('Confirm display changes before previewing a desktop profile')
   files=d['files'];selected=p.get('sections',list(files))
   if not isinstance(selected,list) or not selected or set(selected)-set(files):raise ValueError('Select configuration sections to restore')
   files={name:files[name] for name in selected};before=gather();snapshot('Before '+d.get('name','restore'),False)
   journal=dict(token=str(uuid.uuid4()),name=d.get('name','Profile'),deadline=time.time()+30,deadlineMonotonic=time.monotonic()+30,shellPid=shell_pid,shellStart=process_start(shell_pid),before={k:before.get(k) for k in files},absent=[k for k in files if k!='widgets.json' and not (target(k).exists() or target(k).is_symlink())],applied=files)
   if len(json.dumps(journal,ensure_ascii=False,indent=2).encode())>MAX_PREVIEW_BYTES:raise ValueError('Configuration preview journal exceeds 32 MiB')
   atomic_json(JOURNAL,journal,private=True)
   try:apply_files(files)
   except Exception:rollback();raise
 elif op in ('confirm','revert'):
  pending=read_preview()
  if not pending or pending['token']!=p.get('token'):raise ValueError('The configuration preview has expired')
  if op=='revert' or pending['deadlineMonotonic']<=time.monotonic():rollback()
  else:JOURNAL.unlink();snapshot('Confirmed '+pending['name'],False)
 elif op=='delete-profile':(PROFILES/(identifier(p['id'])+'.json')).unlink()
 elif op=='export-profile':
  d=validate_bundle(read_json(PROFILES/(identifier(p['id'])+'.json')));dest=Path(p['path']).expanduser()
  if not dest.is_absolute():raise ValueError('Choose an absolute export path')
  d=pack_wallpaper(d)
  encoded=json.dumps(d,ensure_ascii=False,indent=2)
  if len(encoded.encode())>MAX_BYTES:raise ValueError('Portable profile is too large')
  write_text(dest,encoded)
 else:raise ValueError('Unknown configuration operation')
 return state()

def repair_invalid_json():
 # A malformed JSON file must not prevent the guard (or next login) starting.
 # Keep the original privately before restoring the latest valid checkpoint.
 names=(FILES|APPEARANCE)-{'widgets.json'}
 latest=None
 for name in sorted(names):
  if not name.endswith('.json'):continue
  path=target(name)
  if not path.is_file() or path.is_symlink():continue
  try:
   if path.stat().st_size>1048576:raise ValueError('Configuration section is too large')
   parsed=json.loads(path.read_text(),parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite configuration value')))
   if not isinstance(parsed,dict):raise ValueError('Expected configuration object')
  except (ValueError,UnicodeError):
   if latest is None:
    entries=history();latest=load_snapshot(HISTORY/(entries[0]['id']+'.json.gz'))['files'] if entries else {}
    from shell_recovery import good
    try:latest.update(good(STATE/'shell-startup-good.json').get('files',{}))
    except (OSError,ValueError):pass
   folder=STATE/'configuration-recovery';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
   saved=folder/(str(time.time_ns())+'-'+name.replace('/','_')+'.invalid')
   os.replace(path,saved)
   try:write_text(path,latest.get(name,'{}'))
   except BaseException:
    os.replace(saved,path);raise
   atomic_json(STATE/'configuration-recovery-warning.json',{'warning':'Invalid configuration restored: '+name,'original':str(saved)},private=True)

def process_start(pid):
 try:
  path=Path('/proc')/str(pid)
  if path.stat().st_uid!=os.getuid():return None
  return (path/'stat').read_text().rsplit(')',1)[1].split()[19]
 except (OSError,IndexError):return None

def runtime():
 root=Path(os.environ.get('XDG_RUNTIME_DIR','/run/user/'+str(os.getuid())))/('hics-configuration-'+hashlib.sha256(str(CONFIG.resolve()).encode()).hexdigest()[:12]);root.mkdir(mode=0o700,parents=True,exist_ok=True)
 if root.is_symlink() or root.stat().st_uid!=os.getuid():raise ValueError('Unsafe configuration runtime directory')
 return root

def configuration_event_relevant(data,watch_paths):
 # Failed atomic writes still create/unlink temporary files. They are not
 # configuration edits and must not schedule another attempt on a full disk.
 offset=0
 while offset+16<=len(data):
  descriptor,mask,cookie,length=struct.unpack_from('iIII',data,offset)
  end=offset+16+length
  if end>len(data):return True
  name=data[offset+16:end].split(b'\0',1)[0];offset=end
  if watch_paths.get(descriptor)==STATE and name.startswith(b'.configuration-recovery-warning.json'):continue
  return True
 return offset!=len(data)


def watch():
 root=runtime();CONFIG.mkdir(parents=True,exist_ok=True);STATE.mkdir(parents=True,exist_ok=True)
 with (root/'watch.lock').open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  preview_broken=False;rollback_retry_at=0;rollback_failures=0
  try:read_preview()
  except (OSError,ValueError):warn_preview();preview_broken=True
  else:
   try:rollback()
   except (OSError,ValueError) as error:
    report_rollback_failure(error);rollback_failures=1;rollback_retry_at=time.monotonic()+2
  endpoint=root/'control.sock';endpoint.unlink(missing_ok=True)
  with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
   server.bind(str(endpoint));os.chmod(endpoint,0o600);server.listen(8)
   libc=ctypes.CDLL(None,use_errno=True);fd=libc.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
   if fd<0:raise OSError(ctypes.get_errno(),'Cannot watch configuration')
   watch_paths={}
   def arm():
    for path in [CONFIG,STATE,STATE/'wallpaper',CONFIG/'monitors',*(CONFIG/'monitors').glob('*')]:
     if path.is_dir() and not path.is_symlink():
      descriptor=libc.inotify_add_watch(fd,os.fsencode(path),0x00000008|0x00000080|0x00000100|0x00000200)
      if descriptor>=0:watch_paths[descriptor]=path
   arm();stopping=False;changed=0;last_hash=None;paused_warning=None
   def stop(*_):
    nonlocal stopping
    stopping=True
   signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
   def observe(startup=False):
    nonlocal last_hash,paused_warning
    try:
     repair_invalid_json();current=digest(gather());policy=preferences()
     if policy['enabled'] and not preview_present() and (policy['captureOnLogin'] if startup else current!=last_hash):snapshot()
     last_hash=current
     if paused_warning:
      warning=STATE/'configuration-recovery-warning.json'
      try:previous=bounded_object(warning)
      except (OSError,ValueError):previous={}
      if previous.get('warning')==paused_warning:warning.unlink(missing_ok=True)
      paused_warning=None
      PENDING_WARNINGS.pop('Capture diagnostics write failed',None);WARNING_IO_FAILURES.pop('Capture diagnostics write failed',None)
    except (OSError,ValueError,TypeError) as error:
     message='Configuration history capture paused: '+str(error);paused_warning=message
     persist_warning(message,'Capture diagnostics write failed')
   observe(True)
   def publish():
    for source,message in list(PENDING_WARNINGS.items()):persist_warning(message,source)
    previous=WARNING_IO_FAILURES.pop('Runtime state write failed',None)
    try:atomic_json(root/'state.json',state(),private=True)
    except OSError as error:
     if previous:WARNING_IO_FAILURES['Runtime state write failed']=previous
     io_warning('Runtime state write failed',error)
   publish()
   events=None
   signature=os.environ.get('HYPRLAND_INSTANCE_SIGNATURE','')
   if signature and '/' not in signature:
    events=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);events.connect(str(Path(os.environ['XDG_RUNTIME_DIR'])/'hypr'/signature/'.socket2.sock'))
   with selectors.DefaultSelector() as select:
    if events:select.register(events,selectors.EVENT_READ)
    select.register(server,selectors.EVENT_READ);select.register(fd,selectors.EVENT_READ)
    while not stopping:
     try:
      pending=read_preview()
      if preview_broken:
       path=STATE/'configuration-recovery-warning.json'
       try:warning=bounded_object(path)
       except (OSError,ValueError):warning={}
       if warning.get('warning')==PREVIEW_WARNING:path.unlink(missing_ok=True)
       preview_broken=False
       PENDING_WARNINGS.pop('Preview diagnostics write failed',None);WARNING_IO_FAILURES.pop('Preview diagnostics write failed',None)
     except (OSError,ValueError):
      pending={}
      if not preview_broken:warn_preview()
      preview_broken=True
     if pending and time.monotonic()>=rollback_retry_at and (pending['deadlineMonotonic']<=time.monotonic() or pending.get('shellPid') and process_start(pending['shellPid'])!=pending.get('shellStart')):
      try:rollback()
      except (OSError,ValueError) as error:
       report_rollback_failure(error);rollback_failures+=1
       rollback_retry_at=time.monotonic()+min(30,2**min(rollback_failures,5))
      else:rollback_failures=0;rollback_retry_at=0
      publish()
     if changed and time.monotonic()>=changed:
      changed=0;observe();publish()
     for key,_ in select.select(.5 if pending or changed else 1):
      if events and key.fileobj is events:
       if not events.recv(65536):
        try:rollback(False)
        except (OSError,ValueError) as error:report_rollback_failure(error)
        os.close(fd);events.close();return
      elif key.fileobj==fd:
       data=os.read(fd,262144)
       if configuration_event_relevant(data,watch_paths):arm();changed=time.monotonic()+.7
      else:
       with server.accept()[0] as client:
        request_deadline=time.monotonic()+2
        client.settimeout(2)
        try:
         raw=b''
         while b'\n' not in raw:
          remaining=request_deadline-time.monotonic()
          if remaining<=0:raise TimeoutError('Configuration request exceeded its time limit')
          client.settimeout(remaining)
          part=client.recv(16384)
          if not part or len(raw)+len(part)>65536:raise ValueError('Invalid configuration request')
          raw+=part
         req=json.loads(raw.split(b'\n',1)[0]);result=dispatch(req['operation'],req.get('value') or {},req.get('shellPid'));publish()
        except Exception as e:result={'error':str(e)}
        try:client.sendall((json.dumps(result,ensure_ascii=False)+'\n').encode())
        except OSError:pass
   try:rollback()
   except (OSError,ValueError) as error:report_rollback_failure(error)
   os.close(fd)
   if events:events.close()

def request(op,p):
 endpoint=runtime()/'control.sock'
 def send():
  with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
   c.settimeout(45);c.connect(str(endpoint));pid=os.getppid();comm=Path('/proc')/str(pid)/'comm';shell_pid=pid if comm.exists() and comm.read_text().strip() in ('hics-qs','quickshell') else None;c.sendall((json.dumps({'operation':op,'value':p,'shellPid':shell_pid})+'\n').encode());data=b''
   while b'\n' not in data:
    part=c.recv(65536)
    if not part:raise ValueError('Configuration service disconnected')
    data+=part
    if len(data)>MAX_BYTES:raise ValueError('Configuration response is too large')
   return json.loads(data.split(b'\n',1)[0])
 try:return send()
 except (FileNotFoundError,ConnectionRefusedError):
  managed=False
  if not os.environ.get('HICS_CONFIG_NO_SYSTEMD'):
   managed=subprocess.run(['systemctl','--user','start','hics-configuration.service'],capture_output=True,timeout=8).returncode==0
  if not managed:subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'watch'],env=application_environment(),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  for _ in range(100):
   try:return send()
   except (FileNotFoundError,ConnectionRefusedError):time.sleep(.05)
  raise ValueError('Configuration service did not become ready')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('operation');args=parser.parse_args()
 try:
  if args.operation=='watch':watch();return 0
  result=request(args.operation,json.load(sys.stdin) if args.operation!='status' else {});output(result);return 1 if result.get('error') else 0
 except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':sys.exit(main())
