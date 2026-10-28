pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import Hyprstack
import Hyprstack.Config
import Hyprstack.Services
import qs.utils
Singleton {
    id: root
    property var pendingVolumes: []
    property bool initialized: false
    // Reuse Quickshell's existing connection. Binding video streams makes their
    // metadata/state available without a second core, subprocess or polling.
    readonly property var videoStreams: Pipewire.nodes.values.filter(n => n.type === PwNodeType.VideoInStream)
    readonly property var captureSnapshot: Pipewire.ready ? videoStreams.filter(n => n.ready).map(n => {
        const props = n.properties;
        const role = props["media.role"] || "";
        return {
            id: n.id,
            serial: String(props["object.serial"] || n.id),
            application: props["application.name"] || props["node.name"] || "",
            screen: role === "Screen" || role === "ScreenCapture",
            state: n.state
        };
    }).sort((a, b) => a.id - b.id) : []

    function publishCapture(): void {
        DesktopIntegration.setCaptureMonitorSnapshot(Pipewire.ready, captureSnapshot);
    }
    onCaptureSnapshotChanged: if (initialized) Qt.callLater(publishCapture)
    Component.onCompleted: {
        publishCapture();
        initialized = true;
    }
    Component.onDestruction: DesktopIntegration.setCaptureMonitorSnapshot(false, [])
    Connections {
        target: Pipewire
        function onReadyChanged(): void { if (root.initialized) Qt.callLater(root.publishCapture); }
    }
    PwObjectTracker { objects: root.videoStreams }
    Timer {
        interval: 5000; running: root.initialized; repeat: true; triggeredOnStart: true
        onTriggered: {
            if (!DesktopIntegration.busy && root.pendingVolumes.length) {
                const path = root.pendingVolumes[0];
                root.pendingVolumes = root.pendingVolumes.slice(1);
                DesktopIntegration.mountVolume(path);
            } else if (!DesktopIntegration.busy) DesktopIntegration.refreshMonitoring();
        }
    }
    Connections {
        target: DesktopIntegration
        function onRemovableVolumeAdded(path: string): void {
            if (GlobalConfig.services.openRemovableVolumes && !root.pendingVolumes.includes(path)) root.pendingVolumes = [...root.pendingVolumes, path];
        }
        function onVolumeMounted(path: string): void {
            if (GlobalConfig.services.openRemovableVolumes && path) CUtils.execDetached(["xdg-open", Paths.fileUrl(path)]);
        }
    }
}
