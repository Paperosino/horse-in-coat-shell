import QtQuick
import Hyprstack.Config
import qs.components.controls
IconButton {
    required property var pluginApi
    icon: "search"
    onClicked: pluginApi.openPanel()
}
