pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
import qs.modules.nexus

ColumnLayout {
    id: root

    required property string title
    required property NexusState nState
    property bool isSubPage
    readonly property int cappedWidth: Math.min(Tokens.sizes.nexus.maxContentWidth, width)
    readonly property alias flickable: flickable

    default property Item contentChild
    property Item searchHighlight
    property int searchAttempts

    function revealSearchTarget(): bool {
        if (!nState.searchTarget && !nState.searchTargetText) return true;
        function find(item) {
            if (root.nState.searchTarget ? item.objectName === root.nState.searchTarget
                : item.text === root.nState.searchTargetText || item.label === root.nState.searchTargetText
                    || item.label?.text === root.nState.searchTargetText)
                return item;
            for (const child of item.children ?? []) {
                const result = find(child);
                if (result) return result;
            }
            return null;
        }
        const item = find(contentChild);
        if (!item || item.height <= 0 || flickable.height <= 0) return false;
        const point = item.mapToItem(flickable.contentItem, 0, 0);
        flickable.cancelFlick();
        flickable.contentY = Math.max(-flickable.topMargin,
            Math.min(Math.max(-flickable.topMargin, flickable.contentHeight - flickable.height + flickable.bottomMargin),
                point.y - (flickable.height - item.height) / 2));
        searchHighlight = item;
        highlightExpiry.restart();
        return true;
    }

    Component.onCompleted: {
        if (nState.searchTarget || nState.searchTargetText) searchRetry.start();
    }

    readonly property Timer searchRetry: Timer {
        interval: 50
        repeat: true
        onTriggered: {
            if (root.revealSearchTarget() || ++root.searchAttempts >= 20) stop();
        }
    }

    readonly property Timer highlightExpiry: Timer {
        interval: 2500
        onTriggered: root.searchHighlight = null
    }

    spacing: Tokens.spacing.extraLargeIncreased

    MouseArea { // Prevent clicks from reaching flickable
        z: 1
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        implicitWidth: header.implicitWidth
        implicitHeight: header.implicitHeight - Layout.bottomMargin
        Layout.bottomMargin: -flickable.topMargin // Extra height to block clicks on flickable top margin
        onClicked: focus = true

        RowLayout {
            id: header

            anchors.left: parent.left
            anchors.right: parent.right
            spacing: Tokens.spacing.largeIncreased

            Loader {
                visible: active
                active: root.isSubPage
                asynchronous: true
                sourceComponent: IconButton {
                    icon: "arrow_back"
                    font: Tokens.font.icon.medium
                    type: IconButton.Tonal
                    isRound: true
                    inactiveColour: Colours.tPalette.m3surfaceContainerHigh
                    inactiveOnColour: Colours.palette.m3onSurfaceVariant
                    onClicked: root.nState.closeSubPage()
                }
            }

            StyledText {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: root.title
                font: Tokens.font.title.large
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }
        }
    }

    VerticalFadeFlickable {
        id: flickable

        Layout.fillWidth: true
        Layout.fillHeight: true

        Layout.topMargin: -topMargin
        topMargin: Tokens.padding.large
        bottomMargin: Tokens.padding.extraLarge

        contentHeight: root.contentChild?.implicitHeight ?? 0
        contentItem.children: [root.contentChild, searchOutline]

        Rectangle {
            id: searchOutline
            visible: root.searchHighlight !== null
            x: root.searchHighlight?.mapToItem(flickable.contentItem, 0, 0).x ?? 0
            y: root.searchHighlight?.mapToItem(flickable.contentItem, 0, 0).y ?? 0
            width: root.searchHighlight?.width ?? 0
            height: root.searchHighlight?.height ?? 0
            radius: Tokens.rounding.medium
            color: "transparent"
            border.width: 2 * Tokens.scale
            border.color: Colours.palette.m3primary
            z: 10
        }

        TapHandler {
            onTapped: flickable.focus = true
        }
    }
}
