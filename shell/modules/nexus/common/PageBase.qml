pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
import qs.modules.nexus

ColumnLayout {
    id: root

    required property string title
    required property NexusState nState
    readonly property var pageInfo: PageRegistry.pages.find(p => p.label === title) ?? PageRegistry.pages[nState.currentPageIdx] ?? ({})
    property string pageIcon: pageInfo.icon ?? "tune"
    property string pageDescription: isSubPage ? (pageInfo.label ?? "") : (pageInfo.description ?? "")
    property bool isSubPage: nState.subPageIdxStack.length > 0
    readonly property int cappedWidth: Math.min(Tokens.sizes.nexus.maxContentWidth, width)
    readonly property alias flickable: flickable

    default property Item contentChild
    property Item searchHighlight
    property int searchAttempts
    property real settledContentHeight: 0
    property real preferredContentY: -flickable.topMargin

    property bool pageDisposing: false
    Component.onDestruction: pageDisposing = true
    property var layoutAnimations: []
    property real animatedLayoutBase: 0

    function syncLayoutAnimationFrame(): void {
        let height = animatedLayoutBase;
        for (const entry of layoutAnimations) {
            // A parent card already includes the motion of nested cards.
            let nested = false;
            for (let parent = entry.item?.parent; parent; parent = parent.parent)
                if (layoutAnimations.some(other => other.item === parent)) {
                    nested = true;
                    break;
                }
            if (!nested && entry.item)
                height += entry.item.expansionExtent - entry.start;
        }
        settledContentHeight = Math.max(0, height);
        const maximum = Math.max(-flickable.topMargin, settledContentHeight - flickable.height + flickable.bottomMargin);
        if (!flickable.dragging && flickable.contentY > maximum)
            flickable.contentY = maximum;
    }
    function layoutAnimationChanged(item: Item, running: bool, destroying: bool): void {
        const wasRunning = layoutAnimations.length > 0;
        if (wasRunning && !destroying)
            syncLayoutAnimationFrame();
        animatedLayoutBase = wasRunning ? settledContentHeight : (contentChild?.implicitHeight ?? 0);
        const next = layoutAnimations.filter(entry => entry.item && entry.item !== item);
        if (running)
            next.push({item: item, start: item.expansionExtent});
        for (const entry of next)
            entry.start = entry.item.expansionExtent;
        layoutAnimations = next;
        if (next.length > 0)
            contentLayoutSettled.stop();
        else if (wasRunning)
            contentLayoutSettled.restart();
    }
    readonly property FrameAnimation layoutMotionFrames: FrameAnimation {
        running: root.layoutAnimations.length > 0
        onTriggered: root.syncLayoutAnimationFrame()
    }

    // Repeaters briefly remove their delegates when a refreshed model arrives.
    // Keep that intermediate layout from clamping the current scroll position.
    readonly property FrameAnimation contentLayoutSettled: FrameAnimation {
        property real sampledHeight: -1
        property int stableFrames: 0
        onTriggered: {
            const height = root.contentChild?.implicitHeight ?? 0;
            if (currentFrame === 1 || height !== sampledHeight) {
                sampledHeight = height;
                stableFrames = 0;
            } else {
                stableFrames++;
            }
            // Wait for layout polish as well as a quiet update interval.
            if (elapsedTime >= 0.064 && stableFrames >= 2) {
                root.settledContentHeight = height;
                const maximum = Math.max(-flickable.topMargin, height - flickable.height + flickable.bottomMargin);
                flickable.contentY = Math.max(-flickable.topMargin, Math.min(maximum, root.preferredContentY));
                stop();
            }
        }
    }

    onContentChildChanged: contentLayoutSettled.restart()

    Connections {
        target: root.contentChild
        function onImplicitHeightChanged(): void {
            if (root.layoutAnimations.length === 0)
                root.contentLayoutSettled.restart();
        }
    }

    function revealSearchTarget(): bool {
        if (!nState.searchTarget && !nState.searchTargetText)
            return true;
        if (contentLayoutSettled.running || layoutAnimations.length > 0)
            return false;
        function find(item) {
            if (root.nState.searchTarget ? item.objectName === root.nState.searchTarget : item.text === root.nState.searchTargetText || item.label === root.nState.searchTargetText || item.label?.text === root.nState.searchTargetText || item.title === root.nState.searchTargetText)
                return item;
            for (const child of item.children ?? []) {
                const result = find(child);
                if (result)
                    return result;
            }
            return null;
        }
        const item = find(contentChild);
        if (!item)
            return false;
        let expanded = false;
        for (let ancestor = item.parent; ancestor; ancestor = ancestor.parent)
            if (typeof ancestor.expandForSearch === "function")
                expanded = ancestor.expandForSearch() || expanded;
        if (expanded || item.height <= 0 || flickable.height <= 0)
            return false;
        const point = item.mapToItem(flickable.contentItem, 0, 0);
        flickable.cancelFlick();
        flickable.contentY = Math.max(-flickable.topMargin, Math.min(Math.max(-flickable.topMargin, flickable.contentHeight - flickable.height + flickable.bottomMargin), point.y - (flickable.height - item.height) / 2));
        searchHighlight = item;
        highlightExpiry.restart();
        return true;
    }

    Component.onCompleted: {
        contentLayoutSettled.restart();
        if (nState.searchTarget || nState.searchTargetText)
            searchRetry.start();
    }

    readonly property Timer searchRetry: Timer {
        interval: 50
        repeat: true
        onTriggered: {
            if (root.revealSearchTarget() || ++root.searchAttempts >= 20)
                stop();
        }
    }

    readonly property Timer highlightExpiry: Timer {
        interval: 2500
        onTriggered: root.searchHighlight = null
    }

    spacing: Tokens.spacing.extraLargeIncreased

    StyledRect {
        Layout.fillWidth: true
        implicitHeight: header.implicitHeight + Tokens.padding.large * 2
        radius: Tokens.rounding.extraLarge
        color: Colours.tPalette.m3surfaceContainerLow
        RowLayout {
            id: header
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Tokens.padding.large
            spacing: Tokens.spacing.medium
            IconButton {
                visible: root.isSubPage || root.nState.canGoBack
                icon: "arrow_back"
                type: IconButton.Tonal
                isRound: true
                Accessible.name: Tr.tr("Back")
                onClicked: root.nState.goBack()
            }
            StyledRect {
                implicitWidth: 52 * Tokens.scale
                implicitHeight: implicitWidth
                radius: Tokens.rounding.extraLarge
                color: Colours.palette.m3primaryContainer
                MaterialIcon {
                    anchors.centerIn: parent
                    text: root.pageIcon
                    color: Colours.palette.m3onPrimaryContainer
                    fontStyle: Tokens.font.icon.large
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 4 * Tokens.scale
                StyledText {
                    Layout.fillWidth: true
                    text: root.title
                    font: Tokens.font.headline.small
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    Accessible.role: Accessible.Heading
                }
                StyledText {
                    Layout.fillWidth: true
                    visible: !!root.pageDescription
                    text: root.pageDescription
                    font: Tokens.font.body.small
                    color: Colours.palette.m3onSurfaceVariant
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                }
            }
        }
    }

    VerticalFadeFlickable {
        id: flickable
        fadeAmount:Math.min(0.1,24*Tokens.scale/Math.max(1,height))

        Layout.fillWidth: true
        Layout.fillHeight: true

        Layout.topMargin: -topMargin
        topMargin: Tokens.padding.large
        bottomMargin: Tokens.padding.extraLarge

        onContentYChanged: {
            if (!root.contentLayoutSettled.running || dragging)
                root.preferredContentY = contentY;
        }
        contentHeight: root.settledContentHeight
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
