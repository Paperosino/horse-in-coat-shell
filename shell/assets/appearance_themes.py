"""User-session icon/cursor integration and real theme previews.

No root writes: GTK, Qt, Xresources and sandbox configuration belong to the user.
"""
from __future__ import annotations
import argparse, configparser, ctypes, ctypes.util, hashlib, json, os, re, shlex, shutil, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image
from feature_common import atomic_json, read_json, output

HOME = Path.home()
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME/'.config'))
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME/'.local/share'))
CACHE = Path(os.environ.get('XDG_CACHE_HOME', HOME/'.cache'))/'hics/theme-previews'
STATE = CONFIG/'hics/appearance.json'
ICON_NAMES = ['folder', 'user-home', 'text-x-generic', 'web-browser', 'user-trash', 'preferences-system']
CURSOR_NAMES = ['left_ptr', 'pointer', 'text', 'wait', 'crosshair', 'grab', 'grabbing', 'ew-resize']

def roots():
    return list(dict.fromkeys([DATA/'icons', HOME/'.icons', *[Path(p)/'icons' for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]]))

def ini(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if path.is_file(): parser.read(path, encoding='utf-8')
    return parser

def atomic_text(path, text):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        with os.fdopen(fd, 'w') as f: f.write(text)
        os.chmod(tmp, 0o600 if path.name == 'appearance.json' else 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def update_ini(path, section, values):
    parser = ini(path)
    if not parser.has_section(section): parser.add_section(section)
    for key, value in values.items(): parser.set(section, key, str(value))
    import io
    stream = io.StringIO(); parser.write(stream, space_around_delimiters=False)
    atomic_text(path, stream.getvalue())

def command(args, warnings=None, input=None):
    try:
        p = subprocess.run(args, input=input, capture_output=True, text=True, timeout=15)
        if p.returncode: raise ValueError((p.stderr or p.stdout).strip()[:350])
        return p.stdout.strip()
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        if warnings is not None: warnings.append(f'{args[0]}: {e}')
        return None

def themes():
    found = {}
    for root in roots():
        if not root.is_dir(): continue
        for path in sorted(root.iterdir()):
            if not path.is_dir() or path.name in found: continue
            if not ((path/'index.theme').is_file() or (path/'cursors').is_dir()): continue
            try: info = dict(ini(path/'index.theme').items('Icon Theme')) if (path/'index.theme').is_file() else {}
            except (configparser.Error, OSError): continue
            if path.name in ('default', 'hicolor', 'locolor'): continue
            found[path.name] = {'id':path.name, 'name':info.get('Name',path.name), 'path':path,
                'inherits':[x.strip() for x in info.get('Inherits','').split(',') if x.strip()],
                'directories':[x.strip() for x in (info.get('Directories','')+','+info.get('ScaledDirectories','')).split(',') if x.strip()],
                'hidden':info.get('Hidden', '').lower() == 'true'}
    return found

def resolve_icon(theme, name, catalogue, seen=None):
    seen = set() if seen is None else seen
    if theme in seen or theme not in catalogue: return None
    seen.add(theme); item = catalogue[theme]
    directories = sorted(item['directories'], key=lambda x:(0 if 'scalable' in x else 1 if re.search(r'(48|64)',x) else 2, len(x)))
    for directory in directories:
        # Theme manifests are untrusted input; previews stay inside the theme.
        parent = (item['path']/directory).resolve()
        if not parent.is_relative_to(item['path'].resolve()): continue
        for ext in ('svg','png','xpm'):
            file = parent/(name+'.'+ext)
            if file.is_file(): return file.as_uri()
    for inherited in item['inherits']:
        result = resolve_icon(inherited,name,catalogue,seen)
        if result: return result
    return None

class XcursorImage(ctypes.Structure):
    _fields_ = [(key, ctypes.c_uint32) for key in ('version','size','width','height','xhot','yhot','delay')] + [('pixels',ctypes.POINTER(ctypes.c_uint32))]

def cursor_preview(path, name):
    file = path/'cursors'/name
    if not file.is_file(): return ''
    key = hashlib.sha256((str(file.resolve())+str(file.stat().st_mtime_ns)).encode()).hexdigest()
    target = CACHE/(key+'.png')
    if target.is_file(): return target.as_uri()
    library = ctypes.util.find_library('Xcursor')
    if not library: return ''
    lib = ctypes.CDLL(library)
    lib.XcursorFilenameLoadImage.argtypes = [ctypes.c_char_p,ctypes.c_int]
    lib.XcursorFilenameLoadImage.restype = ctypes.POINTER(XcursorImage)
    lib.XcursorImageDestroy.argtypes = [ctypes.POINTER(XcursorImage)]
    image = lib.XcursorFilenameLoadImage(os.fsencode(file),32)
    if not image: return ''
    try:
        frame = image.contents
        if not (0 < frame.width <= 1024 and 0 < frame.height <= 1024): return ''
        raw = bytearray()
        for pixel in frame.pixels[:frame.width*frame.height]:
            a=(pixel>>24)&255
            # Xcursor stores premultiplied ARGB; PNG uses straight alpha.
            raw.extend([min(255,((pixel>>shift)&255)*255//a) if a else 0 for shift in (16,8,0)]+[a])
        CACHE.mkdir(parents=True, exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=CACHE,suffix='.png');os.close(fd)
        try:
            Image.frombytes('RGBA',(frame.width,frame.height),bytes(raw)).save(tmp)
            os.replace(tmp,target)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return target.as_uri()
    finally: lib.XcursorImageDestroy(image)

def current():
    saved=read_json(STATE)
    gtk=ini(CONFIG/'gtk-3.0/settings.ini')
    icons=gtk.get('Settings','gtk-icon-theme-name',fallback='Adwaita')
    cursor=gtk.get('Settings','gtk-cursor-theme-name',fallback=os.environ.get('XCURSOR_THEME','Adwaita'))
    size=gtk.get('Settings','gtk-cursor-theme-size',fallback=os.environ.get('XCURSOR_SIZE','24'))
    try:size=max(16,min(96,int(saved.get('size',size))))
    except (ValueError,TypeError):size=24
    return {'icons':saved.get('icons',icons),'cursors':saved.get('cursors',cursor),'size':size,
        'qt5':ini(CONFIG/'qt5ct/qt5ct.conf').get('Appearance','icon_theme',fallback=icons),
        'qt6':ini(CONFIG/'qt6ct/qt6ct.conf').get('Appearance','icon_theme',fallback=icons)}

def catalogue():
    all_themes=themes();icons=[];cursors=[]
    for item in all_themes.values():
        if item['directories'] and (not item['hidden'] or item['id']=='Adwaita'):
            previews=[{'name':name,'source':resolve_icon(item['id'],name,all_themes) or ''} for name in ICON_NAMES]
            icons.append({'id':item['id'],'name':item['name'],'previews':previews})
        if (item['path']/'cursors').is_dir():
            previews=[{'name':name,'source':cursor_preview(item['path'],name)} for name in CURSOR_NAMES]
            cursors.append({'id':item['id'],'name':item['name'],'previews':previews})
    return {'icons':sorted(icons,key=lambda t:t['name'].casefold()),'cursors':sorted(cursors,key=lambda t:t['name'].casefold()),
        'current':current(),'flatpak':bool(shutil.which('flatpak'))}

def set_gtk(base, kind, theme, size):
    values={'gtk-icon-theme-name':theme} if kind=='icons' else {'gtk-cursor-theme-name':theme,'gtk-cursor-theme-size':size}
    for version in ('3.0','4.0'):update_ini(base/f'gtk-{version}/settings.ini','Settings',values)
    # GTK2 uses an rc file rather than INI. Preserve unrelated lines.
    path=base/'gtk-2.0/gtkrc';text=path.read_text() if path.is_file() else ''
    for key,value in values.items():
        line=key+' = '+(str(value) if isinstance(value,int) else json.dumps(value))
        pattern=r'(?m)^\s*'+re.escape(key)+r'\s*=.*$'
        text=re.sub(pattern,lambda _:line,text) if re.search(pattern,text) else text.rstrip()+'\n'+line+'\n'
    atomic_text(path,text)

def qt_settings(base, theme):
    for version in (5,6):update_ini(base/f'qt{version}ct/qt{version}ct.conf','Appearance',{'icon_theme':theme})
    update_ini(base/'kdeglobals','Icons',{'Theme':theme})

def flatpak_settings(kind, theme, size, warnings):
    if not shutil.which('flatpak'):return
    result=command(['flatpak','list','--app','--columns=application'],warnings)
    if result is None:return
    for app in result.splitlines():
        if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',app):continue
        base=HOME/'.var/app'/app/'config'
        set_gtk(base,kind,theme,size)
        if kind=='icons':qt_settings(base,theme)
    # Host icons are already exported by Flatpak. No home/config access grant.
    if kind=='cursors':
        command(['flatpak','override','--user',f'--env=XCURSOR_THEME={theme}',f'--env=XCURSOR_SIZE={size}',
            '--env=XCURSOR_PATH=/run/host/user-share/icons:/run/host/share/icons:/usr/share/icons'],warnings)

def apply(kind, theme, size=24, runtime=True):
    if kind not in ('icons','cursors'):raise ValueError('Unknown theme type')
    if not 16 <= size <= 96:raise ValueError('Cursor size must be between 16 and 96')
    if not isinstance(theme,str) or any(c in theme for c in '\n\r\0'):raise ValueError('Invalid theme name')
    data=catalogue()
    if theme not in {t['id'] for t in data[kind]}:raise ValueError('Theme is not installed')
    warnings=[];set_gtk(CONFIG,kind,theme,size)
    if kind=='icons':qt_settings(CONFIG,theme)
    else:
        update_ini(DATA/'icons/default/index.theme','Icon Theme',{'Inherits':theme})
        # xrdb accepts resource values, not shell text; reject line separators.
        path=CONFIG/'hics/cursor.Xresources'
        atomic_text(path,f'Xcursor.theme: {theme}\nXcursor.size: {size}\n')
    if runtime:
        key='icon-theme' if kind=='icons' else 'cursor-theme'
        command(['gsettings','set','org.gnome.desktop.interface',key,json.dumps(theme)],warnings)
        if kind=='cursors':
            command(['gsettings','set','org.gnome.desktop.interface','cursor-size',str(size)],warnings)
            if os.environ.get('DISPLAY'):command(['xrdb','-merge',str(CONFIG/'hics/cursor.Xresources')],warnings)
            if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):command(['hyprctl','setcursor',theme,str(size)],warnings)
        flatpak_settings(kind,theme,size,warnings)
    saved=read_json(STATE);saved[kind]=theme
    if kind=='cursors':saved['size']=size
    atomic_json(STATE,saved)
    if runtime:
        environment=session_environment()
        atomic_text(CONFIG/'environment.d/90-hics-appearance.conf',
            '\n'.join(k+'='+json.dumps(v,ensure_ascii=False) for k,v in environment.items())+'\n')
        if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            script=';'.join('hl.env('+json.dumps(k)+','+json.dumps(v,ensure_ascii=False)+')' for k,v in environment.items())
            command(['hyprctl','repl',script],warnings)
    return {'current':current(),'warnings':warnings}

def session_environment():
    state=current()
    return {'XCURSOR_THEME':state['cursors'],'XCURSOR_SIZE':str(state['size']),
        'HYPRCURSOR_THEME':state['cursors'],'HYPRCURSOR_SIZE':str(state['size']),
        'QT_QPA_PLATFORMTHEME':'qt5ct',
        'QT_QUICK_CONTROLS_CONF':str(CONFIG/'hics/qtquickcontrols2.conf'),
        'GTK2_RC_FILES':str(CONFIG/'gtk-2.0/gtkrc')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['list','apply','environment','restore']);parser.add_argument('kind',nargs='?');parser.add_argument('theme',nargs='?');parser.add_argument('--size',type=int,default=24)
    args=parser.parse_args()
    if args.action=='list':output(catalogue())
    elif args.action=='apply':
        result=apply(args.kind,args.theme,args.size)
        # New apps launched by the shell and systemd inherit the session choice.
        warnings=result['warnings'];env=session_environment()
        command(['systemctl','--user','set-environment',*[f'{k}={v}' for k,v in env.items()]],warnings)
        command(['dbus-update-activation-environment',*[f'{k}={v}' for k,v in env.items()]],warnings)
        output(result)
    elif args.action=='environment':
        for key,value in session_environment().items():print('export '+key+'='+shlex.quote(value))
    else:
        if STATE.exists():
            saved=current();warnings=[]
            if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):command(['hyprctl','setcursor',saved['cursors'],str(saved['size'])],warnings)
            if os.environ.get('DISPLAY') and (CONFIG/'hics/cursor.Xresources').exists():command(['xrdb','-merge',str(CONFIG/'hics/cursor.Xresources')],warnings)
            output({'warnings':warnings})
        else:output({})
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,configparser.Error) as error:output({'error':str(error)});sys.exit(1)
