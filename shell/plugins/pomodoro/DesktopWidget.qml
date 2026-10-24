import QtQuick
import Hyprstack.I18n
import Hyprstack.Config
import qs.components
import qs.components.controls
Column {
    required property var pluginApi
    readonly property var timer: pluginApi.mainInstance
    spacing: Tokens.spacing.small
    StyledText { text: timer?.breakTime ? Tr.tr("Break") : Tr.tr("Focus"); font: Tokens.font.title.medium }
    StyledText { text: Math.floor((timer?.remaining ?? 1500) / 60) + ":" + String((timer?.remaining ?? 1500) % 60).padStart(2, "0"); font: Tokens.font.title.large }
    Row {
        spacing: Tokens.spacing.small
        TextButton { text: timer?.active ? Tr.tr("Pause") : Tr.tr("Start"); onClicked: timer?.toggle() }
        TextButton { text: Tr.tr("Reset"); onClicked: timer?.reset() }
    }
}
