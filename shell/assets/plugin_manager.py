#!/usr/bin/env python3
"""Hyprstack extensions: atomic installs, lifecycle preferences and API detection.

Manifest lifecycle and entry-point design inspired by AngelOS (MixaDoDs, MIT).
Noctalia 4 QML and Noctalia 5 Luau are deliberately different compatibility levels.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,sys,tempfile,tomllib,urllib.request,urllib.parse,zipfile
from pathlib import Path
from feature_common import CONFIG,DATA,STATE,read_json,atomic_json,output
ASSETS=Path(__file__).resolve().parent
BUNDLED=ASSETS.parent/'plugins';USER=DATA/'plugins';PREFS=CONFIG/'plugins.json';TRASH=STATE/'plugin-trash'
ID=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$')
ALLOWED_IMPORTS={'QtQuick','QtQuick.Layouts','QtQuick.Controls','QtQuick.Controls.Basic','QtQuick.Effects','QtQml','QtQml.Models','Quickshell','Quickshell.Io','Quickshell.Widgets','Quickshell.Hyprland','Quickshell.Wayland','Hyprstack.Config','Hyprstack.I18n','qs.components','qs.components.controls','qs.services','qs.utils','qs.Commons','qs.Widgets','qs.Services'}
SUPPORTED_COMMONS={'Color','Style','I18n','Logger','Settings'}
SUPPORTED_SERVICES={'PluginService','ToastService','WallpaperService','NoctaliaService'}
SUPPORTED_WIDGETS={'NText','NIcon','NButton','NIconButton','NBox','NToggle','NSlider','NTextInput','NSpinBox','NLabel','NDivider'}

def text(v):return v if isinstance(v,str) else v.get('ru',v.get('en',next(iter(v.values()),''))) if isinstance(v,dict) else ''
def checked_path(root,name):
    p=(root/str(name)).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file():raise ValueError('Plugin entry points must be files inside the plugin folder')
    return p

def manifest(folder,bundled=False):
    if (folder/'manifest.json').exists():raw=read_json(folder/'manifest.json');fmt='native' if raw.get('api') in ('hics-1','hyprstack-1') else 'noctalia-qml' if 'entryPoints' in raw else 'angelos'
    elif (folder/'plugin.toml').exists():raw=tomllib.loads((folder/'plugin.toml').read_text());fmt='noctalia-luau'
    else:raise ValueError('No manifest.json or plugin.toml')
    original=str(raw.get('id',folder.name));identifier=re.sub(r'[^A-Za-z0-9_.-]','-',original)
    if not ID.fullmatch(identifier):raise ValueError('Invalid plugin ID')
    entries={};issues=[];settings=[]
    if fmt=='native':source=raw.get('entryPoints',{})
    elif fmt=='angelos':source={k:raw.get(k) for k in ['main','barWidget','desktopWidget','settings','panel']}
    elif fmt=='noctalia-qml':source=raw.get('entryPoints',{})
    else:source={};issues.append('Noctalia 5 Luau API '+str(raw.get('plugin_api','?'))+' requires a Luau host; QML entry points cannot execute this format.')
    if fmt=='angelos':
        # The manifest can be imported; visual QML must use Hyprstack/compatibility tokens.
        for file in folder.rglob('*.qml'):
            if 'qs.config' in file.read_text(errors='replace'):issues.append('AngelOS-specific qs.config/Skin imports require a visual port.');break
    for key,name in source.items():
        if key not in ('main','barWidget','desktopWidget','settings','panel') or not name:continue
        p=checked_path(folder,name);code=p.read_text(errors='replace')
        prop='pluginApi' if re.search(r'property\s+\w+\s+pluginApi\b',code) else 'plugin' if re.search(r'property\s+\w+\s+plugin\b',code) else ''
        entries[key]={'url':p.as_uri(),'property':prop,'requiredProperties':re.findall(r'required\s+property\s+\w+\s+(\w+)',code)}
    if fmt=='noctalia-qml':
        for file in folder.rglob('*.qml'):
            code=file.read_text(errors='replace')
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
    return dict(id=identifier,originalId=original,name=text(raw.get('name',identifier)),description=text(raw.get('description','')),version=str(raw.get('version','1.0.0')),author=text(raw.get('author','')),license=raw.get('license',''),format=fmt,bundled=bundled,path=str(folder.resolve()),entryPoints=entries,settingsSchema=settings,issues=sorted(set(issues)),compatible=not issues,adapter=adapter,icon=raw.get('icon','extension'),actions=raw.get('actions',raw.get('menu',[])),source=raw.get('source',''))

def scan():
    prefs=read_json(PREFS);found={};errors=[]
    for directory,bundled in [(BUNDLED,True),(USER,False)]:
        for folder in sorted(directory.glob('*')):
            if not folder.is_dir() or folder.is_symlink():continue
            try:
                m=manifest(folder,bundled);m['enabled']=m['compatible'] and prefs.get('enabled',{}).get(m['id'],False)
                defaults={s['key']:s.get('default') for s in m['settingsSchema']};m['settings']={**defaults,**prefs.get('settings',{}).get(m['id'],{})};found[m['id']]=m
            except (OSError,ValueError,TypeError,KeyError) as e:errors.append(f'{folder.name}: {e}')
    removed=[]
    for folder in sorted(TRASH.glob('*')):
        if not folder.is_dir() or folder.is_symlink():continue
        try:
            m=manifest(folder);removed.append({'id':m['id'],'name':m['name'],'version':m['version']})
        except (OSError,ValueError,TypeError,KeyError):pass
    for m in found.values():m['backupCount']=len(list((STATE/'plugin-backups'/m['id']).glob('*')))
    return {'plugins':list(found.values()),'removed':removed,'errors':errors,'directory':str(USER),'legacyNoctaliaApi':'QML subset','noctalia5':'Luau manifests and settings; native W Engine adapter'}

def find(identifier):
    result=next((p for p in scan()['plugins'] if p['id']==identifier),None)
    if not result:raise ValueError('Plugin not found')
    return result

def enable(identifier,value):
    plugin=find(identifier)
    if value and not plugin['compatible']:raise ValueError('; '.join(plugin['issues']))
    p=read_json(PREFS);p.setdefault('enabled',{})[identifier]=value;atomic_json(PREFS,p);return scan()

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
    p=read_json(PREFS);p.setdefault('settings',{})[identifier]=values;atomic_json(PREFS,p);return scan()

def github_folder(source, destination):
    u=urllib.parse.urlparse(source)
    parts=u.path.strip('/').split('/')
    if u.hostname!='github.com' or len(parts)<2: return False
    owner,repo=parts[:2];branch=parts[3] if len(parts)>3 and parts[2]=='tree' else 'HEAD'
    sub='/'.join(parts[4:]) if len(parts)>3 and parts[2]=='tree' else ''
    total=[0]
    def fetch(path, dest):
        url='https://api.github.com/repos/'+urllib.parse.quote(owner)+'/'+urllib.parse.quote(repo)+'/contents/'+urllib.parse.quote(path)+'?ref='+urllib.parse.quote(branch)
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Hyprstack/1'}),timeout=20) as r: items=json.load(r)
        if not isinstance(items,list):raise ValueError('Choose a GitHub plugin folder')
        dest.mkdir(parents=True,exist_ok=True)
        for item in items:
            name=item.get('name','')
            if not name or name in ('.','..') or '/' in name or '\\' in name:raise ValueError('Invalid GitHub path')
            if item['type']=='dir':fetch(item['path'],dest/name)
            elif item['type']=='file':
                total[0]+=int(item.get('size',0))
                if total[0]>32*1024*1024:raise ValueError('Plugin exceeds 32 MiB')
                url=item.get('download_url','')
                if urllib.parse.urlparse(url).hostname!='raw.githubusercontent.com':raise ValueError('Unexpected download origin')
                with urllib.request.urlopen(url,timeout=20) as r:(dest/name).write_bytes(r.read(32*1024*1024+1))
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
                with urllib.request.urlopen(req,timeout=30) as r,archive.open('wb') as f:
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
    p=argparse.ArgumentParser();p.add_argument('command',choices=['list','enable','disable','install','remove','settings','update','rollback','restore']);p.add_argument('args',nargs='*');a=p.parse_args()
    try:
        if a.command=='list':v=scan()
        elif a.command in ('enable','disable'):v=enable(a.args[0],a.command=='enable')
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
