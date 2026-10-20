import QtQuick
import Quickshell
import Hyprstack.Config
import qs.components
import qs.services
import qs.modules.dock as Dock
import qs.modules.bar as Bar
import qs.modules.dashboard as Dashboard
import qs.modules.launcher as Launcher
import qs.modules.notifications as Notifications
import qs.modules.osd as Osd
import qs.modules.session as Session
import qs.modules.sidebar as Sidebar
import qs.modules.utilities as Utilities
import qs.modules.bar.popouts as BarPopouts
import qs.modules.utilities.toasts as Toasts
import qs.modules.clipboard as ClipboardDrawer

Item {
    id: root

    required property ShellScreen screen
    required property ScreenState screenState
    required property Bar.BarWrapper bar
    required property real borderThickness

    readonly property alias dock: dock
    readonly property alias osd: osd
    readonly property alias osdWrapper: osdWrapper
    readonly property alias notifications: notifications
    readonly property alias session: session
    readonly property alias sessionWrapper: sessionWrapper
    readonly property alias launcher: launcher
    readonly property alias dashboard: dashboard
    readonly property alias clipboard: clipboard
    readonly property alias popouts: popoutsWrapper.content
    readonly property alias popoutsWrapper: popoutsWrapper
    readonly property alias utilities: utilities
    readonly property alias toasts: toasts
    readonly property alias sidebar: sidebar
    readonly property real sidebarTop: bar.atBottom ? 0
        : notifications.y + notifications.height - notifications.anchors.topMargin

    anchors.fill: parent
    anchors.margins: borderThickness
    anchors.topMargin: bar.topInset
    anchors.bottomMargin: bar.bottomInset

    Item {
        id: osdWrapper

        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: sessionWrapper.anchors.rightMargin + session.width * (1 - session.offsetScale)
        clip: sidebar.visible || session.visible

        implicitWidth: osd.implicitWidth * (1 - osd.offsetScale)
        implicitHeight: osd.implicitHeight

        Osd.Wrapper {
            id: osd

            screen: root.screen
            screenState: root.screenState
            sidebarOrSessionVisible: sidebar.visible || session.visible

            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
        }
    }

    Notifications.Wrapper {
        id: notifications

        screenState: root.screenState
        sidebarPanel: sidebar
        osdPanel: osdWrapper
        sessionPanel: sessionWrapper
        utilitiesPanel: utilities

        anchors.top: parent.top
        anchors.right: parent.right
    }

    Item {
        id: sessionWrapper

        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: sidebar.width * (1 - sidebar.offsetScale)
        clip: sidebar.visible

        implicitWidth: session.implicitWidth * (1 - session.offsetScale)
        implicitHeight: session.implicitHeight

        Session.Wrapper {
            id: session

            screenState: root.screenState
            sidebarVisible: sidebar.visible

            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
        }
    }

    Dock.DockContent {
        id: dock
        screen: root.screen
        screenState: root.screenState
        panelVisible: !root.bar.fullscreen && !root.bar.disabled
        readonly property real dashboardDepth: dashboard.visible ? Math.max(0, Math.min(dashboard.height, dashboard.atBottom ? root.height - dashboard.y : dashboard.y + dashboard.height)) : 0
        readonly property real rightDepth: Math.max(sidebar.visible ? sidebar.width * (1 - sidebar.offsetScale) : 0,
            session.visible ? sessionWrapper.width : 0, osd.visible ? osdWrapper.width : 0)
        readonly property real bottomLift: DockConf.position === "bottom" && dashboard.atBottom ? dashboardDepth : 0
        readonly property real topLift: DockConf.position === "top" && !dashboard.atBottom ? dashboardDepth : 0
        property real horizontalAnchor: DockConf.position === "left" ? 0 : DockConf.position === "right" ? 1 : 0.5
        property real verticalAnchor: DockConf.position === "top" ? 0 : DockConf.position === "bottom" ? 1 : 0.5
        Behavior on horizontalAnchor { Anim {} }
        Behavior on verticalAnchor { Anim {} }
        readonly property real baseX: (root.width - width) * horizontalAnchor
        readonly property real baseY: (root.height - height) * verticalAnchor
        maxWidth: root.width
        viewportHeight: root.height
        maxHeight: Math.max(0, root.height - bottomLift - topLift)
        x: baseX - (DockConf.position === "right" ? rightDepth : 0)
        y: baseY - bottomLift + topLift
    }

    Launcher.Wrapper {
        id: launcher

        screen: root.screen
        screenState: root.screenState
        panels: root

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
    }

    Dashboard.Wrapper {
        id: dashboard

        screenState: root.screenState
        atBottom: !root.bar.atBottom

        anchors.horizontalCenter: parent.horizontalCenter
    }

    ClipboardDrawer.Wrapper {
        id: clipboard

        screenState: root.screenState
        atBottom: root.bar.atBottom

        anchors.horizontalCenter: parent.horizontalCenter
    }

    BarPopouts.ClipWrapper {
        id: popoutsWrapper

        screen: root.screen
        borderThickness: root.borderThickness
        atBottom: root.bar.atBottom
    }

    Utilities.Wrapper {
        id: utilities

        screenState: root.screenState
        sidebar: sidebar
        popouts: popoutsWrapper.content
        atBottom: screenState.sidebar || sidebar.visible || !root.bar.atBottom

        y: atBottom ? parent.height - height
            + (root.bar.atBottom && sidebar.visible ? sidebar.slideDistance : height + 5) * offsetScale
            : -(height + 5) * offsetScale
        anchors.right: parent.right
    }

    Toasts.Toasts {
        id: toasts

        anchors.bottom: sidebar.visible || !utilities.atBottom ? parent.bottom : utilities.top
        anchors.right: sidebar.left
        anchors.margins: Tokens.padding.medium
    }

    Sidebar.Wrapper {
        id: sidebar

        screenState: root.screenState
        atBottom: root.bar.atBottom
        slideDistance: root.height - root.sidebarTop + 5
        readyToOpen: sidebar.contentPrepared && (!Config.utilities.enabled || utilities.contentPrepared)

        anchors.top: notifications.bottom
        anchors.bottom: utilities.atBottom ? utilities.top : parent.bottom
        anchors.right: parent.right
        anchors.topMargin: -notifications.anchors.topMargin

        states: State {
            name: "bottom"
            when: sidebar.atBottom

            AnchorChanges {
                target: sidebar
                anchors.top: undefined
                anchors.bottom: undefined
            }

            PropertyChanges {
                sidebar.y: root.sidebarTop + sidebar.slideDistance * sidebar.offsetScale
                sidebar.height: Math.max(0, root.height - root.sidebarTop - utilities.height)
            }
        }
    }
}
