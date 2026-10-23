pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.modules.nexus.common
import qs.utils
PageBase {
    pageIcon: "hard_drive"
    id: root
    title: Tr.tr("Storage")
    property string selectedPath
    readonly property var selectedVolume: (system.state.volumes ?? []).find(v => v.path === selectedPath) ?? null
    function size(value: real): string { return (value / 1073741824).toFixed(1) + " GiB"; }
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large
        NativeSystemBackend { id: system; section: "storage"; watching: root.visible }
        Connections {
            target: DesktopIntegration
            function onOperationSucceeded(): void { if (!system.busy) system.reload(); }
        }
        FeatureError { error: system.error }
        RowButton { first: true; last: true; text: Tr.tr("Refresh"); icon: "refresh"; disabled: system.busy; onClicked: system.reload() }
        Repeater {
            model: system.state.volumes ?? []
            ColumnLayout {
                id: volume
                required property var modelData
                readonly property bool canChangeMount: modelData.removable || !modelData.mountPoint || modelData.mountPoint.startsWith("/run/media/") || modelData.mountPoint.startsWith("/media/") || modelData.mountPoint.startsWith("/mnt/")
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall / 2
                InfoRow { first: true; label: volume.modelData.label || volume.modelData.model || volume.modelData.device; value: root.size(volume.modelData.size) }
                InfoRow { label: Tr.tr("Filesystem"); value: volume.modelData.filesystem + " · " + volume.modelData.device }
                InfoRow { visible: !!volume.modelData.mountPoint; label: Tr.tr("Mounted at"); value: volume.modelData.mountPoint }
                InfoRow { visible: volume.modelData.free !== undefined; label: Tr.tr("Available space"); value: root.size(volume.modelData.free ?? 0) + " / " + root.size(volume.modelData.total ?? 0) }
                RowButton { last: false; visible: !!volume.modelData.mountPoint; text: Tr.tr("Open in file manager"); icon: "folder_open"; onClicked: Quickshell.execDetached(["xdg-open", Paths.fileUrl(volume.modelData.mountPoint)]) }
                RowButton {
                    last: false
                    visible: volume.canChangeMount
                    text: volume.modelData.mountPoint ? Tr.tr("Unmount volume") : Tr.tr("Mount volume")
                    icon: volume.modelData.mountPoint ? "eject" : "hard_drive"
                    disabled: system.busy
                    onClicked: system.apply(volume.modelData.mountPoint ? "unmount" : "mount", {path: volume.modelData.path})
                }
                RowButton { last: true; text: Tr.tr("Settings, health & maintenance"); icon: "settings"; onClicked: root.selectedPath = root.selectedPath === volume.modelData.path ? "" : volume.modelData.path }
            }
        }
        RemovableStorage {}
        Loader {
            Layout.fillWidth: true
            active: !!root.selectedVolume
            sourceComponent: StorageVolumeSettings { volume: root.selectedVolume ?? ({}); backend: system }
        }
    }
}
