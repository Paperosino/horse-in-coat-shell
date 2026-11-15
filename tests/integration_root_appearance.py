#!/usr/bin/env python3
"""Test installed root themes through Polkit; restore the real palette afterwards."""
import configparser
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def root_probe(directory):
    expected = json.loads(sys.stdin.read())
    # Preserve only the appearance environment supplied by the PAM session.
    env = {'HOME': '/root', 'PATH': '/usr/bin', 'DISPLAY': os.environ['DISPLAY'],
           'GDK_BACKEND': 'x11', 'QT_QPA_PLATFORM': 'xcb'}
    for key in ('ADW_DISABLE_PORTAL', 'QT_QPA_PLATFORMTHEME', 'QT_QUICK_CONTROLS_CONF'):
        assert key in os.environ, 'PAM did not supply '+key
        env[key] = os.environ[key]
    # Deliberately test the Qt fallback as well as the PAM-selected adapter.
    env.pop('QT_QPA_PLATFORMTHEME')
    result = subprocess.run([str(directory/'gtk2')], env=env, capture_output=True, text=True, timeout=8, check=True)
    assert result.stdout.strip() == '#'+expected['colours']['surface'], result.stdout
    print('PASS root GTK 2', expected['mode'], flush=True)
    for version in (5, 6):
        for style in ('Material', 'Universal'):
            result = subprocess.run([str(directory/f'qt{version}'), style],
                env=dict(env, QT_QUICK_CONTROLS_STYLE=style), capture_output=True, text=True, timeout=10)
            assert result.returncode == 0, result.stderr
            value = json.loads(result.stdout)
            assert value['window'] == '#'+expected['colours']['surface'], value
            assert value['quickDark'] == (expected['mode']=='dark'), value
            print('PASS root Qt', version, style, expected['mode'], flush=True)
    for version in ('3.0', '4.0'):
        code = "import gi,json;gi.require_version('Gtk',"+repr(version)+");from gi.repository import Gtk;"+(
            'Gtk.init([]);' if version=='3.0' else 'Gtk.init();')+"s=Gtk.Settings.get_default();print(json.dumps({'dark':s.get_property('gtk-application-prefer-dark-theme')}))"
        result = subprocess.run(['/usr/bin/python3', '-c', code], env=env, capture_output=True, text=True, timeout=8, check=True)
        assert json.loads(result.stdout)['dark'] == (expected['mode']=='dark')
        print('PASS root GTK', version, expected['mode'], flush=True)
    code = "import gi,json;gi.require_version('Adw','1');from gi.repository import Adw;Adw.init();print(json.dumps({'dark':Adw.StyleManager.get_default().get_dark()}))"
    result = subprocess.run(['/usr/bin/python3', '-c', code], env=env, capture_output=True, text=True, timeout=8, check=True)
    assert json.loads(result.stdout)['dark'] == (expected['mode']=='dark'), result.stdout
    print('PASS root libadwaita', expected['mode'], flush=True)


if '--root-probe' in sys.argv:
    assert os.geteuid()==0
    root_probe(Path(sys.argv[-1]))
else:
    assert os.geteuid()!=0, 'Run as the desktop user; Polkit performs the root probes'
    sys.path.insert(0, str(ROOT/'shell/assets'))
    import gtk_theme
    scheme = json.loads((Path(os.environ.get('XDG_STATE_HOME', Path.home()/'.local/state'))/'hics/scheme.json').read_text())
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
    parser = configparser.ConfigParser(interpolation=None);parser.read(config/'gtk-3.0/settings.ini')
    gtk = parser['Settings']
    qt = configparser.ConfigParser(interpolation=None);qt.read(config/'qt6ct/qt6ct.conf')
    aa, hint = gtk_theme.font_rendering()
    original = dict(colours=scheme['colours'], mode=scheme['mode'], antialias=aa, hinting=hint,
        icons=gtk.get('gtk-icon-theme-name','Adwaita'), cursor=gtk.get('gtk-cursor-theme-name','Adwaita'),
        cursorSize=gtk.getint('gtk-cursor-theme-size',24), font=gtk.get('gtk-font-name','Adwaita Sans 11'),
        qtFont=qt.get('Fonts','general',fallback='Adwaita Sans,11,-1,5,50,0,0,0,0,0'), controls=gtk_theme.window_controls(config))
    def apply(value):
        result=subprocess.run(['hics-systemctl','apply','appearance','configure'],input=json.dumps(value),capture_output=True,text=True,check=True,timeout=15)
        assert 'error' not in json.loads(result.stdout), result.stdout
    with tempfile.TemporaryDirectory(prefix='hics-root-themes-') as temp:
        directory=Path(temp)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtk+-2.0'],text=True))
        subprocess.run(['cc',str(ROOT/'tests/fixtures/root-gtk2-probe.c'),*flags,'-o',str(directory/'gtk2')],check=True,capture_output=True)
        for version in (5,6):
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',f'Qt{version}Widgets',f'Qt{version}Quick',f'Qt{version}Qml'],text=True))
            subprocess.run(['c++','-fPIC',str(ROOT/'tests/fixtures/root-toolkit-probe.cpp'),*flags,'-o',str(directory/f'qt{version}')],check=True)
        try:
            for mode,surface in (('light','f5f5f5'),('dark','101018')):
                value={**original,'mode':mode,'colours':{**original['colours'],'surface':surface}}
                apply(value)
                subprocess.run(['pkexec','/usr/bin/env','DISPLAY='+os.environ['DISPLAY'],'/usr/bin/python3',str(Path(__file__).resolve()),'--root-probe',str(directory)],input=json.dumps(value),text=True,check=True,timeout=120)
        finally:
            apply(original)
