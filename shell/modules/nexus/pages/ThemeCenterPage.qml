pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.components.filedialog
import qs.services
import qs.utils
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "palette"
    title: Tr.tr("Themes & automation")
    objectName: "themeCenterPage"
    readonly property FileDialog importDialog: FileDialog {
        title: Tr.tr("Import a colour scheme")
        filterLabel: Tr.tr("Colour schemes")
        filters: ["json", "txt"]
        onAccepted: path => ThemeSchemes.importFile(Paths.toLocalFile(path), Colours.currentLight ? "light" : "dark")
    }
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.extraSmall
        FeatureError {
            error: ThemeSchemes.error
        }
        RowButton {
            text: Tr.tr("Import a colour scheme")
            subtext: Tr.tr("Hyprstack, Noctalia JSON or a three-color palette")
            icon: "file_open"
            onClicked: root.importDialog.open()
        }
        SettingsCard {
            title: Tr.tr("Theme schedule")
            icon: "tune"

            ToggleRow {
                text: Tr.tr("Switch themes by time")
                checked: ThemeAutomation.enabled
                onToggled: ThemeAutomation.save({
                    enabled: checked
                })
            }
            StepperRow {
                label: Tr.tr("Light theme from hour")
                from: 0
                to: 23
                value: ThemeAutomation.lightHour
                onMoved: v => ThemeAutomation.save({
                        lightHour: v
                    })
            }
            StepperRow {
                label: Tr.tr("Dark theme from hour")
                from: 0
                to: 23
                value: ThemeAutomation.darkHour
                onMoved: v => ThemeAutomation.save({
                        darkHour: v
                    })
            }
            GenericSettingRow {
                spec: ({
                        label: "Day theme",
                        type: "choice",
                        choices: [
                            {
                                label: Tr.tr("Current scheme"),
                                value: ""
                            },
                            ...ThemeSchemes.themes.filter(t => t.variants.some(v => v.mode === "light")).map(t => ({
                                        label: t.name,
                                        value: t.id
                                    }))]
                    })
                value: ThemeAutomation.dayTheme
                onEdited: v => ThemeAutomation.save({
                        dayTheme: v
                    })
            }
            GenericSettingRow {
                spec: ({
                        label: "Night theme",
                        type: "choice",
                        choices: [
                            {
                                label: Tr.tr("Current scheme"),
                                value: ""
                            },
                            ...ThemeSchemes.themes.filter(t => t.variants.some(v => v.mode === "dark")).map(t => ({
                                        label: t.name,
                                        value: t.id
                                    }))]
                    })
                value: ThemeAutomation.nightTheme
                onEdited: v => ThemeAutomation.save({
                        nightTheme: v
                    })
            }
        }
        SettingsCard {
            title: Tr.tr("Installed themes")
            icon: "tune"

            Repeater {
                model: ThemeSchemes.themes
                delegate: ColumnLayout {
                    id: theme
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.extraSmall
                    InfoRow {
                        label: theme.modelData.name
                        value: theme.modelData.custom ? Tr.tr("Imported") : Tr.tr("Built in")
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        Repeater {
                            model: theme.modelData.variants.filter(v => v.accent === "default")
                            delegate: TextButton {
                                required property var modelData
                                text: modelData.mode === "dark" ? Tr.tr("Dark") : Tr.tr("Light")
                                enabled: !ThemeSchemes.busy
                                onClicked: ThemeSchemes.apply(theme.modelData.id, modelData.mode)
                            }
                        }
                    }
                }
            }
        }
    }
}
