"""Construct system-integration pages headlessly with private config and D-Bus."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-desktop-ui-') as directory:
    base = Path(directory)
    shell = base / 'shell'
    shutil.copytree(ROOT / 'shell', shell, ignore=shutil.ignore_patterns('plugin', 'extras', '__pycache__'))
    (shell / 'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import Hyprstack.Services
import qs.modules.nexus
import qs.modules.nexus.pages
import qs.modules.nexus.common
import qs.modules.nexus.pages.services
import qs.services
import qs.modules.background
import qs.modules.bar.components
import qs.components
import qs.modules.bar as Bar
import qs.modules.drawers as Drawers
import "utils/scripts/settings-search.js" as Search
import "services/NotificationActivation.js" as ActivationMatch
ShellRoot {
 id: root
 property int defaultActionCount: 0
 property int otherActionCount: 0
 property NotifData activationProbe: NotifData {
  appName: "Test sender"; desktopEntry: "test.sender"
  liveActions: [{identifier:"default", invoke:() => root.defaultActionCount++}, {identifier:"delete", invoke:() => root.otherActionCount++}]
 }
 property int phase: 0
 property var current: null
 property NexusState state: NexusState {}
 FloatingWindow { visible: true; width: 1000; height: 900; Item { id: host; anchors.fill: parent } }
 ScreenState { id: popupState; modelData: Quickshell.screens[0] }
 Bar.BarWrapper { id: testBar; parent:host; screen:Quickshell.screens[0]; screenState:popupState; popouts:popupPanels.popouts; fullscreen:false }
 Drawers.Panels { id:popupPanels; parent:host; screen:Quickshell.screens[0]; screenState:popupState; bar:testBar; borderThickness:0 }
 PageBase {
  id: scrollProbe; parent: host; title: "Scroll regression"; nState: root.state; width: 800; height: 360
  property var rows: Array.from({length: 40}, (_, i) => i)
  Column {
   width: scrollProbe.cappedWidth
   Repeater { model: scrollProbe.rows; Rectangle { required property var modelData; width: 600; height: 40; color: "transparent" } }
  }
 }
 Timer { id: restoreRows; interval: 24; onTriggered: scrollProbe.rows = Array.from({length: 40}, (_, i) => i + 1) }
 Timer {
  property int step: 0
  interval: 160; running: true; repeat: true
  onTriggered: {
   if (step === 0) {
    if (scrollProbe.contentLayoutSettled.running || scrollProbe.flickable.contentHeight < 1000) return;
    scrollProbe.flickable.contentY = 500;
   }
   else if (step <= 4) {
    if (scrollProbe.contentLayoutSettled.running) return;
    if (!root.check(Math.abs(scrollProbe.flickable.contentY - 500) < 1, "scroll position after live update: " + scrollProbe.flickable.contentY + "/" + scrollProbe.flickable.contentHeight)) return;
    scrollProbe.rows = []; restoreRows.start();
   } else if (step === 5) {
    if (scrollProbe.contentLayoutSettled.running) return;
    if (!root.check(Math.abs(scrollProbe.flickable.contentY - 500) < 1, "scroll position after repeated updates")) return;
    scrollProbe.rows = [1];
   } else if (step >= 10) {
    if (!root.check(scrollProbe.flickable.contentY <= 0, "scroll clamped after actual content removal: " + scrollProbe.flickable.contentY + "/" + scrollProbe.flickable.contentHeight)) return;
    console.log("SCROLL_REFRESH_OK"); stop(); scrollProbe.visible = false;
   }
   step++;
  }
 }

 StatusIcons {}
 VideoWallpaper { settings: ({kind:"video",source:"",muted:true,volume:0,scaling:"fill"}); paused:true }
 Process { id: notifier }
 property string actionReply
 Process { id: actionNotifier; stdout: StdioCollector { onStreamFinished: root.actionReply = text.trim() } }
 function findPopup(item): var {
  if (item.objectName === "notificationPopup") return item;
  for (const child of item.children ?? []) { const found = findPopup(child); if (found) return found; }
  return null;
 }
 function sendNotification(): void { notifier.exec(["notify-send", "--app-name=Integration test", "--expire-time=10000", "Integration notification"]); }
 function check(condition, message): bool { if (condition) return true; console.error("NOTIFICATION_TEST_FAILED", message); Qt.quit(); return false; }
 property var sources: PageRegistry.navigationPages.map(p => p.pageIndex).concat(["AudioPage.qml", "NetworkPage.qml", "StoragePage.qml", "AccessibilityPage.qml", "SharingPage.qml", "services/NotificationsPage.qml", "network/AddNetworkPage.qml", "MediaPage.qml"])
 Component.onCompleted: {
  if (!check(PageRegistry.pages.length === PageCompRegistry.pageComps.length, "page registry alignment")) return;
  for (const page of PageRegistry.navigationPages) {
   if (!check(PageRegistry.indexOf(page.id) === page.pageIndex, "canonical route " + page.id)) return;
  }
  const searches = [["Volume step", 5], ["Brightness step", 1], ["Wi-Fi rescan", 3], ["Smart colour scheme", 0], ["Lyrics backend", 5], ["Application rules", 20], ["Encrypted volumes", 24]];
  for (const test of searches) {
   const result = Search.find(test[0], text => text).find(r => r.label === test[0]);
   if (!check(result && result.page === test[1], "search destination " + test[0])) return;
  }
  for (const entry of Search.catalogue) {
   if (!check(entry.page >= 0 && entry.page < PageRegistry.pages.length, "search page index")) return;
  }
  if (!check(GlobalConfig.notifs.actionOnClick, "notification activation enabled by default")) return;
  if (!check(activationProbe.activate() && defaultActionCount === 1 && otherActionCount === 0, "default action takes priority over other actions")) return;
  const entry = {id:"org.telegram.desktop", name:"Telegram", startupClass:"TelegramDesktop"};
  const old = {lastIpcObject:{mapped:true, class:"TelegramDesktop", focusHistoryID:3}};
  const recent = {lastIpcObject:{mapped:true, class:"org.telegram.desktop", focusHistoryID:0}};
  const wrong = {lastIpcObject:{mapped:true, class:"AyugramDesktop", focusHistoryID:0}};
  const spoofed = {lastIpcObject:{mapped:true, class:"Firefox", title:"Telegram", focusHistoryID:0}};
  if (!check(ActivationMatch.bestWindow({desktopEntry:"org.telegram.desktop"}, entry, [wrong, old, recent, spoofed]) === recent, "exact sender and most recent window")) return;
  if (!check(ActivationMatch.bestWindow({appName:"Telegram"}, null, [wrong, recent]) === recent, "sender app name fallback")) return;
  if (!check(!ActivationMatch.bestWindow({desktopEntry:"org.telegram.desktop", appName:"Firefox"}, null, [wrong, spoofed]), "unrelated app and title are not matched")) return;
  if (!check(!ActivationMatch.desktopEntry({appName:"Editor"}, [{id:"a",name:"Editor"},{id:"b",name:"Editor"}]), "ambiguous application names do not launch")) return;
  if (!check(!ActivationMatch.bestWindow({appName:"Telegram"}, null, [{lastIpcObject:{mapped:false,class:"TelegramDesktop"}}]), "closed windows are ignored")) return;
  if (!check(ActivationMatch.followWindow({desktopEntry:"org.telegram.desktop"}, entry, [recent], spoofed) === recent, "drawer focus changes do not cancel sender activation")) return;
  if (!check(ActivationMatch.followWindow({desktopEntry:"org.telegram.desktop"}, entry, [recent,old], old) === old, "application-selected window is preserved")) return;
  console.log("NOTIFICATION_ACTIVATION_OK");
  DesktopIntegration.refresh();
  Nmcli.setAutoconnect("Saved network", false, () => {});
  NotificationPolicy.observe("test.app", "Test app");
  NotificationPolicy.setRule("test.app", "silent");
 }
 Timer {
  interval: 500; running: true; repeat: true
  onTriggered: {
   if (root.current) { root.current.destroy(); root.current = null; }
   if (root.phase >= root.sources.length) {
    const step = root.phase++ - root.sources.length;
    if (step === 0) {
     Notifs.clearAll(); Notifs.dnd = false; NotificationPolicy.resume();
     NotificationPolicy.observe("Integration test", "Integration test");
     NotificationPolicy.setRule("Integration test", "silent"); root.sendNotification();
    } else if (step === 1) {
     if (!root.check(Notifs.notClosed.length === 1 && Notifs.popups.length === 0, "silent rule")) return;
     NotificationPolicy.setRule("Integration test", "blocked"); root.sendNotification();
    } else if (step === 2) {
     if (!root.check(Notifs.notClosed.length === 1, "blocked rule")) return;
     Notifs.clearAll(); NotificationPolicy.setRule("Integration test", "all"); NotificationPolicy.pauseFor(30); root.sendNotification();
    } else if (step === 3) {
     if (!root.check(Notifs.notClosed.length === 1 && Notifs.popups.length === 0, "temporary pause")) return;
     NotificationPolicy.resume(); Notifs.clearAll();
     popupPanels.popouts.currentName = "audio";
     popupPanels.popouts.currentCenter = 950;
     popupPanels.popouts.hasCurrent = true;
     root.sendNotification();
    } else if (step === 4) {
     if (!root.check(Notifs.popups.length === 1, "resume popups")) return;
     if (!root.check(popupPanels.notificationPopoutOverlap, "right-hand popup intersects notification column")) return;
     if (!root.check(popupPanels.notifications.y + 5 >= popupPanels.popoutsWrapper.y + popupPanels.popoutsWrapper.height, "notifications are below the popup instead of overlapping")) return;
     if (!root.check(popupPanels.notifications.y + popupPanels.notifications.height <= popupPanels.height + 1, "notification stack fits remaining screen height")) return;
     const card = root.findPopup(popupPanels.notifications);
     if (!root.check(card !== null, "actual notification card exists")) return;
     const cardTop = card.mapToItem(popupPanels, 0, 0).y;
     if (!root.check(cardTop >= popupPanels.popoutsWrapper.y + popupPanels.popoutsWrapper.height, "notification card follows its background: " + cardTop)) return;
     console.log("NOTIFICATION_POPUP_LAYOUT_OK");
     popupPanels.popouts.close();
    } else if (step === 5) {
     Notifs.clearAll(); root.actionReply = "";
     actionNotifier.exec(["notify-send", "--app-name=Integration test", "--expire-time=10000", "--action=default=Open", "Action notification"]);
    } else if (step === 6) {
     const notification = Notifs.notClosed.find(n => n.summary === "Action notification");
     if (!root.check(notification && notification.activate(), "live notification default action")) return;
    } else if (step === 7) {
     if (!root.check(root.actionReply === "default", "ActionInvoked delivered to application")) return;
     console.log("NOTIFICATION_DBUS_ACTION_OK");
     console.log("DESKTOP_UI_OK"); Qt.quit();
    }
    return;
   }
   const path = root.sources[root.phase++];
   const component = typeof path === "number" ? PageCompRegistry.pageComps[path] : Qt.createComponent("modules/nexus/pages/" + path);
   if (component.status !== Component.Ready) { console.error(component.errorString()); Qt.quit(); return; }
   root.current = component.createObject(host, {nState: root.state, width: 1000, height: 900});
   if (!root.current) { console.error("PAGE_CREATION_FAILED", path); Qt.quit(); return; }
   GlobalConfig.appearance.highContrast = root.phase % 2 === 1;
   GlobalConfig.appearance.reducedMotion = true;
   console.log("PAGE_OK", path);
  }
 }
 Timer { interval: 30000; running: true; onTriggered: { console.error("DESKTOP_UI_TIMEOUT"); Qt.quit(); } }
}''')
    tools = base / 'tools'
    tools.mkdir()
    fake = '#!/usr/bin/python3\nimport sys,json\nprint(json.dumps({"error":"Test backend unavailable"}) if "status" in sys.argv or "apply" in sys.argv else "[]")\n'
    for name in ('hyprctl', 'nmcli', 'hyprstack', 'hics-systemctl', 'pactl', 'pw-dump'):
        path = tools / name
        if name == 'pactl':
            path.write_text('#!/usr/bin/python3\nimport json\nprint(json.dumps([{"name":"test-card","properties":{"device.description":"Test card"},"active_profile":"stereo","profiles":{"stereo":{"description":"Stereo","available":"yes"}}}]))\n')
        elif name == 'pw-dump':
            path.write_text('#!/usr/bin/python3\nimport json\nprint(json.dumps([{"id":1,"info":{"state":"running","props":{"media.class":"Stream/Input/Video","application.name":"Test camera"}}}]))\n')
        elif name == 'nmcli':
            path.write_text('#!/usr/bin/python3\nimport os,json,sys\nwith open(os.environ["TEST_NETWORK_LOG"], "a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\nprint("")\n')
        else:
            path.write_text(fake)
        path.chmod(0o700)
    env = dict(os.environ, QT_QPA_PLATFORM='wayland', QT_QUICK_BACKEND='software',
        XDG_CONFIG_HOME=str(base / 'config'), XDG_STATE_HOME=str(base / 'state'),
        XDG_DATA_HOME=str(base / 'data'), XDG_CACHE_HOME=str(base / 'cache'),
        TEST_NETWORK_LOG=str(base / 'network.log'), XDG_RUNTIME_DIR=str(base / 'runtime'), QML_IMPORT_PATH=str(ROOT / 'build/qml'),
        QML2_IMPORT_PATH=str(ROOT / 'build/qml'), HYPRSTACK_NESTED='1',
        PATH=str(tools) + ':' + os.environ['PATH'])
    Path(env['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
    env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    env.pop('WAYLAND_DISPLAY', None)
    # Use one private bus for both APIs so no host service can be activated.
    runner = base / 'run.py'
    runner.write_text('import os,sys\nos.environ["DBUS_SYSTEM_BUS_ADDRESS"]=os.environ["DBUS_SESSION_BUS_ADDRESS"]\nos.execvp(sys.argv[1],sys.argv[1:])\n')
    compositor = None
    try:
        display = os.environ.get('WAYLAND_DISPLAY')
        if not display:
            raise SystemExit('This integration test needs a parent Wayland session')
        parent = display if display.startswith('/') else str(Path(os.environ['XDG_RUNTIME_DIR']) / display)
        config = base / 'compositor.lua'
        config.write_text('hl.monitor({output="WAYLAND-1",mode="1280x900@60",position="0x0",scale=1})\n')
        nestedEnv = dict(env, WAYLAND_DISPLAY=parent, AQ_BACKEND='wayland')
        nestedEnv['PATH'] = os.environ['PATH']
        with (base / 'compositor.log').open('w') as log:
            compositor = subprocess.Popen(['Hyprland', '--config', str(config)], env=nestedEnv, stdout=log, stderr=subprocess.STDOUT)
        sockets = []
        for _ in range(80):
            sockets = [p for p in Path(env['XDG_RUNTIME_DIR']).glob('wayland-*') if p.is_socket()]
            if sockets or compositor.poll() is not None:
                break
            time.sleep(.1)
        if not sockets:
            raise RuntimeError((base / 'compositor.log').read_text()[-5000:])
        time.sleep(.7)
        env['WAYLAND_DISPLAY'] = str(sockets[0])
        instances = list((Path(env['XDG_RUNTIME_DIR']) / 'hypr').glob('*'))
        if instances:
            env['HYPRLAND_INSTANCE_SIGNATURE'] = instances[0].name
        run = subprocess.run(['dbus-run-session', '--', 'python3', str(runner),
            'quickshell', '-p', str(shell)], env=env, capture_output=True, text=True, timeout=35)
        output = run.stdout + run.stderr
        print(output[-24000:])
        assert run.returncode == 0 and 'DESKTOP_UI_OK' in output and 'SCROLL_REFRESH_OK' in output and 'NOTIFICATION_ACTIVATION_OK' in output and 'NOTIFICATION_DBUS_ACTION_OK' in output and 'NOTIFICATION_POPUP_LAYOUT_OK' in output, 'Pages failed to construct'
        forbidden = ('TypeError:', 'ReferenceError:', 'Unable to assign', 'PAGE_CREATION_FAILED', 'Cannot assign to non-existent', 'Binding loop', 'NOTIFICATION_TEST_FAILED')
        assert not any(message in output for message in forbidden), 'QML runtime errors'
        import json
        commands = [json.loads(line) for line in (base / 'network.log').read_text().splitlines()]
        assert ['connection', 'modify', 'Saved network', 'connection.autoconnect', 'no'] in commands
        assert not any('delete' in cmd or '802-11-wireless-security.psk' in cmd or '802-11-wireless-security.psk-flags' in cmd for cmd in commands)
        print('PASS: all navigation pages, profile menus, notification delivery, palettes and autoconnect credential preservation')
    finally:
        if compositor and compositor.poll() is None:
            compositor.terminate()
            compositor.wait(timeout=5)
