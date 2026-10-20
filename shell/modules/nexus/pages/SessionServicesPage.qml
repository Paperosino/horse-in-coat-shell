pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    property bool autostartOnly: false
    title: autostartOnly ? Tr.tr("Autostart") : Tr.tr("User services and timers")
    objectName: "sessionServicesPage"
    Component.onCompleted: autostartOnly ? SystemControls.reloadAutostart() : SystemControls.reloadUnits()
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.extraSmall
        FeatureError { error: SystemControls.error }
        ColumnLayout {
            Layout.fillWidth: true
            visible: root.autostartOnly
            SectionHeader { first: true; text: Tr.tr("Autostart") }
            Repeater {
                model: SystemControls.autostart
                delegate: ToggleRow {
                    required property var modelData
                    text: modelData.name
                    subtext: modelData.command
                    checked: modelData.enabled
                    enabled: !SystemControls.busy
                    onToggled: SystemControls.setAutostart(modelData.id, checked)
                }
            }
            TextFieldRow { id: appName; label: Tr.tr("Name"); value: "" }
            TextFieldRow { id: appCommand; label: Tr.tr("Command"); value: "" }
            RowButton {
                text: Tr.tr("Add autostart application"); icon: "add"
                disabled: !appName.field.text.trim() || !appCommand.field.text.trim() || SystemControls.busy
                onClicked: { SystemControls.addAutostart(appName.field.text, appCommand.field.text); appName.clear(); appCommand.clear(); }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: !root.autostartOnly
            SectionHeader { text: Tr.tr("User services and timers") }
            SearchBar { id: query; Layout.fillWidth: true; placeholderText: Tr.tr("Filter services") }
            ToggleRow { id: showAll; text: Tr.tr("Show inactive services"); checked: false }
            Repeater {
                model: SystemControls.units.filter(u => (showAll.checked || u.active === "active" || u.enabled) && (!query.text || u.id.toLowerCase().includes(query.text.toLowerCase())))
                delegate: ColumnLayout {
                    id: unit
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0
                    ToggleRow {
                        text: unit.modelData.id
                        subtext: unit.modelData.active + " · " + unit.modelData.sub + " · " + unit.modelData.state
                        checked: unit.modelData.enabled
                        enabled: !SystemControls.busy && !["static", "indirect", "masked"].includes(unit.modelData.state)
                        onToggled: SystemControls.service(checked ? "enable" : "disable", unit.modelData.id)
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        TextButton { text: Tr.tr("Start"); enabled: !SystemControls.busy; onClicked: SystemControls.service("start", unit.modelData.id) }
                        TextButton { text: Tr.tr("Stop"); enabled: !SystemControls.busy; onClicked: SystemControls.service("stop", unit.modelData.id) }
                        TextButton { text: Tr.tr("Restart"); enabled: !SystemControls.busy; onClicked: SystemControls.service("restart", unit.modelData.id) }
                    }
                }
            }
        }
        RowButton { text: Tr.tr("Refresh"); icon: "refresh"; onClicked: root.autostartOnly ? SystemControls.reloadAutostart() : SystemControls.reloadUnits() }
    }
}
