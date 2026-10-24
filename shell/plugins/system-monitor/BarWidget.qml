import QtQuick
import Hyprstack.Config
import Hyprstack.Services
import qs.components
Item {
    required property var pluginApi
    implicitHeight: 28 * Tokens.scale
    implicitWidth: label.implicitWidth
    StyledText {
        id: label
        anchors.fill: parent
        text: "CPU " + Math.round(Cpu.percentage * 100) + "%" + (pluginApi.settings.showMemory ? " · RAM " + Math.round(Memory.used / Math.max(1, Memory.total) * 100) + "%" : "")
        font: Tokens.font.body.small
        verticalAlignment: Text.AlignVCenter
    }
    ServiceRef { service: Cpu }
    ServiceRef { service: Memory }
}
