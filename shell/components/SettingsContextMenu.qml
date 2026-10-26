pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components.controls
import qs.services
import qs.modules.nexus.common
import qs.modules.nexus

PopupWindow {
    id: root
    property var actions: []
    property real entrance: 1
    onVisibleChanged: {
        entranceAnimation.stop();
        if (visible) { entrance = 0; entranceAnimation.restart(); }
    }
    Anim { id: entranceAnimation; target: root; property: "entrance"; to: 1; type: Anim.FastSpatial }
    property string panelId: ""
    color: "transparent"
    grabFocus: true
    implicitWidth: 300 * contentItem.Tokens.scale
    implicitHeight: column.implicitHeight + 16 * contentItem.Tokens.scale

    function openAt(item: Item, x: real, y: real, above: bool): void {
        visible = false;
        anchor.item = item;
        anchor.rect.x = x;
        anchor.rect.y = y;
        anchor.rect.width = 1;
        anchor.rect.height = 1;
        anchor.edges = above ? Edges.Top : Edges.Bottom;
        anchor.gravity = above ? Edges.Top : Edges.Bottom;
        visible = true;
    }

    Rectangle {
        opacity: root.entrance
        scale: 0.94 + root.entrance * 0.06
        anchors.fill: parent
        radius: Tokens.rounding.large
        color: Colours.palette.m3surfaceContainer
        border.width: 1
        border.color: Colours.palette.m3outlineVariant
        focus: true
        Keys.onEscapePressed: root.visible = false
        ColumnLayout {
            id: column
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 8 * Tokens.scale
            spacing: 2 * Tokens.scale
            Repeater {
                model: root.actions
                RowButton {
                    required property var modelData
                    text: Tr.tr(modelData.label)
                    icon: modelData.icon ?? "settings"
                    onClicked: {
                        root.visible = false;
                        if (modelData.page === "statusbar-layout") WindowFactory.openPanelSettings(root.panelId);
                        else WindowFactory.openPage(modelData.page);
                    }
                }
            }
        }
    }
}
