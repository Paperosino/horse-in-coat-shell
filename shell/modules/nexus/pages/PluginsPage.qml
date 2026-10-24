pragma ComponentBehavior: Bound
import Hyprstack
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.utils
import qs.modules.extensions
import qs.modules.nexus
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "extension"
    title: Tr.tr("Plugins")
    objectName: "pluginsPage"
    readonly property var selected: Plugins.byId(Plugins.selectedId)
    Component.onCompleted: Plugins.reload()
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.extraSmall
        FeatureError {
            error: Plugins.error
        }
        SettingsCard {
            visible:Plugins.recoveryMode
            title:Tr.tr("Extension recovery mode")
            description:Tr.tr("Extensions were suspended after an unexpected shell exit. Enable them individually below to identify the problem.")
            icon:"health_and_safety"
            InfoRow {label:Tr.tr("Reason");value:Tr.tr(Plugins.recoveryReason)}
            RowButton {text:Tr.tr("Resume all configured extensions");icon:"play_arrow";onClicked:Plugins.setRecovery(false)}
        }
        SettingsCard {
            title:Tr.tr("Extension catalogue")
            description:Tr.tr("Browse bundled extensions or load a compatible HTTPS catalogue. Installation does not enable third-party code automatically.")
            icon:"extension"
            TextFieldRow {id:catalogueSource;label:Tr.tr("Catalogue URL");subtext:Tr.tr("Optional HTTPS JSON catalogue");value:""}
            RowButton {text:Tr.tr("Load catalogue");icon:"refresh";disabled:Plugins.busy;onClicked:Plugins.loadCatalogue(catalogueSource.field.text.trim())}
            Repeater {
                model:Plugins.catalogue
                SettingsCard {
                    id:catalogueEntry
                    required property var modelData
                    title:modelData.name||modelData.id
                    description:modelData.description||""
                    icon:modelData.icon||"extension"
                    badge:modelData.version||""
                    Image {Layout.fillWidth:true;Layout.preferredHeight:visible?150*Tokens.scale:0;visible:!!source;source:catalogueEntry.modelData.preview??"";asynchronous:true;fillMode:Image.PreserveAspectFit;sourceSize.width:640;sourceSize.height:300}
                    InfoRow {visible:!!catalogueEntry.modelData?.dependencies;label:Tr.tr("Dependencies");value:JSON.stringify(catalogueEntry.modelData?.dependencies??[])}
                    RowButton {text:Plugins.byId(catalogueEntry.modelData.id)?Tr.tr("Settings and details"):Tr.tr("Install");icon:"extension";disabled:Plugins.busy;onClicked:{const item=catalogueEntry.modelData;if(Plugins.byId(item.id))Plugins.selectedId=item.id;else Plugins.install(item.source);}}
                }
            }
        }
        SettingsCard {
            title: Tr.tr("Desktop widget layout")
            description: Tr.tr("Drag widgets, resize from the corner, snap to a grid or lock their placement. Layout is saved separately for each monitor. Arrow keys move; Ctrl + arrows resize.")
            icon: "dashboard_customize"
            ToggleRow { text: Tr.tr("Edit desktop widgets"); checked:Plugins.desktopEditing; onToggled:Plugins.desktopEditing=checked }
        }
        SettingsCard {
            visible:!!Plugins.selectedId && (Plugins.faults[Plugins.selectedId]??[]).length>0
            title:Tr.tr("Extension error log")
            icon:"bug_report"
            Repeater {
                model:Plugins.faults[Plugins.selectedId]??[]
                InfoRow {required property var modelData;label:new Date(modelData.time*1000).toLocaleString();value:modelData.error}
            }
        }
        SettingsCard {
            title: Tr.tr("Installed extensions")
            icon: "extension"

            Repeater {
                model: Plugins.plugins
                delegate: ColumnLayout {
                    id: row
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0
                    ToggleRow {
                        text: Tr.tr(row.modelData.name)
                        subtext: Tr.tr(row.modelData.description) + (row.modelData.compatible ? "" : " · " + (row.modelData.issues.some(i => i.startsWith("Missing dependency:")) ? Tr.tr("Dependencies are missing") : Tr.tr("Requires adaptation")))
                        checked: row.modelData.enabled
                        enabled: row.modelData.compatible && !Plugins.busy
                        onToggled: Plugins.setEnabled(row.modelData.id, checked)
                    }
                    InfoRow {label:Tr.tr("Execution model");value:row.modelData.isolated?Tr.tr("Isolated process · declarative interface"):Tr.tr("Trusted QML · full shell access")}
                    ToggleRow {visible:row.modelData.isolated&&row.modelData.networkRequested;text:Tr.tr("Allow network access");subtext:Tr.tr("Restart the extension with the selected permission");checked:row.modelData.networkGranted;onToggled:Plugins.grantNetwork(row.modelData.id,checked)}
                    RowButton {
                        text: Tr.tr("Settings and details")
                        subtext: row.modelData.format + " · " + row.modelData.version
                        icon: "tune"
                        onClicked: Plugins.selectedId = row.modelData.id
                    }
                }
            }
        }
        SettingsCard {
            title: Tr.tr("Install an extension")
            icon: "extension"

            TextFieldRow {
                id: source
                label: Tr.tr("Plugin source")
                subtext: Tr.tr("Folder, ZIP archive, HTTPS link or GitHub plugin folder")
                value: ""
            }
            RowLayout {
                TextButton {
                    text: Tr.tr("Install")
                    enabled: !!source.field.text.trim() && !Plugins.busy
                    onClicked: Plugins.install(source.field.text.trim())
                }
                TextButton {
                    text: Tr.tr("Update with backup")
                    enabled: !!source.field.text.trim() && !Plugins.busy
                    onClicked: Plugins.update(source.field.text.trim())
                }
                TextButton {
                    text: Tr.tr("Reload plugins")
                    enabled: !Plugins.busy
                    onClicked: Plugins.reloadCode()
                }
            }
            RowButton {
                text: "AngelOS Community"
                subtext: Tr.tr("Browse extension sources")
                icon: "open_in_new"
                onClicked: Quickshell.openUrlExternally("https://github.com/MixaDoDs/AngelOS-Dotfiles/tree/main/.config/quickshell/angelos/plugins")
            }
            RowButton {
                text: "Noctalia Community"
                subtext: Tr.tr("Compatibility is checked on import")
                icon: "open_in_new"
                onClicked: Quickshell.openUrlExternally("https://github.com/noctalia-dev/community-plugins")
            }
            ColumnLayout {
                Layout.fillWidth: true
                visible: !!root.selected
                spacing: Tokens.spacing.extraSmall
                SectionHeader {
                    text: Tr.tr(root.selected?.name ?? "")
                }
                InfoRow {
                    label: Tr.tr("Format")
                    value: root.selected?.format ?? ""
                }
                InfoRow {
                    label: Tr.tr("Author")
                    value: root.selected?.author ?? ""
                }
                InfoRow {
                    label: Tr.tr("License")
                    value: root.selected?.license ?? ""
                }
                FeatureError {
                    error: (root.selected?.issues ?? []).join("\n")
                }
                FeatureError {
                    error: Plugins.runtimeErrors[Plugins.selectedId] ?? ""
                }
                RowButton {
                    visible: root.selected?.adapter === "wallpaper-engine"
                    text: Tr.tr("Open native Wallpaper Engine integration")
                    icon: "wallpaper"
                    onClicked: {
                        root.nState.currentPageIdx = PageRegistry.indexOf("appearance");
                        root.nState.openSubPage(5);
                    }
                }
                Repeater {
                    model: root.selected?.compatible ? root.selected?.settingsSchema ?? [] : []
                    delegate: GenericSettingRow {
                        required property var modelData
                        spec: modelData
                        value: root.selected?.settings?.[modelData.key] ?? modelData.default
                        enabled: !Plugins.busy
                        onEdited: value => Plugins.saveSettings(Plugins.selectedId, Object.assign({}, root.selected.settings, {
                                [modelData.key]: value
                            }))
                    }
                }
                PluginSlot {
                    Layout.fillWidth: true
                    pluginId: Plugins.selectedId
                    slot: "settings"
                }
                PluginSlot {
                    Layout.fillWidth: true
                    pluginId: Plugins.selectedId
                    slot: "panel"
                }
                Repeater {
                    model: root.selected?.enabled ? root.selected?.actions ?? [] : []
                    delegate: RowButton {
                        required property var modelData
                        text: Tr.tr(modelData.label ?? "")
                        icon: modelData.icon ?? "play_arrow"
                        onClicked: {
                            if (Array.isArray(modelData.command))
                                CUtils.execDetached(modelData.command);
                            else if (modelData.url)
                                Quickshell.openUrlExternally(modelData.url);
                        }
                    }
                }
                RowLayout {
                    TextButton {
                        text: Tr.tr("Roll back version")
                        enabled: !Plugins.busy && (root.selected?.backupCount ?? 0) > 0
                        onClicked: Plugins.rollback(Plugins.selectedId)
                    }
                    TextButton {
                        text: Tr.tr("Remove extension")
                        enabled: !Plugins.busy
                        onClicked: Plugins.remove(Plugins.selectedId)
                    }
                }
            }
        }
        SettingsCard {
            title: Tr.tr("Restore removed extension")
            icon: "extension"
            visible: Plugins.removed.length > 0

            Repeater {
                model: Plugins.removed
                delegate: RowButton {
                    required property var modelData
                    text: Tr.tr(modelData.name) + " · " + modelData.version
                    icon: "restore_from_trash"
                    onClicked: Plugins.restore(modelData.id)
                }
            }
            FeatureError {
                error: Plugins.errors.join("\n")
            }
        }
    }
}
