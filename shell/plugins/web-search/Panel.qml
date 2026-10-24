import QtQuick
import Quickshell
import Hyprstack.I18n
import Hyprstack.Config
import qs.components.controls
Column {
    required property var pluginApi
    spacing: Tokens.spacing.medium
    StyledTextField {
        id: query
        width: parent.width
        placeholderText: Tr.tr("Search the web")
        onAccepted: if (text.trim()) Quickshell.openUrlExternally((pluginApi.settings.engine ?? "https://duckduckgo.com/?q=%s").replace("%s", encodeURIComponent(text)))
    }
    TextButton { text: Tr.tr("Search"); onClicked: query.accepted() }
}
