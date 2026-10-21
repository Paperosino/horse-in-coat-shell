pragma Singleton
import QtQuick
import Quickshell
import Hyprstack
import Hyprstack.Config
import Hyprstack.Services
import qs.utils
Singleton {
    id: root
    property var pendingVolumes: []
    Timer {
        interval: 5000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: {
            if (!DesktopIntegration.busy && root.pendingVolumes.length) {
                const path = root.pendingVolumes[0];
                root.pendingVolumes = root.pendingVolumes.slice(1);
                DesktopIntegration.mountVolume(path);
            } else DesktopIntegration.refresh();
        }
    }
    Connections {
        target: DesktopIntegration
        function onRemovableVolumeAdded(path: string): void {
            if (GlobalConfig.services.openRemovableVolumes && !root.pendingVolumes.includes(path)) root.pendingVolumes = [...root.pendingVolumes, path];
        }
        function onVolumeMounted(path: string): void {
            if (GlobalConfig.services.openRemovableVolumes && path) Quickshell.execDetached(["xdg-open", Paths.fileUrl(path)]);
        }
    }
}
