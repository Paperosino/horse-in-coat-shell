pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.services

ConnectedRect {
    id: root
    property string title
    property string description
    property string icon: "tune"
    property string badge
    property bool collapsible: false
    property bool expanded: true
    property var expansionHandler: null
    function changeExpansion(value: bool): void {
        if (expansionHandler) expansionHandler(value);
        else expanded=value;
    }
    readonly property bool settingsCard: true
    readonly property real expansionExtent: viewport.animatedHeight
    property var motionPage: null
    property bool motionReady: false
    Component.onCompleted: Qt.callLater(() => { if (root) root.motionReady = true; })
    function notifyLayoutMotion(running: bool): void {
        if (running) {
            for (let item = root.parent; item; item = item.parent) {
                if (typeof item.layoutAnimationChanged === "function") {
                    motionPage = item;
                    break;
                }
            }
        }
        if (motionPage && !motionPage.pageDisposing)
            motionPage.layoutAnimationChanged(root, running, false);
        if (!running)
            motionPage = null;
    }
    Component.onDestruction: {
        if (motionPage && !motionPage.pageDisposing)
            motionPage.layoutAnimationChanged(root, false, true);
    }
    default property alias contents: body.data
    function expandForSearch(): bool {
        if (!collapsible || expanded)
            return false;
        changeExpansion(true);
        return true;
    }
    Layout.fillWidth: true
    first: true
    last: true
    implicitHeight: frame.implicitHeight + Tokens.padding.large * 2
    color: Colours.tPalette.m3surfaceContainerLow
    border.width: 1 * Tokens.scale
    border.color: Qt.alpha(Colours.palette.m3outlineVariant, GlobalConfig.appearance.highContrast ? 1 : 0.35)
    readonly property ColumnLayout frame: ColumnLayout {
        parent: root
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Tokens.padding.large
        spacing: 0
        Item {
            Layout.fillWidth: true
            implicitHeight: heading.implicitHeight
            StateLayer {
                enabled: root.collapsible
                keyboardFocusable: true
                radius: Tokens.rounding.large
                Accessible.name: root.title
                Accessible.role: Accessible.Button
                Accessible.expanded: root.expanded
                onClicked: root.changeExpansion(!root.expanded)
            }
            RowLayout {
                id: heading
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: Tokens.spacing.medium
                StyledRect {
                    implicitWidth: 40 * Tokens.scale
                    implicitHeight: implicitWidth
                    radius: Tokens.rounding.large
                    color: Colours.palette.m3secondaryContainer
                    MaterialIcon {
                        anchors.centerIn: parent
                        text: root.icon
                        color: Colours.palette.m3onSecondaryContainer
                        fontStyle: Tokens.font.icon.medium
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 4 * Tokens.scale
                    StyledText {
                        Layout.fillWidth: true
                        text: root.title
                        textFormat: Text.PlainText
                        font: Tokens.font.title.small
                        wrapMode: Text.WordWrap
                    }
                    StyledText {
                        Layout.fillWidth: true
                        visible: !!root.description
                        text: root.description
                        textFormat: Text.PlainText
                        font: Tokens.font.body.small
                        color: Colours.palette.m3onSurfaceVariant
                        wrapMode: Text.WordWrap
                    }
                }
                StyledRect {
                    visible: !!root.badge
                    implicitWidth: badgeText.implicitWidth + Tokens.padding.medium * 2
                    implicitHeight: badgeText.implicitHeight + Tokens.padding.small * 2
                    radius: Tokens.rounding.full
                    color: Colours.palette.m3secondaryContainer
                    StyledText {
                        id: badgeText
                        anchors.centerIn: parent
                        text: root.badge
                        font: Tokens.font.label.small
                        color: Colours.palette.m3onSecondaryContainer
                    }
                }
                MaterialIcon {
                    visible: root.collapsible
                    text: "expand_more"
                    color: Colours.palette.m3onSurfaceVariant
                    rotation: root.expanded ? 180 : 0
                    Behavior on rotation {
                        Anim {
                            type: Anim.FastSpatial
                        }
                    }
                }
            }
        }
        Item {
            id: viewport
            Layout.fillWidth: true
            // Animate a pixel extent so content updates retarget from the
            // current height instead of multiplying by a changing natural size.
            readonly property real fullHeight: body.implicitHeight + Tokens.spacing.medium
            property real animatedHeight: !root.collapsible || root.expanded ? fullHeight : 0
            readonly property real reveal: root.collapsible ? Math.max(0, Math.min(1, animatedHeight / Math.max(1, fullHeight))) : 1
            implicitHeight: animatedHeight
            visible: !root.collapsible || animatedHeight > 0
            enabled: !root.collapsible || root.expanded
            clip: root.collapsible
            Behavior on animatedHeight {
                enabled: root.collapsible && root.motionReady
                Anim {
                    id: heightMotion
                    type: Anim.Emphasized
                    duration: GlobalConfig.appearance.reducedMotion ? 0 : Tokens.anim.durations.expressiveDefaultSpatial
                    onRunningChanged: root.notifyLayoutMotion(running)
                }
            }
            ColumnLayout {
                id: body
                anchors.left: parent.left
                anchors.right: parent.right
                y: Tokens.spacing.medium - (1 - viewport.reveal) * 8 * Tokens.scale
                spacing: Tokens.spacing.extraSmall
                opacity: !root.collapsible || root.expanded ? 1 : 0
                Behavior on opacity {
                    enabled: root.collapsible
                    Anim { type: Anim.DefaultEffects }
                }
            }
        }
    }
}
