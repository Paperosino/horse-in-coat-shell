import QtQuick
import Hyprstack.Config
import qs.components.controls
TextButton {
    required property var pluginApi
    readonly property var timer: pluginApi.mainInstance
    text: "◷ " + Math.floor((timer?.remaining ?? 1500) / 60) + ":" + String((timer?.remaining ?? 1500) % 60).padStart(2, "0")
    onClicked: timer?.toggle()
}
