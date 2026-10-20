#!/usr/bin/env python3
"""Video and Workshop library integration. Engine options follow W Engine's
linux-wallpaperengine adapter (tadomika_ari/w-engine, MIT); playback is owned by
Hyprstack, with per-output processes rather than global pkill.
"""
from __future__ import annotations
import argparse,json,os,re,shutil,sys
from pathlib import Path
from feature_common import CONFIG,STATE,read_json,atomic_json,output
CONFIG_FILE=CONFIG/'live-wallpapers.json'
DEFAULTS={'kind':'static','source':'','muted':True,'volume':15,'fps':30,'scaling':'fill','pauseFullscreen':True,'pauseBattery':True,'disableMouse':False,'disableParticles':False,'disableParallax':False,'syncColors':True,'properties':{},'playlist':[],'cycleMinutes':15,'shuffle':False}
VIDEO={'.mp4','.webm','.mkv','.mov','.m4v','.avi','.ogv'}

def roots():
    saved=read_json(CONFIG_FILE);out=[];home=Path.home()
    for p in [home/'.steam/steam',home/'.local/share/Steam',home/'.var/app/com.valvesoftware.Steam/.local/share/Steam',*[Path(x).expanduser() for x in saved.get('workshopPaths',[])]]:
        candidates=[p]
        vdf=p/'steamapps/libraryfolders.vdf'
        if vdf.exists():
            try:candidates.extend(Path(x.replace('\\\\','\\')) for x in re.findall(r'"path"\s+"([^"]+)"',vdf.read_text()))
            except OSError:pass
        for lib in candidates:
            for root in [lib/'steamapps/workshop/content/431960',lib/'workshop/content/431960',lib]:
                if root.is_dir() and root not in out and (root.name=='431960' or root==lib and (lib/'project.json').exists()):out.append(root)
    return out

def library():
    result=[];seen=set()
    for root in roots():
        dirs=[root] if (root/'project.json').exists() else sorted(root.iterdir())
        for folder in dirs[:5000]:
            if not folder.is_dir() or not (folder/'project.json').is_file() or str(folder.resolve()) in seen:continue
            seen.add(str(folder.resolve()));data=read_json(folder/'project.json');preview=folder/str(data.get('preview','preview.jpg'))
            if not preview.is_file() or not preview.resolve().is_relative_to(folder.resolve()):preview=next((p for p in folder.glob('preview.*') if p.suffix.lower() in {'.jpg','.png','.jpeg','.webp','.gif'}),Path(''))
            props=(data.get('general') or {}).get('properties',{})
            result.append({'id':folder.name,'title':data.get('title',folder.name),'type':data.get('type','scene'),'path':str(folder.resolve()),'preview':str(preview.resolve()) if preview.is_file() else '', 'properties':props if isinstance(props,dict) else {}})
    return {'entries':result,'roots':[str(x) for x in roots()],'engineAvailable':bool(shutil.which('linux-wallpaperengine')),'ffmpegAvailable':bool(shutil.which('ffmpeg'))}

def config():
    d=read_json(CONFIG_FILE);return {'defaults':{**DEFAULTS,**d.get('defaults',{})},'outputs':d.get('outputs',{}),'workshopPaths':d.get('workshopPaths',[])}

def validate(value):
    c={**DEFAULTS,**value}
    if c['kind'] not in ('static','video','engine'):raise ValueError('Unknown wallpaper type')
    c['fps']=max(5,min(120,int(c['fps'])));c['volume']=max(0,min(100,int(c['volume'])));c['cycleMinutes']=max(1,min(1440,int(c['cycleMinutes'])))
    if c['scaling'] not in ('fill','fit','stretch','default'):raise ValueError('Unknown scaling mode')
    for k in ['muted','pauseFullscreen','pauseBattery','disableMouse','disableParticles','disableParallax','syncColors','shuffle']:c[k]=bool(c[k])
    if c['kind']=='video':
        path=Path(c['source']).expanduser()
        if not path.is_file() or path.suffix.lower() not in VIDEO:raise ValueError('Choose a local video file')
        c['source']=str(path.resolve())
    if c['kind']=='engine':
        path=Path(c['source']).expanduser()
        if not (path/'project.json').is_file():raise ValueError('Choose a Workshop item folder containing project.json')
        c['source']=str(path.resolve())
    if not isinstance(c['properties'],dict):raise ValueError('Expected wallpaper properties')
    for key,value in c['properties'].items():
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*',key):raise ValueError('Invalid wallpaper property')
        if not isinstance(value,(str,int,float,bool,list)):raise ValueError('Unsupported wallpaper property value')
    if not isinstance(c['playlist'],list):raise ValueError('Expected a playlist')
    return c

def save(output_name,value):
    if not output_name or len(output_name)>100 or '\n' in output_name:raise ValueError('Choose an output')
    data=config();data['outputs'][output_name]=validate(value);atomic_json(CONFIG_FILE,data);return data

def engine_command(output_name,value):
    c=validate(value)
    cmd=['linux-wallpaperengine','--screen-root',output_name,'--bg',c['source'],'--scaling',c['scaling'],'--layer','background','--fps',str(c['fps'])]
    cmd+=['--silent'] if c['muted'] else ['--volume',str(c['volume'])]
    for key,flag in [('disableMouse','--disable-mouse'),('disableParticles','--disable-particles'),('disableParallax','--disable-parallax')]:
        if c[key]:cmd.append(flag)
    if not c['pauseFullscreen']:cmd.append('--no-fullscreen-pause')
    for key,value in c['properties'].items():
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*',key):raise ValueError('Invalid wallpaper property')
        if isinstance(value,bool):value='1' if value else '0'
        elif isinstance(value,list):value=' '.join(str(x) for x in value)
        cmd.extend(['--set-property',f'{key}={value}'])
    return cmd

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['library','config','save','paths','engine-command']);p.add_argument('output',nargs='?',default='');a=p.parse_args()
    try:
        if a.command=='library':v=library()
        elif a.command=='config':v=config()
        elif a.command=='save':v=save(a.output,json.load(sys.stdin))
        elif a.command=='paths':
            d=config();paths=json.load(sys.stdin)
            if not isinstance(paths,list) or any(not isinstance(x,str) for x in paths):raise ValueError('Expected a list of paths')
            d['workshopPaths']=paths;atomic_json(CONFIG_FILE,d);v=d
        else:v={'command':engine_command(a.output,json.load(sys.stdin))}
        output(v);return 0
    except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':raise SystemExit(main())
