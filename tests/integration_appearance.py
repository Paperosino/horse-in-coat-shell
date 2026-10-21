#!/usr/bin/env python3
"""Construct settings routes in an isolated nested Wayland session.

Requires built QML plugins (or an installed Hyprstack), Hyprland, grim and the
bundled Quickshell runtime. Does not apply themes or modify host preferences.
"""
import os,subprocess,tempfile,shutil,json,time
from pathlib import Path
repo=Path(__file__).resolve().parents[1];base=Path(tempfile.mkdtemp(prefix='hyprstack-appearance-smoke-'))
shell=base/'shell';shutil.copytree(repo/'shell',shell,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
# The qs.* aliases resolve from the test configuration root.
(shell/'shell.qml').write_text('''import QtQuick
import Quickshell
import Hyprstack.I18n
import qs.modules.nexus
import qs.services
ShellRoot {
 FloatingWindow {
  id:win
  implicitWidth:1100;implicitHeight:880
  color:Colours.palette.m3surface
  Nexus { id:nexus;anchors.fill:parent;nState.screen:win.screen;nState.isWindow:true }
  property var routes: ["appearance","panels","statusbar-layout","dock","apps","default-apps","plugins","assistant","shortcuts","mouse","cursor","shell-style","cursor-theme","icons"]
  property int next:0
  Timer {
   interval:900;running:true;repeat:true
   onTriggered: {
    if (win.next>=win.routes.length) {
     stop();
     function find(item) {
      if (item.objectName === "iconThemesPage") return item;
      for (const child of item.children ?? []) { const found=find(child); if(found)return found; }
      return null;
     }
     const page=find(nexus);
     if (!page || !AppearanceThemes.icons.length || !AppearanceThemes.cursors.length) {console.error("SMOKE_FAIL missing theme catalogue");return;}
     page.query="__no_such_theme__";
     if (page.filtered.length!==0) {console.error("SMOKE_FAIL theme search");return;}
     page.query=AppearanceThemes.icons[0].name;
     if (!page.filtered.length) {console.error("SMOKE_FAIL name search");return;}
     page.selected=page.filtered[0].id;
     if (page.choice!==page.selected) {console.error("SMOKE_FAIL preview selection");return;}
     page.query="";
     console.log("SMOKE_THEME_SEARCH_OK");
     return;
    }
    const id=win.routes[win.next++];const route=PageRegistry.route(id);
    nexus.nState.currentPageIdx=PageRegistry.indexOf(id);
    nexus.nState.subPageIdxStack=route.subPage!==undefined ? [route.subPage] : [];
    nexus.nState.searchRequested();
    console.log("SMOKE_PAGE",id);
   }
  }
 }
 Timer { interval:16000;running:true;onTriggered:Qt.quit() }
}
''')
env=dict(os.environ,HYPRSTACK_DATA_DIR=str(base),QML_IMPORT_PATH=str(repo/'build/qml') if (repo/'build/qml/Hyprstack').is_dir() else '/usr/share/hics/qml',QML2_IMPORT_PATH=str(repo/'build/qml') if (repo/'build/qml/Hyprstack').is_dir() else '/usr/share/hics/qml',LD_LIBRARY_PATH='/usr/share/hics/qs/lib',QT_QPA_PLATFORM='offscreen',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'))
# Probe only UI construction; helper processes see an isolated user config.
(base/'nested.lua').write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
nestedenv=dict(os.environ,AQ_BACKEND='wayland',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'));nestedenv.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
with open(base/'nested.log','w') as nestedlog:
 nested=subprocess.Popen(['Hyprland','--config',str(base/'nested.lua')],env=nestedenv,stdout=nestedlog,stderr=subprocess.STDOUT)
 try:
  for _ in range(80):
   instance=next((i for i in json.loads(subprocess.check_output(['hyprctl','instances','-j'])) if i['pid']==nested.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance
  env.update(QT_QPA_PLATFORM='wayland',WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'])
  with open('/tmp/hics-appearance-smoke.log','w') as out:
   child=subprocess.Popen(['/usr/share/hics/qs/bin/hics-qs','-p',str(shell)],env=env,stdout=out,stderr=subprocess.STDOUT)
   time.sleep(14)
   subprocess.run(['grim',str(base/'preview.png')],env=env,check=True,capture_output=True)
   result=child.wait(timeout=15)
 finally:
  nested.terminate();nested.wait(timeout=5)
print('Smoke root:',base,'exit:',result)
log=Path('/tmp/hics-appearance-smoke.log').read_text()
print(log[-6500:])
assert result==0, 'Settings process failed'
assert 'ERROR:' not in log and 'TypeError:' not in log and 'Unable to assign' not in log, 'QML errors in settings'
assert log.count('SMOKE_PAGE')==14, 'Some routes did not open'
assert 'SMOKE_THEME_SEARCH_OK' in log and 'SMOKE_FAIL' not in log, 'Theme search/selection failed'
print('PASS: all settings routes and theme previews construct without QML errors')
