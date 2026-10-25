pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus
import qs.modules.nexus.common
PageBase {
    id: root
    objectName: "settingsSectionOverview"
    readonly property var section: PageRegistry.section(nState.sectionId)
    readonly property bool home: section.id === "home"
    title: home ? Tr.tr("Settings") : section.label
    pageIcon: section.icon
    pageDescription: section.description
    isSubPage: false
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large
        SettingsCard {
            visible: root.home
            title: Tr.tr("Quick access")
            icon: "tune"
            description: Tr.tr("Common settings, one step away")
            GridLayout {
                Layout.fillWidth: true
                columns: width >= 700 * Tokens.scale ? 2 : 1
                columnSpacing: Tokens.spacing.small
                rowSpacing: Tokens.spacing.small
                Repeater {
                    model: root.home ? PageRegistry.entries(["display","audio","network","appearance"]) : []
                    SettingsLink {
                        required property var modelData
                        objectName: "settings-link-" + modelData.id
                        title: modelData.label
                        description: modelData.description
                        icon: modelData.icon
                        compact: true
                        onClicked: root.nState.openPage(modelData.id)
                    }
                }
            }
        }
        StyledText { visible: root.home; text: Tr.tr("All settings"); font: Tokens.font.title.medium; Accessible.role: Accessible.Heading }
        GridLayout {
            visible: root.home
            Layout.fillWidth: true
            columns: width >= 760 * Tokens.scale ? 2 : 1
            columnSpacing: Tokens.spacing.medium
            rowSpacing: Tokens.spacing.medium
            Repeater {
                model: root.home ? PageRegistry.sections.slice(1) : []
                SettingsLink {
                    required property var modelData
                    objectName: "settings-link-" + modelData.id
                        title: modelData.label
                    description: modelData.description
                    icon: modelData.icon
                    onClicked: root.nState.openSection(modelData.id)
                }
            }
        }
        Repeater {
            model: root.home ? [] : root.section.groups
            SettingsCard {
                required property var modelData
                objectName: "settings-link-" + modelData.id
                        title: modelData.label
                icon: root.section.icon
                Repeater {
                    model: PageRegistry.entries(modelData.pages)
                    SettingsLink {
                        required property var modelData
                        objectName: "settings-link-" + modelData.id
                        title: modelData.label
                        description: modelData.description
                        icon: modelData.icon
                        compact: true
                        onClicked: root.nState.openPage(modelData.id)
                    }
                }
            }
        }
        SettingsCard {
            visible: root.section.id === "privacy"
            title: Tr.tr("Application permissions")
            icon: "shield"
            description: Tr.tr("Choose an installed application to manage its permissions, AppArmor profile and startup behaviour.")
            SettingsLink { title: Tr.tr("Installed applications"); icon: "apps"; compact: true; onClicked: root.nState.openPage("apps") }
        }
    }
}
