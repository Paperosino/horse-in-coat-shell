#!/usr/bin/env python3
"""Check real GTK3/4 settings on a private bus and private settings store."""
import sys,tempfile,subprocess,os
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'shell/assets'))
if os.environ.get('HICS_FONT_TEST_BUS') != '1':
    from integration_support import require_wayland_session
    require_wayland_session()
    with tempfile.TemporaryDirectory(prefix='hics-font-bus-') as private:
        config=Path(private)/'bus.conf'
        config.write_text('<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        # No activation directories: never start a portal, GVfs or systemd
        # instance against the real user's session during this test.
        raise SystemExit(subprocess.run(['dbus-run-session','--config-file='+str(config),'--',sys.executable,__file__],env=dict(os.environ,HICS_FONT_TEST_BUS='1')).returncode)
import gtk_theme
c=dict(surface='101018',onSurface='e0e0e0',surfaceContainer='202028',primary='aaccee',onPrimary='102030',outlineVariant='505060')
with tempfile.TemporaryDirectory() as d:
 env=dict(os.environ,XDG_CONFIG_HOME=d,XDG_DATA_HOME=d+'/data',GSETTINGS_BACKEND='keyfile')
 for key in ('HYPRLAND_INSTANCE_SIGNATURE','DISPLAY'):env.pop(key,None)
 with patch.dict(os.environ,env,clear=True):
  for aa,hint in [(a,h) for a in (False,True) for h in ('none','slight','medium','full')]:
   with patch.object(gtk_theme,'_font_override',(aa,hint)):
    gtk_theme.apply_palette(c,Path(d),'dark');gtk_theme.sync_session_preference(c,Path(d),'dark')
   for version in ['3.0','4.0']:
    probe=f'''import gi;gi.require_version('Gtk','{version}');from gi.repository import Gtk;Gtk.init({'[]' if version=='3.0' else ''});s=Gtk.Settings.get_default();print(s.get_property('gtk-xft-antialias'),s.get_property('gtk-xft-hinting'),s.get_property('gtk-xft-hintstyle'))'''
    out=subprocess.check_output(['python3','-c',probe],env=env,text=True).strip()
    expected=f'{int(aa)} {int(hint!="none")} hint{hint}'
    assert out==expected,(version,out,expected)
    print('GTK',version,out)
