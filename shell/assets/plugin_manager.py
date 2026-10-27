#!/usr/bin/env python3
"""Hyprstack extensions: atomic installs, lifecycle preferences and API detection.

Manifest lifecycle and entry-point design inspired by AngelOS (MixaDoDs, MIT).
Noctalia 4 QML and Noctalia 5 Luau are deliberately different compatibility levels.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,sys,tempfile,tomllib,urllib.request,urllib.parse,zipfile
from pathlib import Path
from feature_common import CONFIG,DATA,STATE,read_json,atomic_json,output
from plugin_preferences import load as load_preferences
from shell_recovery import read_text as bounded_text, strict_object
ASSETS=Path(__file__).resolve().parent
BUNDLED=ASSETS.parent/'plugins';USER=DATA/'plugins';PREFS=CONFIG/'plugins.json';TRASH=STATE/'plugin-trash'
ID=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$')
ALLOWED_IMPORTS={'QtQuick','QtQuick.Layouts','QtQuick.Controls','QtQuick.Controls.Basic','QtQuick.Effects','QtQml','QtQml.Models','Quickshell','Quickshell.Io','Quickshell.Widgets','Quickshell.Hyprland','Quickshell.Wayland','Hyprstack.Config','Hyprstack.I18n','qs.components','qs.components.controls','qs.services','qs.utils','qs.Commons','qs.Widgets','qs.Services'}
SUPPORTED_COMMONS={'Color','Style','I18n','Logger','Settings'}
SUPPORTED_SERVICES={'PluginService','ToastService','WallpaperService','NoctaliaService'}
SUPPORTED_WIDGETS={'NText','NIcon','NButton','NIconButton','NBox','NToggle','NSlider','NTextInput','NSpinBox','NLabel','NDivider'}

class HttpsRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts=None):self.hosts=hosts
    def validate(self,url):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or self.hosts and parsed.hostname not in self.hosts:
            raise ValueError('Extension download redirected outside the allowed HTTPS origin')
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        self.validate(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def https_open(request,timeout,hosts=None):
    redirects=HttpsRedirects(hosts)
    redirects.validate(request.full_url if isinstance(request,urllib.request.Request) else request)
    return urllib.request.build_opener(redirects).open(request,timeout=timeout)


def text(v):
    if isinstance(v,str):return v
    if isinstance(v,dict):return text(v.get('ru',v.get('en',next(iter(v.values()),''))))
    return ''
def checked_path(root,name):
    p=(root/str(name)).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file():raise ValueError('Plugin entry points must be files inside the plugin folder')
    return p

def qml_files(folder):
    # Bound directory enumeration as well as source bytes; never follow links.
    pending=[(folder,0)];visited=0
    while pending:
        directory,depth=pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                visited+=1
                if visited>4096:raise ValueError('Extension source tree exceeds 4096 entries')
                if entry.is_symlink():raise ValueError('Extension source tree contains a symlink')
                if entry.is_dir(follow_symlinks=False):
                    if depth>=32:raise ValueError('Extension source tree is too deep')
                    pending.append((Path(entry.path),depth+1))
                elif entry.name.endswith('.qml'):
                    yield Path(entry.path)


def manifest(folder,bundled=False):
    folder=Path(folder).resolve()
    try:document=bounded_text(folder/'manifest.json',2097152)
    except FileNotFoundError:
        try:raw=tomllib.loads(bounded_text(folder/'plugin.toml',2097152))
        except FileNotFoundError:raise ValueError('No manifest.json or plugin.toml')
        fmt='noctalia-luau'
    else:
        raw=strict_object(document)
        fmt='native' if (str(raw.get('api','')).startswith('hics-') or raw.get('api')=='hyprstack-1') else 'noctalia-qml' if 'entryPoints' in raw else 'angelos'
    for key in ('entryPoints','metadata','permissions'):
        if key in raw and not isinstance(raw[key],dict):raise ValueError('Invalid manifest object: '+key)
    for key in ('setting','settingsSchema','dependencies'):
        if key in raw and not isinstance(raw[key],list):raise ValueError('Invalid manifest list: '+key)
    original=str(raw.get('id',folder.name));identifier=re.sub(r'[^A-Za-z0-9_.-]','-',original)
    if not ID.fullmatch(identifier):raise ValueError('Invalid plugin ID')
    entries={};issues=[];settings=[]
    sources={};source_bytes=0
    def source_text(path):
        nonlocal source_bytes
        if path not in sources:
            code=bounded_text(path,2*1024*1024)
            source_bytes+=len(code.encode('utf-8'))
            if source_bytes>16*1024*1024:raise ValueError('Extension QML sources exceed 16 MiB')
            sources[path]=code
        return sources[path]
    isolated=raw.get('api')=='hics-2'
    if fmt=='native' and raw.get('api') not in ('hics-1','hyprstack-1','hics-2'):issues.append('Unsupported hics API version')
    worker=''
    if isolated:
        worker=str(checked_path(folder,raw.get('worker','worker.py')))
        if not worker.endswith('.py'):issues.append('Isolated workers require a Python entry point')
        if not shutil.which('bwrap'):issues.append('Missing dependency: bwrap')
    if fmt=='native':source=raw.get('entryPoints',{})
    elif fmt=='angelos':source={k:raw.get(k) for k in ['main','barWidget','desktopWidget','settings','panel']}
    elif fmt=='noctalia-qml':source=raw.get('entryPoints',{})
    else:source={};issues.append('Noctalia 5 Luau API '+str(raw.get('plugin_api','?'))+' requires a Luau host; QML entry points cannot execute this format.')
    if fmt=='angelos':
        # The manifest can be imported; visual QML must use Hyprstack/compatibility tokens.
        for file in qml_files(folder):
            if 'qs.config' in source_text(file):issues.append('AngelOS-specific qs.config/Skin imports require a visual port.');break
    for key,name in source.items():
        if key not in ('main','barWidget','desktopWidget','settings','panel') or not name:continue
        if isolated:
            entries[key]={'format':'declarative','url':'','property':'pluginApi','requiredProperties':[]}
            continue
        p=checked_path(folder,name);code=source_text(p)
        prop='pluginApi' if re.search(r'property\s+\w+\s+pluginApi\b',code) else 'plugin' if re.search(r'property\s+\w+\s+plugin\b',code) else ''
        entries[key]={'url':p.as_uri(),'property':prop,'requiredProperties':re.findall(r'required\s+property\s+\w+\s+(\w+)',code)}
    if fmt=='noctalia-qml':
        for file in qml_files(folder):
            code=source_text(file)
            for imp in re.findall(r'^\s*import\s+([\w.]+)',code,re.M):
                if imp not in ALLOWED_IMPORTS:issues.append('Unsupported QML module: '+imp)
            for name in re.findall(r'\b([A-Z]\w*)\.',code):
                if name in {'Quickshell','Qt','Text','Item','Image','Math','JSON','String','ListView','Flickable','Easing','Process','FileView','StdioCollector','Font','Screen','TextInput','TextEdit','Timer','MouseArea','Component','Layout','Loader','PopupAnchor','WlrLayershell','WlrLayer','Edges'}:continue
                if re.search(r'\b'+name+r'\s*\{',code):continue
                # Fail known Noctalia service namespaces, not imported Qt constants.
                if name.endswith('Service') and name not in SUPPORTED_SERVICES:issues.append('Unsupported service: '+name)
            if 'qs.Widgets' in code:
                for name in re.findall(r'\b(N[A-Z]\w*)\s*\{',code):
                    if name not in SUPPORTED_WIDGETS:issues.append('Unsupported Noctalia widget: '+name)
            if 'qs.Commons' in code:
                for name in re.findall(r'\b([A-Z]\w*)\.',code):
                    if name in ('Color','Style','I18n','Logger','Settings'):continue
                    if name in ('BarService','ColorSchemeService','DesktopService','ScreenService'):issues.append('Unsupported Noctalia API: '+name)
    for spec in raw.get('setting',raw.get('settingsSchema',[])):
        if not isinstance(spec,dict) or not spec.get('key'):continue
        kind={'bool':'bool','int':'int','float':'number','string':'string','select':'choice'}.get(spec.get('type'),spec.get('type','string'))
        settings.append({**spec,'type':kind,'label':spec.get('label',spec.get('key'))})
    if isinstance(raw.get('metadata',{}).get('defaultSettings'),dict):
        for key,value in raw['metadata']['defaultSettings'].items():settings.append({'key':key,'label':key,'type':'bool' if isinstance(value,bool) else 'number' if isinstance(value,(float,int)) else 'json' if isinstance(value,(dict,list)) else 'string','default':value})
    missing=[x for x in raw.get('dependencies',[]) if isinstance(x,str) and not shutil.which(x)]
    for name in missing:issues.append('Missing dependency: '+name)
    adapter='wallpaper-engine' if fmt=='noctalia-luau' and original=='tadomika_ari/w-engine' else ''
    return dict(api=raw.get('api','legacy'),isolated=isolated,worker=worker,networkRequested=bool((raw.get('permissions') if isinstance(raw.get('permissions'),dict) else {}).get('network',False)),id=identifier,originalId=original,name=text(raw.get('name',identifier)),description=text(raw.get('description','')),version=str(raw.get('version','1.0.0')),author=text(raw.get('author','')),license=raw.get('license',''),format=fmt,bundled=bundled,path=str(folder.resolve()),entryPoints=entries,settingsSchema=settings,issues=sorted(set(issues)),compatible=not issues,adapter=adapter,icon=raw.get('icon','extension'),actions=raw.get('actions',raw.get('menu',[])),source=raw.get('source',''))

def scan():
    errors=[]
    try:prefs=load_preferences(PREFS)
    except ValueError as error:
        prefs={'recoveryMode':True,'recoveryReason':str(error)};errors.append(str(error))
    found={}
    for directory,bundled in [(BUNDLED,True),(USER,False)]:
        for folder in sorted(directory.glob('*')):
            if not folder.is_dir() or folder.is_symlink():continue
            try:
                m=manifest(folder,bundled);m['enabled']=m['compatible'] and prefs.get('enabled',{}).get(m['id'],False) and (not prefs.get('recoveryMode',False) or prefs.get('recoveryAllow',{}).get(m['id'],False))
                defaults={s['key']:s.get('default') for s in m['settingsSchema']};m['settings']={**defaults,**prefs.get('settings',{}).get(m['id'],{})};m['desktopLayout']=prefs.get('desktopLayout',{}).get(m['id'],{});m['networkGranted']=bool(prefs.get('permissions',{}).get(m['id'],{}).get('network',False));found[m['id']]=m
            except (OSError,ValueError,TypeError,KeyError) as e:errors.append(f'{folder.name}: {e}')
    removed=[]
    for folder in sorted(TRASH.glob('*')):
        if not folder.is_dir() or folder.is_symlink():continue
        try:
            m=manifest(folder);removed.append({'id':m['id'],'name':m['name'],'version':m['version']})
        except (OSError,ValueError,TypeError,KeyError):pass
    for m in found.values():m['backupCount']=len(list((STATE/'plugin-backups'/m['id']).glob('*')))
    return {'plugins':list(found.values()),'removed':removed,'errors':errors,'directory':str(USER),'legacyNoctaliaApi':'QML subset','noctalia5':'Luau manifests and settings; native W Engine adapter','recoveryMode':bool(prefs.get('recoveryMode',False)),'recoveryReason':prefs.get('recoveryReason',''),'faults':prefs.get('faults',{})}

def find(identifier):
    result=next((p for p in scan()['plugins'] if p['id']==identifier),None)
    if not result:raise ValueError('Plugin not found')
    return result

def enable(identifier,value):
    plugin=find(identifier)
    if value and not plugin['compatible']:raise ValueError('; '.join(plugin['issues']))
    p=load_preferences(PREFS);p.setdefault('enabled',{})[identifier]=value
    if p.get('recoveryMode'):p.setdefault('recoveryAllow',{})[identifier]=value
    atomic_json(PREFS,p);return scan()

def save_settings(identifier,values):
    plugin=find(identifier)
    if not isinstance(values,dict):raise ValueError('Expected settings object')
    for spec in plugin['settingsSchema']:
        if spec['key'] not in values:continue
        v=values[spec['key']]
        if spec['type']=='bool' and not isinstance(v,bool):raise ValueError('Expected boolean: '+spec['key'])
        if spec['type'] in ('int','number'):
            if isinstance(v,bool) or not isinstance(v,(int,float)):raise ValueError('Expected number: '+spec['key'])
            if spec.get('min') is not None and v<spec['min'] or spec.get('max') is not None and v>spec['max']:raise ValueError('Out of range: '+spec['key'])
    p=load_preferences(PREFS);p.setdefault('settings',{})[identifier]=values;atomic_json(PREFS,p);return scan()

def fault(identifier, payload):
    import time
    find(identifier)
    message=payload.get('error','')
    if not isinstance(message,str) or not message or len(message)>16384:raise ValueError('Invalid extension error')
    prefs=load_preferences(PREFS)
    history=prefs.setdefault('faults',{}).setdefault(identifier,[])
    history.append({'time':int(time.time()),'error':message})
    prefs['faults'][identifier]=history[-50:]
    prefs.setdefault('enabled',{})[identifier]=False
    atomic_json(PREFS,prefs)
    return scan()

def recovery(enabled):
    prefs=load_preferences(PREFS);prefs['recoveryMode']=enabled;prefs['recoveryAllow']={}
    if not enabled:prefs['recoveryReason']=''
    atomic_json(PREFS,prefs)
    return scan()

def catalogue(source=''):
    entries=[];warnings=[]
    for item in scan()['plugins']:
        if item['bundled']:
            entries.append({k:item[k] for k in ('id','name','description','version','icon','path','compatible','issues')})
    if source:
        if urllib.parse.urlsplit(source).scheme!='https':raise ValueError('Catalogues require an HTTPS URL')
        request=urllib.request.Request(source,headers={'User-Agent':'hics-extension-catalogue/1'})
        with https_open(request,timeout=10) as response:
            if urllib.parse.urlsplit(response.url).scheme!='https':raise ValueError('Catalogue redirected outside HTTPS')
            raw=response.read(2097153)
        if len(raw)>2097152:raise ValueError('Extension catalogue is too large')
        document=json.loads(raw)
        if not isinstance(document,dict) or document.get('version')!=1 or not isinstance(document.get('extensions'),list):raise ValueError('Unsupported extension catalogue format')
        for item in document['extensions'][:1000]:
            if not isinstance(item,dict) or not ID.fullmatch(str(item.get('id',''))):raise ValueError('Invalid catalogue extension')
            if urllib.parse.urlsplit(item.get('source','')).scheme!='https':raise ValueError('Catalogue extension sources require HTTPS')
            entry={k:text(item.get(k,''))[:4096] for k in ('id','name','description','version','icon','source','preview')}
            if entry['preview'] and urllib.parse.urlsplit(entry['preview']).scheme!='https':raise ValueError('Catalogue previews require HTTPS')
            entry['dependencies']=item.get('dependencies',[]) if isinstance(item.get('dependencies',[]),list) else []
            entries.append(entry)
    return {'catalogue':entries,'warnings':warnings}

def desktop_layout(identifier, payload):
    import math
    find(identifier)
    screen=payload.get('screen')
    geometry=payload.get('geometry')
    if not isinstance(screen,str) or not screen or len(screen)>256 or not isinstance(geometry,dict):raise ValueError('Invalid desktop layout')
    bounds={'x':(-65536,65536),'y':(-65536,65536),'width':(64,16384),'height':(48,16384),'grid':(4,128)}
    for key,value in geometry.items():
        if key in ('locked','snap'):
            if not isinstance(value,bool):raise ValueError('Invalid widget switch')
        elif key in bounds:
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not bounds[key][0]<=value<=bounds[key][1]):raise ValueError('Invalid widget geometry: '+key)
        else:raise ValueError('Unknown widget geometry field')
    prefs=load_preferences(PREFS)
    layouts=prefs.setdefault('desktopLayout',{}).setdefault(identifier,{})
    updated=dict(layouts.get(screen,{}))
    for key,value in geometry.items():
        if value is None:updated.pop(key,None)
        else:updated[key]=value
    layouts[screen]=updated
    atomic_json(PREFS,prefs)
    return scan()

def github_folder(source, destination):
    u=urllib.parse.urlparse(source)
    parts=u.path.strip('/').split('/')
    if u.hostname!='github.com' or len(parts)<2: return False
    owner,repo=parts[:2];branch=parts[3] if len(parts)>3 and parts[2]=='tree' else 'HEAD'
    sub='/'.join(parts[4:]) if len(parts)>3 and parts[2]=='tree' else ''
    total=0;entries=0
    def fetch(path, dest, depth=0):
        nonlocal total,entries
        if depth>32:raise ValueError('GitHub plugin tree is too deep')
        url='https://api.github.com/repos/'+urllib.parse.quote(owner)+'/'+urllib.parse.quote(repo)+'/contents/'+urllib.parse.quote(path)+'?ref='+urllib.parse.quote(branch,safe='')
        with https_open(urllib.request.Request(url,headers={'User-Agent':'hics/1'}),timeout=20,hosts={'api.github.com'}) as response:
            if urllib.parse.urlsplit(response.url).scheme!='https':raise ValueError('GitHub API redirected outside HTTPS')
            document=response.read(2*1024*1024+1)
        if len(document)>2*1024*1024:raise ValueError('GitHub directory response exceeds 2 MiB')
        items=json.loads(document)
        if not isinstance(items,list):raise ValueError('Choose a GitHub plugin folder')
        dest.mkdir(parents=True,exist_ok=True)
        names=set()
        for item in items:
            entries+=1
            if entries>4096:raise ValueError('GitHub plugin exceeds 4096 entries')
            if not isinstance(item,dict):raise ValueError('Invalid GitHub directory entry')
            name=item.get('name','')
            if not isinstance(name,str) or not name or name in ('.','..') or '/' in name or '\\' in name or '\0' in name or name in names:raise ValueError('Invalid GitHub path')
            names.add(name)
            expected=path+'/'+name if path else name
            if item.get('path')!=expected:raise ValueError('Unexpected GitHub entry path')
            if item.get('type')=='dir':fetch(expected,dest/name,depth+1)
            elif item.get('type')=='file':
                url=item.get('download_url','')
                origin=urllib.parse.urlsplit(url)
                if origin.scheme!='https' or origin.hostname!='raw.githubusercontent.com':raise ValueError('Unexpected download origin')
                target=dest/name;created=False
                try:
                    with https_open(url,timeout=20,hosts={'raw.githubusercontent.com'}) as response:
                        final=urllib.parse.urlsplit(response.url)
                        if final.scheme!='https' or final.hostname!='raw.githubusercontent.com':raise ValueError('Unexpected download redirect')
                        with target.open('xb') as output:
                            created=True
                            while True:
                                chunk=response.read(min(65536,32*1024*1024-total+1))
                                if not chunk:break
                                total+=len(chunk)
                                if total>32*1024*1024:raise ValueError('Plugin exceeds 32 MiB')
                                output.write(chunk)
                except Exception:
                    if created:target.unlink(missing_ok=True)
                    raise
            else:raise ValueError('Plugin folder contains unsupported links')
    fetch(sub,destination)
    return True


def install(source, update=False):
    USER.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.install-',dir=USER.parent) as work:
        root=Path(work);path=Path(source).expanduser()
        if path.is_dir():candidate=path
        elif source.startswith('https://github.com/') and not source.endswith('.zip'):
            candidate=root/'github';github_folder(source,candidate)
        else:
            archive=root/'plugin.zip'
            if source.startswith('https://'):
                req=urllib.request.Request(source,headers={'User-Agent':'Hyprstack/1'})
                with https_open(req,timeout=30) as r,archive.open('wb') as f:
                    if urllib.parse.urlsplit(r.url).scheme!='https':raise ValueError('Plugin archive redirected outside HTTPS')
                    total=0
                    while chunk:=r.read(65536):
                        total+=len(chunk)
                        if total>32*1024*1024:raise ValueError('Plugin archive exceeds 32 MiB')
                        f.write(chunk)
            else:shutil.copyfile(path,archive)
            extract=root/'unpacked';extract.mkdir()
            with zipfile.ZipFile(archive) as z:
                if sum(x.file_size for x in z.infolist())>128*1024*1024:raise ValueError('Expanded plugin exceeds 128 MiB')
                for item in z.infolist():
                    dest=(extract/item.filename).resolve()
                    if not dest.is_relative_to(extract) or (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe archive entry')
                z.extractall(extract)
            candidates=[p.parent for p in extract.rglob('manifest.json')]+[p.parent for p in extract.rglob('plugin.toml')]
            if len(candidates)!=1:raise ValueError('Select an archive containing exactly one plugin')
            candidate=candidates[0]
        m=manifest(candidate);dest=USER/m['id']
        if dest.exists() and not update:raise ValueError('A user plugin with this ID is already installed; use Update')
        for entry in candidate.rglob('*'):
            if entry.is_symlink():raise ValueError('Plugin folders must not contain symlinks')
        staged=root/'ready';shutil.copytree(candidate,staged,ignore=shutil.ignore_patterns('.git','__pycache__'))
        backup=None
        if dest.exists():
            import time
            backup=STATE/'plugin-backups'/m['id']/str(time.time_ns());backup.parent.mkdir(parents=True,exist_ok=True)
            dest.rename(backup)
        try:staged.rename(dest)
        except Exception:
            if backup:backup.rename(dest)
            raise
    return scan()

def remove(identifier):
    m=find(identifier)
    if m['bundled']:return enable(identifier,False)
    import time
    TRASH.mkdir(parents=True,exist_ok=True);Path(m['path']).rename(TRASH/(str(time.time_ns())+'-'+identifier));return scan()

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['list','enable','disable','install','remove','settings','update','rollback','restore','desktop-layout','fault','recovery','catalogue','permissions']);p.add_argument('args',nargs='*');a=p.parse_args()
    try:
        if a.command=='list':v=scan()
        elif a.command in ('enable','disable'):v=enable(a.args[0],a.command=='enable')
        elif a.command=='permissions':
            find(a.args[0]);value=json.load(sys.stdin)
            if not isinstance(value,dict) or set(value)!= {'network'} or not isinstance(value['network'],bool):raise ValueError('Invalid extension permissions')
            prefs=load_preferences(PREFS);prefs.setdefault('permissions',{})[a.args[0]]=value;atomic_json(PREFS,prefs);v=scan()
        elif a.command=='catalogue':v=catalogue(a.args[0] if a.args else '')
        elif a.command=='fault':v=fault(a.args[0],json.load(sys.stdin))
        elif a.command=='recovery':v=recovery(a.args[0]=='on')
        elif a.command=='desktop-layout':v=desktop_layout(a.args[0],json.load(sys.stdin))
        elif a.command=='settings':v=save_settings(a.args[0],json.load(sys.stdin))
        elif a.command in ('install','update'):v=install(a.args[0],a.command=='update')
        elif a.command=='rollback':
            identifier=a.args[0]
            if not ID.fullmatch(identifier):raise ValueError('Invalid plugin ID')
            backups=sorted((STATE/'plugin-backups'/identifier).glob('*'))
            if not backups:raise ValueError('No previous version')
            current=USER/identifier
            if current.exists():
                import time
                TRASH.mkdir(parents=True,exist_ok=True);current.rename(TRASH/(str(time.time_ns())+'-'+identifier))
            backups[-1].rename(current);v=scan()
        elif a.command=='restore':
            identifier=a.args[0]
            if not ID.fullmatch(identifier):raise ValueError('Invalid plugin ID')
            choices=sorted(TRASH.glob('*-'+identifier));dest=USER/identifier
            if not choices or dest.exists():raise ValueError('Cannot restore this plugin')
            choices[-1].rename(dest);v=scan()
        else:v=remove(a.args[0])
        output(v);return 0
    except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':raise SystemExit(main())
