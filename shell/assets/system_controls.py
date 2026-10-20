#!/usr/bin/env python3
"""Typed, allowlisted Hyprland Lua settings and user session management.

UI concepts follow AngelOS and hyprland-dots-userfriendly/settings-ui; no legacy
hyprland.conf or privileged settings daemon is used.
"""
from __future__ import annotations
import argparse,json,os,re,shlex,sys,configparser
from pathlib import Path
from feature_common import CONFIG,atomic_json,read_json,run,output,lua
SCHEMA=[]
def field(group,key,label,kind,default,minimum=None,maximum=None,choices=None):
    SCHEMA.append(dict(group=group,key=key,label=label,type=kind,default=default,min=minimum,max=maximum,choices=choices or []))
field('Mouse','input.sensitivity','Pointer sensitivity','number',0,-1,1)
field('Mouse','input.accel_profile','Acceleration profile','choice','',choices=['','flat','adaptive'])
field('Mouse','input.natural_scroll','Natural scrolling','bool',False)
field('Mouse','input.left_handed','Left-handed mouse','bool',False)
field('Mouse','input.scroll_factor','Mouse scroll speed','number',1,0.1,5)
field('Mouse','input.scroll_method','Scroll method','choice','',choices=['','2fg','edge','on_button_down','no_scroll'])
field('Mouse','input.scroll_button','Scroll button code','int',0,0,999)
field('Mouse','input.scroll_button_lock','Lock scroll button','bool',False)
field('Touchpad','input.touchpad.natural_scroll','Natural touchpad scrolling','bool',True)
field('Touchpad','input.touchpad.tap-to-click','Tap to click','bool',True)
field('Touchpad','input.touchpad.tap-and-drag','Tap and drag','bool',True)
field('Touchpad','input.touchpad.drag_lock','Drag lock','int',0,0,2)
field('Touchpad','input.touchpad.disable_while_typing','Disable while typing','bool',True)
field('Touchpad','input.touchpad.scroll_factor','Touchpad scroll speed','number',0.3,0.1,5)
field('Touchpad','input.touchpad.clickfinger_behavior','Click with two or three fingers','bool',False)
field('Touchpad','input.touchpad.middle_button_emulation','Middle button emulation','bool',False)
field('Touchpad','input.touchpad.tap_button_map','Tap button mapping','choice','lrm',choices=['lrm','lmr'])
field('Touchpad','input.touchpad.flip_x','Reverse horizontal movement','bool',False)
field('Touchpad','input.touchpad.flip_y','Reverse vertical movement','bool',False)
field('Windows','input.follow_mouse','Focus follows mouse','choice',2,choices=[0,1,2,3])
field('Windows','input.float_switch_override_focus','Focus floating windows on hover','choice',0,choices=[0,1,2])
field('Windows','misc.focus_on_activate','Focus requested windows','bool',False)
field('Windows','misc.new_window_takes_over_fullscreen','New windows over fullscreen','choice',0,choices=[0,1,2])
field('Windows','misc.mouse_move_focuses_monitor','Focus monitor under pointer','bool',True)
field('Windows','misc.close_special_on_empty','Close empty special workspace','bool',True)
field('Windows','general.resize_on_border','Resize from window borders','bool',True)
field('Windows','general.extend_border_grab_area','Border resize grab area','int',15,0,40)
field('Windows','general.hover_icon_on_border','Resize cursor on borders','bool',True)
field('Windows','binds.allow_workspace_cycles','Allow workspace cycles','bool',True)
field('Windows','binds.workspace_back_and_forth','Return to previous workspace','bool',False)
field('Cursor','cursor.no_warps','Keep cursor position on focus change','bool',False)
field('Cursor','cursor.inactive_timeout','Hide cursor after seconds (0 disables)','int',0,0,600)
field('Cursor','cursor.hide_on_key_press','Hide cursor while typing','bool',False)
field('Cursor','cursor.hide_on_touch','Hide cursor for touch input','bool',True)
field('Cursor','cursor.zoom_factor','Cursor zoom','number',1,1,5)
field('Cursor','cursor.zoom_rigid','Rigid cursor zoom','bool',False)
field('Cursor','cursor.warp_on_change_workspace','Warp on workspace change','bool',False)
field('Cursor','cursor.hotspot_padding','Cursor edge padding','int',1,0,20)
field('Effects','decoration.blur.enabled','Window background blur','bool',False)
field('Effects','decoration.blur.size','Blur size','int',8,1,30)
field('Effects','decoration.blur.passes','Blur passes','int',2,1,8)
field('Effects','decoration.blur.xray','Blur through windows','bool',False)
field('Effects','decoration.blur.special','Blur special workspaces','bool',False)
field('Effects','decoration.blur.popups','Blur popup windows','bool',True)
field('Effects','decoration.blur.ignore_opacity','Ignore window opacity for blur','bool',False)
field('Effects','decoration.dim_inactive','Dim inactive windows','bool',False)
field('Effects','decoration.dim_strength','Inactive dim strength','number',0.1,0,1)
field('Effects','decoration.dim_special','Special workspace dim strength','number',0.2,0,1)
field('Effects','animations.enabled','Compositor animations','bool',True)
field('Gestures','gestures.workspace_swipe_distance','Workspace swipe distance','int',300,50,1000)
field('Gestures','gestures.workspace_swipe_invert','Invert workspace swipe','bool',True)
field('Gestures','gestures.workspace_swipe_forever','Continuous workspace swipe','bool',False)
field('Gestures','gestures.workspace_swipe_create_new','Create workspaces by swipe','bool',True)
field('Gestures','gestures.workspace_swipe_cancel_ratio','Swipe cancel ratio','number',0.5,0.1,0.9)
field('Gestures','gestures.workspace_swipe_min_speed_to_force','Forced swipe speed','int',30,0,200)
field('Gestures','gestures.workspace_swipe_touch','Touchscreen workspace swipe','bool',False)
field('Compatibility','xwayland.force_zero_scaling','Unscaled XWayland applications','bool',False)
field('Compatibility','misc.vfr','Variable frame rendering','bool',True)
field('Compatibility','misc.vrr','Adaptive sync policy','choice',0,choices=[0,1,2,3])
field('Compatibility','misc.animate_manual_resizes','Animate manual resizing','bool',False)
field('Compatibility','misc.animate_mouse_windowdragging','Animate mouse window dragging','bool',False)
BY_KEY={x['key']:x for x in SCHEMA}

