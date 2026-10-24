import QtQuick
import Quickshell.Io
Item {
    required property var pluginApi
    Process {
        id: sunset
        command: ["hyprsunset", "--temperature", String(pluginApi.settings.temperature ?? 4500)]
        running: true
        onCommandChanged: if (running) { running = false; restart.restart(); }
    }
    Timer { id: restart; interval: 0; onTriggered: sunset.running = true }
}
