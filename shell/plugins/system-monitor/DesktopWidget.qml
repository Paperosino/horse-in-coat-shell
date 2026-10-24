import QtQuick
import Hyprstack.Config
import Hyprstack.Services
import qs.components
Column {
    required property var pluginApi
    spacing: Tokens.spacing.small
    StyledText { text: "CPU · " + Math.round(Cpu.percentage * 100) + "%"; font: Tokens.font.title.medium }
    StyledText { visible: pluginApi.settings.showMemory; text: "RAM · " + (Memory.used / 1048576).toFixed(1) + " / " + (Memory.total / 1048576).toFixed(1) + " GiB" }
    ServiceRef { service: Cpu }
    ServiceRef { service: Memory }
}
