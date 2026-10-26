pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Hyprstack.Config
import qs.components
import qs.utils
import qs.services
import qs.modules.bar.popouts as BarPopouts

Item {
    id: root

    required property ShellScreen screen
    required property ScreenState screenState
    required property BarPopouts.Wrapper popouts
    required property bool fullscreen
    readonly property alias content: content
    readonly property alias settingsMenu: contextMenu

    readonly property bool disabled: Strings.testRegexList(Config.bar.excludedScreens, screen.name)

    property string panelId: ""
    property bool atBottom: false
    property real thicknessOverride: 0
    property bool desktopFrame: true
    readonly property var activeWorkspace: Hypr.monitorFor(screen)?.activeWorkspace
    readonly property int clampedThickness: Math.max((Config.border.minThickness * Tokens.scale), implicitHeight)
    readonly property real frameThickness: (desktopFrame && Tiling.desktopFrame ? (Config.border.thickness * Tokens.scale) : 0) * (1 - Hypr.stackingProgress)
    readonly property real topInset: implicitHeight
    readonly property real bottomInset: fullscreen ? 0 : frameThickness
    readonly property int padding: Math.max(Tokens.padding.small, (Config.border.thickness * Tokens.scale))
    readonly property real panelScale: Math.max(0.65, Math.min(1.5, Config.bar.scale))
    readonly property int contentWidth: Math.round((thicknessOverride > 0 ? thicknessOverride : Tokens.sizes.bar.innerWidth + padding * 2) * panelScale)
    readonly property int exclusiveZone: !disabled && (Config.bar.persistent || screenState.bar) ? contentWidth : frameThickness
    readonly property bool shouldBeVisible: !fullscreen && !disabled && (Config.bar.persistent || screenState.bar || isHovered)
    property bool isHovered
    property bool popoutHoverPaused
    property point lastHoverPosition
    property point pausedHoverPosition

    function openContext(x: real): void {
        popouts.close();
        contextMenu.show(x, atBottom, content.contextIdAt(x / panelScale));
    }

    function closeTray(): void {
        content.closeTray();
    }

    function checkPopout(x: real, y: real): void {
        lastHoverPosition = Qt.point(x, y);
        if (popoutHoverPaused && x === pausedHoverPosition.x && y === pausedHoverPosition.y)
            return;
        popoutHoverPaused = false;
        content.checkPopout(x / panelScale);
    }

    function resumePopoutHover(): void {
        popoutHoverPaused = false;
    }

    function handleWheel(x: real, angleDelta: point): void {
        content.handleWheel(x / panelScale, angleDelta);
    }

    clip: true
    onActiveWorkspaceChanged: {
        popouts.close();
        pausedHoverPosition = lastHoverPosition;
        popoutHoverPaused = true;
    }
    onAtBottomChanged: {
        popouts.close();
        screenState.dashboard = false;
        screenState.launcher = false;
    }

    visible: height > frameThickness
    implicitWidth: parent?.width ?? 0
    implicitHeight: fullscreen ? 0 : frameThickness
    y: 0

    states: State {
        name: "visible"
        when: root.shouldBeVisible

        PropertyChanges {
            root.implicitHeight: root.contentWidth
        }
    }

    transitions: [
        Transition {
            from: ""
            to: "visible"

            Anim {
                target: root
                property: "implicitHeight"
            }
        },
        Transition {
            from: "visible"
            to: ""

            Anim {
                target: root
                property: "implicitHeight"
                type: Anim.Emphasized
            }
        }
    ]

    PanelContextMenu { id: contextMenu; anchor.item: root; panelId: root.panelId }
    TapHandler {
        acceptedButtons: Qt.RightButton
        gesturePolicy: TapHandler.ReleaseWithinBounds
        onTapped: point => root.openContext(point.position.x)
    }

    Bar {
        id: content

        width: root.width / root.panelScale
        height: root.contentWidth / root.panelScale
        scale: root.panelScale
        transformOrigin: Item.TopLeft
        y: root.height - height * root.panelScale

        visible: root.shouldBeVisible
        opacity: 1
        screen: root.screen
        screenState: root.screenState
        popouts: root.popouts // qmllint disable incompatible-type
        fullscreen: root.fullscreen
    }

}
