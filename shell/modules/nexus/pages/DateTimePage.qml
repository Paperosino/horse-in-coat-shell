pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "schedule"
    title: Tr.tr("Date & time")
    property string zoneQuery
    property string manualDate: Qt.formatDateTime(new Date(), "dd.MM.yyyy")
    property string manualClock: Qt.formatDateTime(new Date(), "HH:mm")
    readonly property string manualTime: manualDate.split(".").reverse().join("-") + "T" + manualClock + ":00"
    readonly property bool validManualTime: /^\d{2}\.\d{2}\.\d{4}$/.test(manualDate) && /^\d{2}:\d{2}$/.test(manualClock)
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large
        NativeSystemBackend {
            id: system
            section: "datetime"
            watching: root.visible
        }
        FeatureError {
            error: system.error
        }
        SettingsCard {
            title: Tr.tr("System time")
            icon: "schedule"
            InfoRow {
                first: true
                label: Tr.tr("System time")
                value: (system.state.localTime ?? "").replace("T", " ").replace(/[+-]\d{2}:\d{2}$/, "")
            }
            InfoRow {
                last: true
                label: Tr.tr("Time zone")
                value: system.state.timezone ?? ""
            }
            ToggleRow {
                first: true
                text: Tr.tr("Automatic network time")
                checked: !!system.state.ntp
                enabled: !!system.state.canNtp && !system.busy
                onToggled: system.apply("ntp", {
                    enabled: checked
                })
            }
            InfoRow {
                last: true
                label: Tr.tr("Clock synchronization")
                value: system.state.synchronized ? Tr.tr("Synchronized") : Tr.tr("Not synchronized")
            }
        }
        SettingsCard {
            title: Tr.tr("Time zone")
            icon: "schedule"

            SearchBar {
                Layout.fillWidth: true
                placeholderText: Tr.tr("Search time zones")
                onTextChanged: root.zoneQuery = text
            }
            Repeater {
                model: root.zoneQuery.length > 1 ? (system.state.timezones ?? []).filter(z => z.toLowerCase().includes(root.zoneQuery.toLowerCase())).slice(0, 12) : []
                RowButton {
                    required property string modelData
                    text: modelData
                    icon: "globe"
                    trailingIcon: system.state.timezone === modelData ? "check" : ""
                    disabled: system.busy
                    onClicked: system.apply("timezone", {
                        timezone: modelData
                    })
                }
            }
        }
        SettingsCard {
            title: Tr.tr("Set time manually")
            icon: "schedule"

            TextFieldRow {
                first: true
                label: Tr.tr("Date")
                value: root.manualDate
                placeholderText: "19.10.2026"
                maximumLength: 10
                enabled: !system.state.ntp
                onValueEdited: v => root.manualDate = v
            }
            TextFieldRow {
                label: Tr.tr("Time")
                value: root.manualClock
                placeholderText: "14:45"
                maximumLength: 5
                enabled: !system.state.ntp
                onValueEdited: v => root.manualClock = v
            }
            RowButton {
                last: true
                text: Tr.tr("Set system time")
                subtext: Tr.tr("Turn off automatic network time before setting the clock manually")
                icon: "schedule"
                disabled: system.busy || system.state.ntp || !root.validManualTime
                onClicked: system.apply("time", {
                    time: root.manualTime
                })
            }
        }
    }
}
