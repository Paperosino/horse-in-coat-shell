pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Config
import qs.services

Row {
    id: root
    required property ShellScreen screen
    spacing: Tokens.spacing.small
    Repeater {
        model: ScriptModel { values: Plugins.enabled.filter(p => !!p.entryPoints.barWidget).map(p => p.id) }
        delegate: PluginSlot {
            required property string modelData
            pluginId: modelData
            slot: "barWidget"
            width: item?.implicitWidth ?? 0
            height: item?.implicitHeight ?? 0
            anchors.verticalCenter: parent.verticalCenter
            onLoaded: {
                if ("screenName" in item) item.screenName = root.screen.name;
                if ("screen" in item) item.screen = root.screen;
                if ("barWindow" in item) item.barWindow = QsWindow.window;
            }
        }
    }
}
