pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus

FloatingWindow {
    id: win

    property string pageId: ""
    property string panelId: ""

    color: Colours.tPalette.m3surface
    surfaceFormat.opaque: false

    onVisibleChanged: {
        if (!visible)
            destroy();
    }

    implicitWidth: nexus.implicitWidth
    implicitHeight: nexus.implicitHeight

    minimumSize.width: Math.min(contentItem.Tokens.sizes.nexus.minWidth, nexus.availableWidth)
    minimumSize.height: Math.min(contentItem.Tokens.sizes.nexus.minHeight, nexus.availableHeight)

    contentItem.Config.screen: screen.name
    contentItem.Tokens.screen: screen.name

    title: Tr.tr("Nexus — %1").arg((nexus.nState.showingSection ? PageRegistry.section(nexus.nState.sectionId).label : PageRegistry.pages[nexus.nState.currentPageIdx].label))

    Nexus {
        id: nexus

        anchors.fill: parent
        nState.screen: win.screen
        nState.isWindow: true
        Component.onCompleted: if (win.pageId) {
            nState.requestedPanelId = win.panelId;
            nState.openPage(win.pageId);
        }
        onClose: win.destroy()
    }

    Behavior on color {
        CAnim {}
    }
}
