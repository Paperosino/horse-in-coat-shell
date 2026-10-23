import "navpane"
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus
import "../../utils/scripts/settings-search.js" as Search

ColumnLayout {
    id: root

    required property NexusState nState
    readonly property var searchResults: {
        Tr.language;
        return Search.find(nState.searchQuery, (text, context) => context ? Tr.trCtx(text, context) : Tr.tr(text));
    }

    function choose(result: var): void {
        if (!result)
            return;
        searchField.text = "";
        searchField.focus = false;
        nState.currentPageIdx = result.page;
        nState.subPageIdxStack = result.subpages;
        nState.searchTarget = result.target;
        nState.searchTargetText = result.match ? (result.context ? Tr.trCtx(result.match, result.context) : Tr.tr(result.match)) : "";
        nState.searchRequested();
    }

    spacing: Tokens.spacing.large

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Tokens.padding.small
        spacing: Tokens.spacing.small
        MaterialIcon {
            text: "tune"
            color: Colours.palette.m3primary
            fontStyle: Tokens.font.icon.medium
        }
        StyledText {
            text: Tr.tr("Settings")
            font: Tokens.font.title.medium
            Layout.fillWidth: true
        }
    }

    SearchBar {
        id: searchField
        objectName: "settingsSearchField"

        Layout.fillWidth: true

        placeholderText: Tr.tr("Search settings")
        font: Tokens.font.body.medium

        bg.color: Colours.tPalette.m3surfaceContainerLowest
        bg.border.color: Colours.palette.m3outlineVariant
        searchIcon.fontStyle: Tokens.font.icon.medium
        searchIcon.anchors.leftMargin: Tokens.padding.largeIncreased
        clearIcon.font: Tokens.font.icon.medium
        clearIcon.padding: Tokens.padding.extraSmall

        Behavior on bg.border.color {
            CAnim {}
        }

        onTextChanged: {
            root.nState.searchQuery = text;
            root.nState.searchResultIdx = 0;
        }
        onAccepted: root.choose(root.searchResults[root.nState.searchResultIdx])
        Keys.onDownPressed: event => {
            root.nState.searchResultIdx = Math.max(0, Math.min(root.searchResults.length - 1, root.nState.searchResultIdx + 1));
            event.accepted = true;
        }
        Keys.onUpPressed: event => {
            root.nState.searchResultIdx = Math.max(0, root.nState.searchResultIdx - 1);
            event.accepted = true;
        }
        Keys.onEscapePressed: event => {
            clear();
            event.accepted = true;
        }
    }

    NavLocations {
        visible: !root.nState.searchOpen
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.topMargin: -topMargin
        Layout.bottomMargin: -bottomMargin
        nState: root.nState
    }

    SearchResults {
        objectName: "settingsSearchResults"
        visible: root.nState.searchOpen
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.topMargin: -topMargin
        Layout.bottomMargin: -bottomMargin
        nState: root.nState
        results: root.searchResults
        onChosen: result => root.choose(result)
    }
}
