// Disposable VM observer. Use a snapshot of the current shell/native modules,
// not the wrapper's installed import path. No extra PipeWire connection.
import QtQuick
import Quickshell
import Hyprstack.Services
import qs.services

ShellRoot {
    id: root
    property var monitor: DesktopIntegrationMonitor
    property string previous: ""
    function observe(): void {
        const snapshot = JSON.stringify({available: DesktopIntegration.captureMonitorAvailable,
                                        streams: DesktopIntegration.captureStreams});
        if (snapshot === previous) return;
        previous = snapshot;
        console.log("CAPTURE_OBSERVATION", Date.now(), snapshot);
    }
    Component.onCompleted: observe()
    Connections {
        target: DesktopIntegration
        function onChanged(): void { root.observe(); }
    }
    // Test-only bounded lifetime; this timer is not part of the release shell.
    Timer { interval: 120000; running: true; onTriggered: Qt.quit() }
}
