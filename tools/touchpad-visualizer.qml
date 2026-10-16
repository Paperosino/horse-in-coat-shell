import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

Scope {
    id: root
    property var gesture: ({phase: "idle", fingers: 0, x: 0, y: 0})
    property bool contacts: false
    readonly property var target: Quickshell.screens.find(s => s.name === Quickshell.env("HYPRSTACK_DEMO_OUTPUT")) ?? Quickshell.screens[0]
    readonly property real dx: Math.max(-65, Math.min(65, (gesture.x ?? 0) * .15))
    readonly property real dy: Math.max(-28, Math.min(28, (gesture.y ?? 0) * .065))
    FileView {
        path: Quickshell.env("HYPRSTACK_GESTURE_TRACE")
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const event = JSON.parse(text());
                root.gesture = event;
                if (event.phase === "begin" || event.phase === "update") {
                    release.stop();
                    root.contacts = true;
                } else if (event.phase === "end") release.restart();
            } catch (error) {}
        }
    }
    Timer { id: release; interval: 160; onTriggered: root.contacts = false }
    IpcHandler { target: "touchpad"; function ready(): bool { return true; } }

    PanelWindow {
        screen: root.target
        anchors { bottom: true }
        margins.bottom: 32
        implicitWidth: 280
        implicitHeight: 112
        color: "transparent"
        WlrLayershell.namespace: "hyprstack-touchpad-visualizer"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.exclusionMode: ExclusionMode.Ignore
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        mask: Region {}

        Repeater {
            model: root.gesture.fingers || 0
            Rectangle {
                required property int index
                width: 22; height: 22; radius: 11
                x: 140 + (index - (root.gesture.fingers - 1) / 2) * 34 + root.dx - width / 2
                y: 56 + root.dy - height / 2
                color: "#b9c5e8"
                border { color: "#f0f1ff"; width: 2 }
                opacity: root.contacts ? .95 : 0
                Behavior on opacity { NumberAnimation { duration: 100 } }
            }
        }
    }
}
