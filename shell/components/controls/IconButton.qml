import QtQuick
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services

ButtonBase {
    id: root

    Accessible.name: Tr.tr(({close:"Close",add:"Add",edit:"Edit",delete:"Delete",settings:"Settings",search:"Search",refresh:"Refresh",arrow_back:"Back",arrow_forward:"Forward",arrow_upward:"Move up",arrow_downward:"Move down",check:"Confirm",undo:"Undo",lock:"Lock",lock_open:"Unlock"})[root.icon] ?? root.icon.replace(/_/g," "))
    property alias icon: label.text
    readonly property alias label: label

    font: Tokens.font.icon.medium
    padding: type === IconButton.Text ? Tokens.padding.extraSmall / 2 : Tokens.padding.small

    activeColour: type === IconButton.Filled ? Colours.palette.m3primary : Colours.palette.m3secondary
    inactiveColour: {
        if (!isToggle && type === IconButton.Filled)
            return Colours.palette.m3primary;
        return type === IconButton.Filled ? Colours.tPalette.m3surfaceContainer : Colours.palette.m3secondaryContainer;
    }
    activeOnColour: type === IconButton.Filled ? Colours.palette.m3onPrimary : type === IconButton.Tonal ? Colours.palette.m3onSecondary : Colours.palette.m3primary
    inactiveOnColour: {
        if (!isToggle && type === IconButton.Filled)
            return Colours.palette.m3onPrimary;
        return type === IconButton.Tonal ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant;
    }

    implicitWidth: implicitHeight
    implicitHeight: {
        // Ensure even size so icon is centered properly
        const h = label.implicitHeight + padding * 2;
        if (h % 2 !== 0)
            return h + 1;
        return h;
    }

    MaterialIcon {
        id: label

        anchors.centerIn: parent
        anchors.verticalCenterOffset: 1 // AHHHHHHH material symbols whyyyy
        color: root.onColour
        fontStyle: root.font
        fill: !root.isToggle || root.internalChecked ? 1 : 0

        Behavior on fill {
            Anim {
                type: Anim.DefaultEffects
            }
        }
    }
}
