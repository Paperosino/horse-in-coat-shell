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

    readonly property bool disabled: Strings.testRegexList(Config.bar.excludedScreens, screen.name)

    readonly property bool atBottom: Hypr.stacking
    readonly property var activeWorkspace: Hypr.monitorFor(screen)?.activeWorkspace
    readonly property int clampedThickness: Math.max((Config.border.minThickness * Tokens.scale), implicitHeight)
    readonly property real frameThickness: (Tiling.desktopFrame ? (Config.border.thickness * Tokens.scale) : 0) * (1 - Hypr.stackingProgress)
    readonly property real topInset: implicitHeight * (1 - Hypr.stackingProgress) + (fullscreen ? 0 : frameThickness) * Hypr.stackingProgress
    readonly property real bottomInset: implicitHeight * Hypr.stackingProgress + (fullscreen ? 0 : frameThickness) * (1 - Hypr.stackingProgress)
    readonly property int padding: Math.max(Tokens.padding.small, (Config.border.thickness * Tokens.scale))
    readonly property int contentWidth: Hypr.stacking ? 40 * Tokens.scale : Tokens.sizes.bar.innerWidth + padding * 2
    readonly property int exclusiveZone: !disabled && (Config.bar.persistent || screenState.bar) ? contentWidth : frameThickness
    readonly property bool shouldBeVisible: !fullscreen && !disabled && (Config.bar.persistent || screenState.bar || isHovered)
    property bool isHovered
    property bool popoutHoverPaused
    property point lastHoverPosition
    property point pausedHoverPosition

    function closeTray(): void {
        content.closeTray();
    }

    function checkPopout(x: real, y: real): void {
        lastHoverPosition = Qt.point(x, y);
        if (popoutHoverPaused && x === pausedHoverPosition.x && y === pausedHoverPosition.y)
            return;
        popoutHoverPaused = false;
        content.checkPopout(x);
    }

    function resumePopoutHover(): void {
        popoutHoverPaused = false;
    }

    function handleWheel(x: real, angleDelta: point): void {
        content.handleWheel(x, angleDelta);
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
    // Slide the new bar in from its edge while the frame changes shape.
    y: atBottom ? (parent?.height ?? 0) - height * Hypr.stackingProgress : -height * Hypr.stackingProgress

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

    Bar {
        id: content

        anchors.left: parent.left
        anchors.right: parent.right
        height: root.contentWidth
        y: root.atBottom ? 0 : root.height - height

        visible: root.shouldBeVisible
        opacity: root.atBottom ? Hypr.stackingProgress : 1 - Hypr.stackingProgress
        screen: root.screen
        screenState: root.screenState
        popouts: root.popouts // qmllint disable incompatible-type
        fullscreen: root.fullscreen
    }

}
