import QtQuick
import qs.components
import qs.services

Item {
    id: root

    required property ScreenState screenState
    required property Item sidebarPanel
    property alias originY: content.originY
    property alias availableHeight: content.availableHeight
    property alias osdPanel: content.osdPanel
    property alias sessionPanel: content.sessionPanel
    property alias utilitiesPanel: content.utilitiesPanel

    visible: height > 0 && !(Presentation.privateOn(root.screenState.modelData))
    anchors.topMargin: -5
    implicitWidth: Math.max(sidebarPanel.width, content.implicitWidth)
    // Content keeps its expressive height animation. The outer viewport must
    // obey the current free space immediately while another popout moves;
    // animating the capacity itself lets notifications spill below the screen.
    implicitHeight: Math.max(0, Math.min(availableHeight, content.implicitHeight))

    Content {
        id: content

        // The parent margin also includes space reserved for a status popup.
        // Only compensate the fixed five-pixel join, not that placement.
        anchors.topMargin: 5
        screenState: root.screenState
    }
}
