"""Privileged palette writer. Accept data, never user CSS, paths or code."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


def validate(options):
    if set(options) != {'colours', 'mode', 'antialias', 'hinting', 'icons', 'cursor', 'cursorSize', 'font', 'qtFont', 'controls'}:
        raise ValueError('Invalid root appearance fields')
    colours = options['colours']
    required = {'surface', 'onSurface', 'surfaceContainer', 'primary', 'onPrimary', 'outlineVariant'}
    if not isinstance(colours, dict) or not required <= colours.keys() or len(colours) > 256:
        raise ValueError('Invalid root palette')
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,95}', k) or not isinstance(v, str) or
           not re.fullmatch(r'[0-9a-fA-F]{6}', v) for k, v in colours.items()):
        raise ValueError('Invalid palette colour')
    if options['mode'] not in ('dark', 'light') or type(options['antialias']) is not bool or options['hinting'] not in ('none', 'slight', 'medium', 'full'):
        raise ValueError('Invalid appearance preference')
    if type(options['cursorSize']) is not int or not 8 <= options['cursorSize'] <= 128:
        raise ValueError('Invalid cursor size')
    for name in ('icons', 'cursor'):
        if not isinstance(options[name], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,127}', options[name]):
            raise ValueError('Invalid theme name')
    for name in ('font', 'qtFont'):
        if not isinstance(options[name], str) or not 1 <= len(options[name]) <= 256 or any(ord(c)<32 for c in options[name]):
            raise ValueError('Invalid font')
    import gtk_theme
    gtk_theme.validate_window_controls(options['controls'])
    return options


def apply(options, home):
    options = validate(options)
    # This module and gtk_theme are installed in a root-owned system directory.
    import gtk_theme
    home = Path(home)
    config = home/'.config'
    # Do not write through administrator-provided symlinks.
    targets = ('gtk-2.0', 'gtk-3.0', 'gtk-4.0', 'qt5ct', 'qt5ct/colors',
               'qt6ct', 'qt6ct/colors', 'hics', 'fontconfig', 'fontconfig/conf.d')
    for directory in (home, config, home/'.local', home/'.local/share', home/'.local/share/color-schemes', *(config/p for p in targets)):
        if directory.is_symlink():
            raise ValueError('Symlinked root appearance directory: ' + str(directory))
    for name in ('gtk-2.0/gtkrc', 'kdeglobals'):
        if (config/name).is_symlink():
            raise ValueError('Symlinked root appearance file')
    gtk_theme._font_override = options['antialias'], options['hinting']
    gtk_theme.atomic_text(config/'hics/window-controls.json', json.dumps(options['controls']))
    gtk_theme.apply_palette(options['colours'], config, options['mode'])
    # Root can read system-installed themes without loading user-owned plugins.
    icons = options['icons'] if (Path('/usr/share/icons')/options['icons']).is_dir() else 'Adwaita'
    cursor = options['cursor'] if (Path('/usr/share/icons')/options['cursor']).is_dir() else 'Adwaita'
    for version in ('3.0', '4.0'):
        gtk_theme.update_settings(config/f'gtk-{version}/settings.ini', 'Settings', {
            'gtk-icon-theme-name': icons, 'gtk-cursor-theme-name': cursor,
            'gtk-font-name': options['font'],
            'gtk-cursor-theme-size': options['cursorSize']})
    for version in (5, 6):
        gtk_theme.update_settings(config/f'qt{version}ct/qt{version}ct.conf', 'Appearance', {'icon_theme': icons})
        gtk_theme.update_settings(config/f'qt{version}ct/qt{version}ct.conf', 'Fonts', {'general': options['qtFont']})
    gtk_theme.update_settings(config/'kdeglobals', 'General', {'font': options['qtFont'].strip('"')})
    rc = config/'gtk-2.0/gtkrc'
    text = re.sub(r'(?m)^gtk-font-name\s*=.*\n?', '', rc.read_text())
    gtk_theme.atomic_text(rc, text.rstrip()+'\ngtk-font-name = '+json.dumps(options['font'])+'\n')
    gtk_theme.update_settings(config/'kdeglobals', 'Icons', {'Theme': icons})
    legacy = home/'.gtkrc-2.0'
    content = 'include '+json.dumps(str(config/'gtk-2.0/gtkrc'))+'\n'
    # The broker has a writable bind mount of this one file, not all of /root.
    # Its include is stable; palette updates happen atomically in .config.
    descriptor = os.open(legacy, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError('Invalid root GTK2 configuration')
        os.write(descriptor, content.encode())
        os.ftruncate(descriptor, len(content.encode()))
    finally:
        os.close(descriptor)
    gtk_theme.write_kde_scheme(config, home/'.local/share/color-schemes/hics.colors')
    # libadwaita reads GSettings rather than gtk-application-prefer-dark-theme.
    # Use root's own temporary bus and dconf service, never the user's bus.
    preferences = ("[/]\ncolor-scheme='prefer-"+options['mode']+"'\n"+
                   "gtk-theme='"+('Adwaita-dark' if options['mode']=='dark' else 'Adwaita')+"'\n"+
                   "icon-theme='"+icons+"'\ncursor-theme='"+cursor+"'\n"+
                   'font-name='+json.dumps(options['font'])+'\n'+
                   'cursor-size='+str(options['cursorSize'])+'\n')
    subprocess.run(['/usr/bin/dbus-run-session', '--', '/usr/bin/dconf', 'load',
                    '/org/gnome/desktop/interface/'], input=preferences,
                   text=True, capture_output=True, check=True, timeout=8)


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Root appearance writer must run as root')
    # Ignore inherited Python/module and XDG paths in this privileged helper.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    for key in tuple(os.environ):
        if key.startswith(('XDG_', 'DBUS_', 'GTK_', 'QT_', 'PYTHON')):
            os.environ.pop(key, None)
    import pwd
    home = pwd.getpwuid(0).pw_dir
    os.environ['HOME'] = home
    os.environ['GSETTINGS_BACKEND'] = 'dconf'
    os.environ['PATH'] = '/usr/bin'
    raw = sys.stdin.read(16385)
    if len(raw) > 16384:
        raise SystemExit('Appearance request is too large')
    apply(json.loads(raw), home)