def snapshot():
    overrides=read_json(CONFIG/'system-controls.json'); entries=[]
    for field in SCHEMA:
        item=dict(field); item['available']=True
        try:
            raw=json.loads(run(['hyprctl','-j','getoption',field['key']],timeout=3))
            item['value']=raw.get('int',raw.get('float',raw.get('str',field['default'])))
            if item['value']=='[[EMPTY]]':item['value']=''
            if field['type']=='bool':item['value']=bool(item['value'])
            if 'error' in raw: item['available']=False
        except (ValueError,OSError,TimeoutError):item['available']=False;item['value']=field['default']
        item['overridden']=field['key'] in overrides
        entries.append(item)
    return {'fields':entries,'configPath':str(CONFIG/'system.lua')}

def validate(key,value):
    f=BY_KEY.get(key)
    if not f:raise ValueError('Unknown system setting')
    if f['type']=='bool':
        if not isinstance(value,bool):raise ValueError('Expected a boolean')
    elif f['type'] in ('int','number'):
        if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError('Expected a number')
        if f['min'] is not None and not f['min']<=value<=f['max']:raise ValueError('Number out of range')
        if f['type']=='int':value=int(value)
    elif value not in f['choices']:raise ValueError('Unknown option')
    return value

def apply_change(key,value,reset=False):
    values=read_json(CONFIG/'system-controls.json')
    if reset: values.pop(key,None)
    else: values[key]=validate(key,value)
    tree={}
    for k,v in values.items():
        validate(k,v);node=tree;parts=k.split('.')
        for part in parts[:-1]:node=node.setdefault(part,{})
        node[parts[-1]]=v
    # Apply first: a rejected option never replaces a valid persistent configuration.
    if reset:
        default=BY_KEY[key]['default'];live={};n=live;parts=key.split('.')
        for part in parts[:-1]:n=n.setdefault(part,{})
        n[parts[-1]]=default; run(['hyprctl','eval','hl.config('+lua(live)+')'])
    else:run(['hyprctl','eval','hl.config('+lua(tree)+')'])
    CONFIG.mkdir(parents=True,exist_ok=True)
    path=CONFIG/'system.lua';text='-- Generated by Hyprstack system controls.\nhl.config('+lua(tree)+')\n'
    tmp=path.with_suffix('.lua.tmp');tmp.write_text(text);os.replace(tmp,path)
    atomic_json(CONFIG/'system-controls.json',values)
    hook=CONFIG/'hypr-user.lua'
    if hook.exists() and 'system.lua' not in hook.read_text():
        source=hook.read_text()
        if '"local.lua"' in source:source=source.replace('"local.lua"','"system.lua", "local.lua"',1)
        else:source+='\n-- Hyprstack system controls\nlocal system_controls = '+lua(str(path))+'\nif io.open(system_controls) then dofile(system_controls) end\n'
        hook.write_text(source)
    return {'ok':True,'key':key,'value':value}

