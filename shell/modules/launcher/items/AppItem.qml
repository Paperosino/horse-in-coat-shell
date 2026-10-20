import QtQuick
import Quickshell
import Quickshell.Widgets
import Hyprstack.I18n
import qs.components.controls
import Hyprstack.Config
import qs.components
import qs.services
import qs.utils
import qs.modules.launcher.services

Item {
    id: root

    required property DesktopEntry modelData
    required property ScreenState screenState

    property bool selectionOnly: false
    signal chosen(var entry)
    signal launched()
    function dock(): var { return ShellState.componentsFor(screenState.modelData)?.panels?.dock ?? null; }

    implicitHeight: Tokens.sizes.launcher.itemHeight

    anchors.left: parent?.left
    anchors.right: parent?.right

    StateLayer {
        id: appMouse
        property point pressPoint
        property bool dragged: false
        preventStealing: DockConf.enabled && !root.selectionOnly
        onPressed: event => { pressPoint = Qt.point(event.x, event.y); dragged = false; }
        onPositionChanged: event => {
            if (root.selectionOnly || !DockConf.enabled || !(pressedButtons & Qt.LeftButton)) return;
            if (!dragged && Math.hypot(event.x - pressPoint.x, event.y - pressPoint.y) > 8 * Tokens.scale)
                dragged = true;
            const target = root.dock();
            if (dragged && target?.visible)
                target.dragApplication(root.modelData, appMouse.mapToItem(target, event.x, event.y));
        }
        onReleased: if (dragged) root.dock()?.dropApplication(root.modelData)
        onCanceled: root.dock()?.cancelDrag()
        radius: Tokens.rounding.large
        acceptedButtons: DockConf.enabled && !root.selectionOnly ? Qt.LeftButton | Qt.RightButton : Qt.LeftButton
        onClicked: event => {
            if (dragged) return;
            if (event.button === Qt.RightButton) {
                pinMenu.expanded = true;
                return;
            }
            if (root.selectionOnly) { root.chosen(root.modelData); return; }
            Apps.launch(root.modelData);
            root.launched();
            root.screenState.launcher = false;
        }
    }

    Menu {
        id: pinMenu
        attachTo: root
        updateActiveOnSelection: false
        items: [MenuItem {
            text: Taskbar.pinned.includes(root.modelData?.id) ? Tr.tr("Unpin from dock") : Tr.tr("Pin to dock")
            icon: Taskbar.pinned.includes(root.modelData?.id) ? "keep_off" : "keep"
            onClicked: if (DockConf.enabled && root.modelData) Taskbar.togglePin(root.modelData.id)
        }]
    }
    Connections {
        target: DockConf
        function onEnabledChanged() { if (!DockConf.enabled) pinMenu.expanded = false; }
    }

    Item {
        anchors.fill: parent
        anchors.leftMargin: Tokens.padding.medium
        anchors.rightMargin: Tokens.padding.medium
        anchors.margins: Tokens.padding.small

        IconImage {
            id: icon

            asynchronous: true
            source: Quickshell.iconPath(root.modelData?.icon, "image-missing")
            implicitSize: parent.height * 0.8

            anchors.verticalCenter: parent.verticalCenter
        }

        Item {
            anchors.left: icon.right
            anchors.leftMargin: Tokens.spacing.medium
            anchors.verticalCenter: icon.verticalCenter

            implicitWidth: parent.width - icon.width - favouriteIcon.width
            implicitHeight: name.implicitHeight + comment.implicitHeight

            StyledText {
                id: name

                text: root.modelData?.name ?? ""
                font: Tokens.font.body.medium
            }

            StyledText {
                id: comment

                text: (root.modelData?.comment || root.modelData?.genericName || root.modelData?.name) ?? ""
                font: Tokens.font.body.small
                color: Colours.palette.m3outline

                elide: Text.ElideRight
                width: root.width - icon.width - favouriteIcon.width - Tokens.rounding.extraLargeIncreased

                anchors.top: name.bottom
            }
        }

        Loader {
            id: favouriteIcon

            asynchronous: true
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            active: root.modelData && Strings.testRegexList(GlobalConfig.launcher.favouriteApps, root.modelData.id)

            sourceComponent: MaterialIcon {
                text: "favorite"
                fill: 1
                color: Colours.palette.m3primary
            }
        }
    }
}
