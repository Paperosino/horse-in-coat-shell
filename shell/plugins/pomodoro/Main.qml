import Hyprstack
import QtQuick
import Quickshell
Item {
    id: root
    required property var pluginApi
    property bool active: false
    property bool breakTime: false
    property int remaining: (pluginApi.settings.focusMinutes ?? 25) * 60
    function toggle(): void { active = !active; }
    function reset(): void { active = false; breakTime = false; remaining = (pluginApi.settings.focusMinutes ?? 25) * 60; }
    Timer {
        interval: 1000
        repeat: true
        running: root.active
        onTriggered: {
            if (--root.remaining > 0) return;
            root.breakTime = !root.breakTime;
            root.remaining = (root.breakTime ? root.pluginApi.settings.breakMinutes ?? 5 : root.pluginApi.settings.focusMinutes ?? 25) * 60;
            root.active = !!root.pluginApi.settings.autoContinue;
            CUtils.execDetached(["notify-send", "Hyprstack", root.breakTime ? "Time for a break" : "Time to focus"]);
        }
    }
}
