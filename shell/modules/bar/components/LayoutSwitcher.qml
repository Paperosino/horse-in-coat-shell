pragma ComponentBehavior: Bound
import QtQuick
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
Item {
    id: root
    required property var bar
    implicitWidth: icon.implicitWidth + Tokens.padding.medium * 2
    implicitHeight: Tokens.sizes.bar.innerWidth
    Accessible.role: Accessible.Button
    Accessible.name: Tr.tr("Window layout") + ": " + (LayoutModes.modes.find(m => m.id === LayoutModes.mode)?.label ?? "")
    function open(): void {
        bar.popouts.currentName = "layouts";
        bar.popouts.currentCenter = Qt.binding(() => root.mapToItem(root.bar, root.width / 2, 0).x);
        bar.popouts.hasCurrent = true;
    }
    MaterialIcon {
        id: icon
        anchors.centerIn: parent
        text: LayoutModes.modes.find(m => m.id === LayoutModes.mode)?.icon ?? "grid_view"
        fontStyle: Tokens.font.icon.medium
        color: Colours.palette.m3primary
    }
    StateLayer { onClicked: root.open() }
}