def autostart_list():
    out=[];seen=set()
    for directory in [Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart',Path('/etc/xdg/autostart')]:
        for path in sorted(directory.glob('*.desktop')):
            if path.name in seen:continue
            seen.add(path.name);parser=configparser.ConfigParser(interpolation=None,strict=False)
            try:
                parser.read(path);e=parser['Desktop Entry'];out.append({'id':path.name,'name':e.get('Name',path.stem),'command':e.get('Exec',''),'enabled':e.get('Hidden','false').lower()!='true','path':str(path)})
            except (KeyError,configparser.Error):pass
    return out

def autostart_set(identifier,enabled):
    if not re.fullmatch(r'[\w. -]+\.desktop',identifier) or '/' in identifier:raise ValueError('Invalid autostart ID')
    row=next((x for x in autostart_list() if x['id']==identifier),None)
    if not row:raise ValueError('Autostart entry not found')
    parser=configparser.ConfigParser(interpolation=None);parser.optionxform=str;parser.read(row['path']);parser['Desktop Entry']['Hidden']='false' if enabled else 'true'
    dest=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart'/identifier;dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('w') as f:parser.write(f,space_around_delimiters=False)
    return {'ok':True}

def add_autostart(name,command):
    if not name.strip() or not command.strip() or '\n' in command or '\n' in name:raise ValueError('Enter a name and a command')
    shlex.split(command)
    import hashlib
    identifier='hyprstack-'+hashlib.sha256(name.encode()).hexdigest()[:12]+'.desktop'
    path=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart'/identifier;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec='+command+'\nTerminal=false\n');return {'ok':True}

def services():
    text=run(['systemctl','--user','list-unit-files','--type=service','--type=timer','--no-legend','--no-pager'])
    active=run(['systemctl','--user','list-units','--type=service','--type=timer','--all','--plain','--no-legend','--no-pager'])
    states={}
    for line in active.splitlines():
        p=line.split()
        if len(p)>3:states[p[0]]={'active':p[2],'sub':p[3]}
    return [{'id':p[0],'enabled':p[1] in ('enabled','enabled-runtime'),'state':p[1],**states.get(p[0],{'active':'inactive','sub':'dead'})} for l in text.splitlines() if len(p:=l.split())>=2]

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['list','set','reset','autostart','autostart-set','autostart-add','services','service']);p.add_argument('args',nargs='*');a=p.parse_args()
    try:
        if a.command=='list':v=snapshot()
        elif a.command=='set':v=apply_change(a.args[0],json.loads(a.args[1]))
        elif a.command=='reset':v=apply_change(a.args[0],None,True)
        elif a.command=='autostart':v=autostart_list()
        elif a.command=='autostart-set':v=autostart_set(a.args[0],a.args[1]=='true')
        elif a.command=='autostart-add':v=add_autostart(*a.args[:2])
        elif a.command=='services':v=services()
        else:
            action,unit=a.args[:2]
            if action not in ['start','stop','restart','enable','disable'] or not re.fullmatch(r'[A-Za-z0-9_@.:-]+\.(service|timer)',unit):raise ValueError('Invalid service action')
            if unit=='hyprstack-session.service' and action in ('stop','disable'):raise ValueError('The shell cannot stop itself from this page')
            run(['systemctl','--user',action,unit]);v={'ok':True}
        output(v)
    except Exception as e:output({'error':str(e)});return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
