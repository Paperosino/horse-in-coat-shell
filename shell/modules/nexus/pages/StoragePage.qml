pragma ComponentBehavior: Bound
import Hyprstack
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common
import qs.utils

PageBase {
    id: root
    pageIcon: "hard_drive"
    title: Tr.tr("Storage")
    pageDescription: Tr.tr("Your drives, available space and device health")
    property var backend: system
    property string selectedPath: ""
    readonly property var selectedVolume: (backend.state.volumes ?? []).find(v => v.path === selectedPath) ?? null
    readonly property var drives: {
        const result = new Map();
        for (const volume of backend.state.volumes ?? []) {
            const key = volume.drivePath && volume.drivePath !== "/" ? volume.drivePath : volume.serial || volume.model || volume.path;
            if (!result.has(key))
                result.set(key, {
                    key: key,
                    model: volume.model,
                    removable: volume.removable,
                    ssd: volume.ssd,
                    size: volume.driveSize || 0,
                    volumes: []
                });
            const drive = result.get(key);
            drive.volumes.push(volume);
        }
        for (const drive of result.values()) {
            drive.volumes.sort((a, b) => a.device.localeCompare(b.device));
            if (!drive.size)
                drive.size = drive.volumes.reduce((n, v) => n + v.size, 0);
        }
        return [...result.values()].sort((a, b) => Number(a.removable) - Number(b.removable) || String(a.model).localeCompare(String(b.model)));
    }
    function size(value: real): string {
        if (value >= 1099511627776)
            return (value / 1099511627776).toFixed(1) + " TiB";
        if (value >= 1073741824)
            return (value / 1073741824).toFixed(1) + " GiB";
        return (value / 1048576).toFixed(0) + " MiB";
    }
    function canUnmount(volume: var): bool {
        return !!volume.mountPoint && !["/", "/boot", "/boot/efi", "/home", "/usr", "/var"].includes(volume.mountPoint) && (volume.removable || volume.mountPoint.startsWith("/run/media/") || volume.mountPoint.startsWith("/media/") || volume.mountPoint.startsWith("/mnt/"));
    }
    function inspect(volume: var): void {
        selectedPath = selectedPath === volume.path ? "" : volume.path;
        if (selectedPath)
            Qt.callLater(() => {
                if (inspector.item)
                    root.flickable.contentY = Math.max(0, inspector.mapToItem(root.contentChild, 0, 0).y - 16 * Tokens.scale);
            });
    }
    function usage(volume: var): real {
        return volume.total > 0 ? Math.max(0, Math.min(1, 1 - (volume.free ?? 0) / volume.total)) : 0;
    }
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large
        NativeSystemBackend {
            id: system
            section: "storage"
            watching: root.visible && root.backend === system
        }
        Connections {
            target: DesktopIntegration
            function onOperationSucceeded(): void {
                if (!root.backend.busy)
                    root.backend.reload();
            }
        }
        FeatureError {
            error: root.backend.error
        }
        SettingsCard {
            id: memoryCard
            title: Tr.tr("Memory compression")
            description: Tr.tr("ZRAM, ZSwap and adaptive memory expansion")
            icon: "memory"
            collapsible: true
            expanded: false
            MemorySection { watching: root.visible && memoryCard.expanded }
        }
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                StyledText {
                    text: Tr.tr("Drives and volumes")
                    font: Tokens.font.title.medium
                }
                StyledText {
                    text: Tr.tr("Select a volume to view its health and connection settings")
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.body.small
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
            IconButton {
                icon: "refresh"
                Accessible.name: Tr.tr("Refresh")
                disabled: root.backend.busy
                onClicked: root.backend.reload()
            }
        }
        SettingsCard {
            visible: root.drives.length === 0
            title: root.backend.busy ? Tr.tr("Looking for drives…") : Tr.tr("No volumes found")
            description: Tr.tr("Connect a drive or unlock an encrypted volume below")
            icon: "hard_drive"
        }
        Repeater {
            model: root.drives
            SettingsCard {
                id: disk
                required property var modelData
                title: modelData.model || Tr.tr("Drive")
                description: root.size(modelData.size) + " · " + (modelData.removable ? Tr.tr("Removable drive") : Tr.tr("Internal drive"))
                icon: modelData.removable ? "usb" : "hard_drive"
                badge: modelData.ssd ? "SSD" : "HDD"
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 12 * Tokens.scale
                    radius: height / 2
                    color: Colours.palette.m3surfaceContainerHighest
                    clip: true
                    Row {
                        anchors.fill: parent
                        spacing: 0
                        Repeater {
                            model: disk.modelData.volumes
                            Rectangle {
                                required property var modelData
                                required property int index
                                width: Math.max(0, parent.width * modelData.size / Math.max(1, disk.modelData.size))
                                height: parent.height
                                radius: height / 2
                                color: index % 2 ? Colours.palette.m3tertiary : Colours.palette.m3primary
                                border.width: 1 * Tokens.scale
                                border.color: Colours.palette.m3surfaceContainerLow
                            }
                        }
                    }
                }
                Repeater {
                    model: disk.modelData.volumes
                    ConnectedRect {
                        id: partition
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        first: index === 0
                        last: index === disk.modelData.volumes.length - 1
                        color: root.selectedPath === modelData.path ? Colours.tPalette.m3secondaryContainer : Colours.tPalette.m3surfaceContainer
                        implicitHeight: details.implicitHeight + Tokens.padding.large * 2
                        ColumnLayout {
                            id: details
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: Tokens.padding.large
                            spacing: Tokens.spacing.small
                            RowLayout {
                                Layout.fillWidth: true
                                MaterialIcon {
                                    text: partition.modelData.mountPoint === "/" ? "computer" : "folder"
                                    color: Colours.palette.m3primary
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: 2 * Tokens.scale
                                    StyledText {
                                        Layout.fillWidth: true
                                        text: partition.modelData.label || (partition.modelData.mountPoint === "/" ? Tr.tr("System volume") : partition.modelData.device.split("/").pop())
                                        font: Tokens.font.title.small
                                        elide: Text.ElideRight
                                    }
                                    StyledText {
                                        Layout.fillWidth: true
                                        text: partition.modelData.device + " · " + partition.modelData.filesystem.toUpperCase()
                                        font: Tokens.font.body.small
                                        color: Colours.palette.m3onSurfaceVariant
                                        elide: Text.ElideMiddle
                                    }
                                }
                                StyledText {
                                    text: root.size(partition.modelData.size)
                                    font: Tokens.font.body.medium
                                }
                            }
                            StyledText {
                                Layout.fillWidth: true
                                text: partition.modelData.mountPoint ? (partition.modelData.mountPoint === "/" ? Tr.tr("System volume") : partition.modelData.mountPoint) : Tr.tr("Not mounted")
                                color: Colours.palette.m3onSurfaceVariant
                                font: Tokens.font.body.small
                                elide: Text.ElideMiddle
                            }
                            Rectangle {
                                visible: partition.modelData.total > 0
                                Layout.fillWidth: true
                                implicitHeight: 6 * Tokens.scale
                                radius: height / 2
                                color: Colours.palette.m3surfaceContainerHighest
                                Rectangle {
                                    width: parent.width * root.usage(partition.modelData)
                                    height: parent.height
                                    radius: parent.radius
                                    color: root.usage(partition.modelData) > .9 ? Colours.palette.m3error : Colours.palette.m3primary
                                    Behavior on width {
                                        Anim {}
                                    }
                                }
                            }
                            StyledText {
                                visible: partition.modelData.free !== undefined
                                text: Tr.tr("%1 available of %2").arg(root.size(partition.modelData.free ?? 0)).arg(root.size(partition.modelData.total ?? partition.modelData.size))
                                color: Colours.palette.m3onSurfaceVariant
                                font: Tokens.font.body.small
                            }
                            Flow {
                                Layout.fillWidth: true
                                spacing: Tokens.spacing.small
                                TextButton {
                                    visible: !!partition.modelData.mountPoint
                                    text: Tr.tr("Open")
                                    type: TextButton.Filled
                                    onClicked: CUtils.execDetached(["xdg-open", Paths.fileUrl(partition.modelData.mountPoint)])
                                }
                                TextButton {
                                    visible: !partition.modelData.mountPoint || root.canUnmount(partition.modelData)
                                    type: TextButton.Tonal
                                    text: partition.modelData.mountPoint ? Tr.tr("Unmount volume") : Tr.tr("Mount volume")
                                    disabled: root.backend.busy
                                    onClicked: root.backend.apply(partition.modelData.mountPoint ? "unmount" : "mount", {
                                        path: partition.modelData.path
                                    })
                                }
                                TextButton {
                                    type: TextButton.Text
                                    text: Tr.tr("Details and settings")
                                    isToggle: true
                                    checked: root.selectedPath === partition.modelData.path
                                    onClicked: root.inspect(partition.modelData)
                                }
                            }
                        }
                    }
                }
            }
        }
        Loader {
            id: inspector
            Layout.fillWidth: true
            active: !!root.selectedVolume
            sourceComponent: ColumnLayout {
                spacing: Tokens.spacing.medium
                Layout.fillWidth: true
                RowLayout {
                    Layout.fillWidth: true
                    StyledText {
                        Layout.fillWidth: true
                        text: root.selectedVolume?.label || root.selectedVolume?.device || ""
                        font: Tokens.font.title.medium
                        elide: Text.ElideMiddle
                    }
                    IconButton {
                        icon: "close"
                        Accessible.name: Tr.tr("Close")
                        onClicked: root.selectedPath = ""
                    }
                }
                StorageVolumeSettings {
                    volume: root.selectedVolume ?? ({})
                    backend: root.backend
                }
            }
        }
        RemovableStorage {}
    }
}
