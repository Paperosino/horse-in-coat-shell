pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "Keybinds.js" as Bindings

Singleton {
    id: root

    property var bindings: []
    property string error
    readonly property bool loading: reader.running

    function reload(): void {
        if (!reader.running)
            reader.running = true;
    }

    Component.onCompleted: reload()

    Connections {
        target: Hyprland
        function onRawEvent(event: HyprlandEvent): void {
            if (event.name === "configreloaded")
                refreshTimer.restart();
        }
    }

    Connections {
        target: LayoutModes
        function onModeChanged(): void { refreshTimer.restart(); }
    }

    Timer {
        id: refreshTimer
        interval: 200
        onTriggered: root.reload()
    }

    Process {
        id: reader
        command: ["hyprctl", "-j", "binds"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.bindings = Bindings.fromHyprland(JSON.parse(text));
                    root.error = "";
                } catch (err) {
                    root.error = "Unable to read keyboard shortcuts";
                }
            }
        }
        onExited: (code, status) => {
            if (code !== 0 || status !== 0)
                root.error = "Unable to read keyboard shortcuts";
        }
    }
}
