pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Config
import qs.components
import qs.services

Item {
    id: root
    required property ShellScreen screen
    Repeater {
        model: ScriptModel { values: Plugins.enabled.filter(p => !!p.entryPoints.desktopWidget).map(p => p.id) }
        delegate: StyledRect {
            id: frame
            required property string modelData
            readonly property var api: Plugins.apiFor(modelData)
            x: Number(api?.settings.desktopX ?? 32)
            y: Number(api?.settings.desktopY ?? 32)
            width: widget.implicitWidth + Tokens.padding.medium * 2
            height: widget.implicitHeight + Tokens.padding.medium * 2
            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainer
            PluginSlot {
                id: widget
                anchors.centerIn: parent
                pluginId: frame.modelData
                slot: "desktopWidget"
                onLoaded: if ("screenName" in item) item.screenName = root.screen.name
            }
            DragHandler {
                target: frame
                onActiveChanged: if (!active && frame.api) {
                    Plugins.saveSettings(frame.modelData, Object.assign({}, frame.api.pluginSettings, {desktopX: frame.x, desktopY: frame.y}));
                }
            }
        }
    }
}
