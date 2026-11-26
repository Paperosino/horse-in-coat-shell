pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.modules.nexus.common
import qs.services

Item {
    id: root
    objectName:"windowMenu"
    required property ShellScreen screen
    property var request: null
    readonly property var window: Hypr.toplevels.values.find(w => w.lastIpcObject.address === request?.address && w.lastIpcObject.stableId === request?.stableId) ?? null
    visible: request !== null
    focus: visible
    onWindowChanged: if (!window) request = null
    Keys.onEscapePressed: request = null
    function act(operation: string): void {
        const target = window;
        request = null;
        if (!target) return;
        if (operation === "overview") Overview.toggle();
        else Hypr.windowAction(operation,target);
    }
    Connections {
        target: Hypr
        function onTitlebarMenuRequested(data): void {
            if (data.monitor !== Hypr.monitorFor(root.screen)?.name || !Hypr.stacking) { root.request=null; return; }
            ShellState.closeDrawers();
            root.request=data;
            root.forceActiveFocus();
        }
    }
    MouseArea { anchors.fill:parent; acceptedButtons:Qt.AllButtons; onClicked:root.request=null }
    StyledRect {
        id: menu
        objectName: "titlebarContextMenu"
        x: Math.max(0,Math.min(root.width-width,(root.request?.x??0)-(Hypr.monitorFor(root.screen)?.lastIpcObject.x??0)))
        y: Math.max(0,Math.min(root.height-height,(root.request?.y??0)-(Hypr.monitorFor(root.screen)?.lastIpcObject.y??0)))
        width: Math.min(root.width,300*Tokens.scale)
        height: Math.min(root.height,rows.implicitHeight+Tokens.padding.small*2)
        radius:Tokens.rounding.large
        color:Colours.palette.m3surfaceContainer
        border.width:1; border.color:Colours.palette.m3outlineVariant
        MouseArea {anchors.fill:parent;acceptedButtons:Qt.AllButtons;onWheel:event=>event.accepted=true}
        Flickable {
            anchors.fill:parent;anchors.margins:Tokens.padding.small
            contentHeight:rows.implicitHeight;clip:true
            Column {
                id:rows;width:parent.width;spacing:2*Tokens.scale
                Action {text:Hypr.windowState(root.window).keep_above?Tr.tr("Allow other windows above"):Tr.tr("Keep above other windows");icon:"keep";trailingIcon:Hypr.windowState(root.window).keep_above?"check":"";operation:"keep-above"}
                Action {text:Tr.tr("Minimize");icon:"minimize";operation:"minimize"}
                Action {text:Tr.tr("Maximize or restore");icon:"crop_square";operation:"maximize"}
                Action {text:Tr.tr("Fullscreen");icon:"fullscreen";operation:"fullscreen"}
                Action {text:Tr.tr("Decrease window size");icon:"zoom_out";operation:"size-down"}
                Action {text:Tr.tr("Restore window size");icon:"restart_alt";operation:"size-reset"}
                Action {text:Tr.tr("Increase window size");icon:"zoom_in";operation:"size-up"}
                Action {text:Tr.tr("Center window");icon:"center_focus_strong";operation:"center"}
                Action {text:Tr.tr("Show all windows");icon:"overview";operation:"overview"}
                Action {text:Tr.tr("Close");icon:"close";operation:"close"}
            }
        }
    }
    component Action: RowButton {
        required property string operation
        objectName:"windowAction_"+operation
        width:parent.width
        onClicked:root.act(operation)
    }
}
