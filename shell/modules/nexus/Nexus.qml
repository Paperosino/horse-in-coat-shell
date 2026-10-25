pragma ComponentBehavior: Bound

import QtQuick
import Hyprstack.Blobs
import Hyprstack.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus

Item {
    id: root

    readonly property NexusState nState: NexusState {
        id: nState

        onClose: root.close()
    }
    property bool navigationExpanded: false
    readonly property bool narrowNavigation: width < 900 * Tokens.scale
    readonly property bool compactNavigation: narrowNavigation && !navigationExpanded
    property real navigationExtent: compactNavigation ? 0 : 1
    Behavior on navigationExtent { enabled: root.narrowNavigation; Anim { type: Anim.FastSpatial } }
    property color blobColour: Colours.tPalette.m3surfaceContainerLow

    signal close

    // Keep settings inside the output, including portrait screens and large UI scales.
    readonly property real availableWidth: Math.max(1, (nState.screen?.width ?? 1280) - Tokens.padding.extraLarge * 2)
    readonly property real availableHeight: Math.max(1, (nState.screen?.height ?? 720) - Tokens.padding.extraLarge * 2)
    implicitWidth: Math.min(availableWidth, Math.max(Tokens.sizes.nexus.minWidth, Math.round(implicitHeight * Tokens.sizes.nexus.ratio)))
    implicitHeight: Math.round(Math.min(840 * Tokens.scale, availableHeight,
        Math.max(Tokens.sizes.nexus.minHeight, (nState.screen?.height ?? 720) * Tokens.sizes.nexus.heightMult * 0.95)))

    Behavior on blobColour {
        CAnim {}
    }

    StyledRect {
        anchors.fill:parent
        radius:Tokens.rounding.extraLarge
        color:Colours.tPalette.m3surface
    }

    TapHandler {
        onTapped: root.focus = true
    }

    BlobGroup {
        id: blobGroup

        smoothing: root.Tokens.rounding.medium
        color: root.blobColour
    }

    BlobInvertedRect {
        anchors.fill: parent
        group: blobGroup
        opacity: root.blobColour.a
        radius: Tokens.rounding.large

        borderLeft: navPane.width + navPane.anchors.margins * 2
        borderRight: Tokens.padding.medium
        borderTop: Tokens.padding.medium
        borderBottom: Tokens.padding.medium
    }

    BlobRect {
        id: windowBtnRect

        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.nState.isWindow ? 0 : Tokens.padding.extraSmall

        group: blobGroup
        opacity: root.blobColour.a
        radius: Tokens.rounding.medium

        implicitWidth: windowBtn.implicitWidth + (root.nState.isWindow ? Tokens.padding.extraSmall : Tokens.padding.small) * 2
        implicitHeight: windowBtn.implicitHeight + (root.nState.isWindow ? Tokens.padding.extraSmall : Tokens.padding.small)
    }

    IconButton {
        id: windowBtn

        anchors.centerIn: windowBtnRect
        icon: nState.isWindow ? "close" : "pip"
        type: IconButton.Text
        label.fill: 0
        inactiveOnColour: hovered ? nState.isWindow ? Colours.palette.m3error : Colours.palette.m3primary : Colours.palette.m3onSurfaceVariant
        stateLayer.opacity: 0
        onClicked: {
            if (!nState.isWindow)
                WindowFactory.create();
            root.close();
        }

        label.scale: pressed ? 0.8 : 1
        label.renderType: Text.QtRendering

        Behavior on label.scale {
            Anim {}
        }
    }

    NavPane {
        id: navPane

        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.margins: Tokens.padding.large

        nState: nState
        compact: root.compactNavigation
        collapsible: root.narrowNavigation
        onExpansionRequested: root.navigationExpanded = true
        onCollapseRequested: root.navigationExpanded = false
        width: 68 * Tokens.scale + (Math.min(Tokens.sizes.nexus.maxNavWidth, 260 * Tokens.scale, Math.round(root.width / 3)) - 68 * Tokens.scale) * root.navigationExtent
    }

    Connections {
        target: nState
        function onCurrentPageIdxChanged(): void { root.navigationExpanded = false; }
        function onSectionIdChanged(): void { root.navigationExpanded = false; }
    }
    Shortcut {
        sequences: [StandardKey.Find, "Ctrl+E"]
        enabled: root.visible
        onActivated: { root.navigationExpanded = true; Qt.callLater(navPane.focusSearch); }
    }

    Pages {
        anchors.left: navPane.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: navPane.anchors.margins + anchors.margins
        anchors.margins: Tokens.padding.extraLarge

        nState: nState
    }
}
