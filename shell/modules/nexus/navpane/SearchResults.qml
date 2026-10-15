pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.modules.nexus
import qs.modules.nexus.common
import qs.services

VerticalFadeFlickable {
    id: root
    required property NexusState nState
    required property var results
    signal chosen(result: var)

    topMargin: Tokens.padding.large
    bottomMargin: Tokens.padding.large
    contentHeight: content.implicitHeight

    function revealSelection(): void {
        const item = list.itemAt(nState.searchResultIdx);
        if (item)
            contentY = Math.max(-topMargin, Math.min(Math.max(-topMargin, contentHeight - height + bottomMargin),
                item.y - (height - item.height) / 2));
    }

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: Tokens.spacing.extraSmall

        StyledText {
            Layout.fillWidth: true
            Layout.topMargin: Tokens.padding.large
            visible: root.results.length === 0
            text: Tr.tr("No settings found")
            wrapMode: Text.WordWrap
        }

        Repeater {
            id: list
            model: root.results
            NavRow {
                required property var modelData
                required property int index
                objectName: "settingsSearchResult_" + index
                first: index === 0
                last: index === root.results.length - 1
                icon: PageRegistry.pages[modelData.page].icon
                text: modelData.label
                subtext: modelData.description
                color: index === root.nState.searchResultIdx ? Colours.palette.m3secondaryContainer : Colours.tPalette.m3surfaceContainerHigh
                onClicked: root.chosen(modelData)
            }
        }
    }

    Connections {
        target: root.nState
        function onSearchResultIdxChanged(): void { root.revealSelection(); }
    }
}
