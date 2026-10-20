pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
import qs.utils

Item {
    id: root

    required property ScreenState screenState

    property var editingEntry: null
    property var previewingEntry: null

    implicitWidth: 560 * Tokens.scale
    implicitHeight: 480 * Tokens.scale

    function startEditing(entry: var): void {
        if (!entry || !entry.raw) return;
        root.editingEntry = entry;
        editTextEdit.text = entry.text || "";
        editTextEdit.forceActiveFocus();
        editTextEdit.cursorPosition = editTextEdit.text.length;

        Clipboard.decodeEntry(entry.raw, (fullText) => {
            if (root.editingEntry && root.editingEntry.id === entry.id) {
                if (fullText && fullText.length > 0) {
                    editTextEdit.text = fullText;
                    editTextEdit.cursorPosition = fullText.length;
                }
            }
        });
    }

    function saveEditing(): void {
        if (!root.editingEntry) return;
        const newText = editTextEdit.text;
        Clipboard.saveEditedText(root.editingEntry.raw, newText, () => {
            root.editingEntry = null;
        });
    }

    function cancelEditing(): void {
        root.editingEntry = null;
        searchField.forceActiveFocus();
    }

    Component.onCompleted: {
        Clipboard.reload();
        searchField.focus = true;
    }

    Connections {
        target: screenState
        function onClipboardChanged(): void {
            if (screenState.clipboard) {
                root.editingEntry = null;
                root.previewingEntry = null;
                Clipboard.query = "";
                Clipboard.reload();
                searchField.text = "";
                searchField.focus = true;
                entryList.currentIndex = 0;
            }
        }
    }

    // 1. LIST VIEW (Default)
    ColumnLayout {
        id: listLayout
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium
        visible: root.editingEntry === null && root.previewingEntry === null

        // Top bar
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            MaterialIcon {
                text: "history"
                fontStyle: Tokens.font.icon.medium
                color: Colours.palette.m3primary
            }

            StyledText {
                text: Tr.tr("Clipboard history")
                font: Tokens.font.title.small
                color: Colours.palette.m3onSurface
            }

            StyledRect {
                implicitWidth: badgeText.implicitWidth + Tokens.padding.small * 2
                implicitHeight: badgeText.implicitHeight + Tokens.padding.extraSmall
                radius: Tokens.rounding.full
                color: Colours.palette.m3surfaceContainerHigh

                StyledText {
                    id: badgeText
                    anchors.centerIn: parent
                    text: String(Clipboard.filteredEntries.length)
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                }
            }

            Item { Layout.fillWidth: true }

            IconButton {
                icon: "delete_sweep"
                disabled: Clipboard.entries.length === 0
                onClicked: Clipboard.clearAll()
            }

            IconButton {
                icon: "close"
                onClicked: root.screenState.clipboard = false
            }
        }

        // Search field
        SearchBar {
            id: searchField
            Layout.fillWidth: true
            placeholderText: Tr.tr("Search clipboard...")

            Keys.onEscapePressed: root.screenState.clipboard = false
            Keys.onDownPressed: entryList.incrementCurrentIndex()
            Keys.onUpPressed: entryList.decrementCurrentIndex()
            Keys.onReturnPressed: {
                if (entryList.currentItem) {
                    const itemData = entryList.model[entryList.currentIndex];
                    if (itemData) Clipboard.copy(itemData);
                }
            }
            onTextChanged: {
                Clipboard.query = text;
                entryList.currentIndex = 0;
            }
        }

        // Items list or empty state
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: entryList
                anchors.fill: parent
                clip: true
                spacing: Tokens.spacing.extraSmall
                model: Clipboard.filteredEntries
                boundsBehavior: Flickable.StopAtBounds

                ScrollBar.vertical: ScrollBar {
                    active: entryList.moving || entryList.flicking
                }

                delegate: StyledRect {
                    id: delegateRect
                    required property var modelData
                    required property int index

                    readonly property bool isSelected: entryList.currentIndex === index
                    readonly property bool isHovered: hoverArea.containsMouse

                    width: entryList.width - (entryList.ScrollBar.vertical.visible ? entryList.ScrollBar.vertical.width : 0)
                    implicitHeight: Math.max(rowLayout.implicitHeight + Tokens.padding.small * 2, delegateRect.modelData.isBinary ? 72 * Tokens.scale : 48 * Tokens.scale)
                    radius: Tokens.rounding.medium
                    color: isSelected
                        ? Colours.palette.m3secondaryContainer
                        : isHovered
                            ? Colours.palette.m3surfaceContainerHigh
                            : Colours.palette.m3surfaceContainer

                    Behavior on color { CAnim {} }

                    MouseArea {
                        id: hoverArea
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            entryList.currentIndex = delegateRect.index;
                            Clipboard.copy(delegateRect.modelData);
                        }
                    }

                    RowLayout {
                        id: rowLayout
                        anchors.fill: parent
                        anchors.margins: Tokens.padding.medium
                        spacing: Tokens.spacing.medium

                        // Thumbnail or Icon
                        Item {
                            implicitWidth: delegateRect.modelData.isBinary ? 56 * Tokens.scale : 28 * Tokens.scale
                            implicitHeight: delegateRect.modelData.isBinary ? 56 * Tokens.scale : 28 * Tokens.scale
                            Layout.alignment: Qt.AlignVCenter

                            StyledClippingRect {
                                anchors.fill: parent
                                visible: delegateRect.modelData.isBinary
                                radius: Tokens.rounding.small
                                color: Colours.palette.m3surfaceContainerLowest

                                Image {
                                    anchors.fill: parent
                                    source: delegateRect.modelData.imagePath ? Paths.fileUrl(delegateRect.modelData.imagePath) : ""
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: false
                                }

                                MaterialIcon {
                                    anchors.centerIn: parent
                                    visible: !delegateRect.modelData.imagePath
                                    text: "image"
                                    fontStyle: Tokens.font.icon.small
                                    color: Colours.palette.m3onSurfaceVariant
                                }
                            }

                            MaterialIcon {
                                anchors.centerIn: parent
                                visible: !delegateRect.modelData.isBinary
                                text: "content_paste"
                                fontStyle: Tokens.font.icon.small
                                color: delegateRect.isSelected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3primary
                            }
                        }

                        // Content text / description
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.alignment: Qt.AlignVCenter
                            spacing: 2

                            StyledText {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                text: delegateRect.modelData.isBinary ? Tr.tr("Image") : delegateRect.modelData.text
                                font: Tokens.font.body.medium
                                color: delegateRect.isSelected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                                elide: Text.ElideRight
                                maximumLineCount: delegateRect.modelData.isBinary ? 1 : 2
                                wrapMode: Text.WrapAnywhere
                            }

                            StyledText {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                visible: delegateRect.modelData.isBinary
                                text: delegateRect.modelData.text
                                font: Tokens.font.label.small
                                color: delegateRect.isSelected ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurfaceVariant
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }

                        // Actions for this item
                        RowLayout {
                            Layout.alignment: Qt.AlignVCenter
                            spacing: Tokens.spacing.extraSmall

                            // Image preview button
                            IconButton {
                                visible: delegateRect.modelData.isBinary && delegateRect.modelData.imagePath.length > 0
                                icon: "visibility"
                                onClicked: root.previewingEntry = delegateRect.modelData
                            }

                            // Text edit button
                            IconButton {
                                visible: !delegateRect.modelData.isBinary
                                icon: "edit"
                                onClicked: root.startEditing(delegateRect.modelData)
                            }

                            // Copy button
                            IconButton {
                                icon: "content_copy"
                                onClicked: Clipboard.copy(delegateRect.modelData)
                            }

                            // Delete button
                            IconButton {
                                icon: "delete"
                                onClicked: Clipboard.deleteEntry(delegateRect.modelData)
                            }
                        }
                    }
                }
            }

            // Empty state
            ColumnLayout {
                anchors.centerIn: parent
                visible: Clipboard.filteredEntries.length === 0
                spacing: Tokens.spacing.small

                MaterialIcon {
                    Layout.alignment: Qt.AlignHCenter
                    text: "content_paste_off"
                    fontStyle: Tokens.font.icon.large
                    color: Colours.palette.m3outline
                }

                StyledText {
                    Layout.alignment: Qt.AlignHCenter
                    text: Clipboard.query ? Tr.tr("No matching clipboard entries") : Tr.tr("Clipboard history is empty")
                    font: Tokens.font.body.medium
                    color: Colours.palette.m3outline
                }
            }
        }
    }

    // 2. TEXT EDITOR VIEW
    ColumnLayout {
        id: editLayout
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium
        visible: root.editingEntry !== null

        // Top bar
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            IconButton {
                icon: "arrow_back"
                onClicked: root.cancelEditing()
            }

            StyledText {
                text: Tr.tr("Edit clipboard text")
                font: Tokens.font.title.small
                color: Colours.palette.m3onSurface
            }

            Item { Layout.fillWidth: true }

            StyledRect {
                implicitWidth: charCountText.implicitWidth + Tokens.padding.small * 2
                implicitHeight: charCountText.implicitHeight + Tokens.padding.extraSmall
                radius: Tokens.rounding.full
                color: Colours.palette.m3surfaceContainerHigh

                StyledText {
                    id: charCountText
                    anchors.centerIn: parent
                    text: editTextEdit.text.length + " " + Tr.tr("chars")
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                }
            }
        }

        // Editor Area
        StyledRect {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Tokens.rounding.medium
            color: Colours.palette.m3surfaceContainerHigh
            clip: true

            Flickable {
                id: editFlickable
                anchors.fill: parent
                contentWidth: width
                contentHeight: Math.max(height, editTextEdit.contentHeight + Tokens.padding.large * 2)
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                ScrollBar.vertical: ScrollBar {
                    active: editFlickable.moving || editFlickable.flicking
                }

                TextEdit {
                    id: editTextEdit
                    width: editFlickable.width - Tokens.padding.large * 2
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: Tokens.padding.large
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    color: Colours.palette.m3onSurface
                    selectionColor: Colours.palette.m3primary
                    selectedTextColor: Colours.palette.m3onPrimary
                    font: Tokens.font.body.medium

                    Keys.onEscapePressed: root.cancelEditing()
                }
            }
        }

        // Action buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            Item { Layout.fillWidth: true }

            TextButton {
                text: Tr.tr("Cancel")
                onClicked: root.cancelEditing()
            }

            IconTextButton {
                icon: "save"
                text: Tr.tr("Save & Copy")
                onClicked: root.saveEditing()
            }
        }
    }

    // 3. IMAGE PREVIEW VIEW
    ColumnLayout {
        id: imagePreviewLayout
        anchors.fill: parent
        anchors.margins: Tokens.padding.large
        spacing: Tokens.spacing.medium
        visible: root.previewingEntry !== null

        // Top bar
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            IconButton {
                icon: "arrow_back"
                onClicked: root.previewingEntry = null
            }

            StyledText {
                text: Tr.tr("Image preview")
                font: Tokens.font.title.small
                color: Colours.palette.m3onSurface
            }

            Item { Layout.fillWidth: true }

            StyledRect {
                implicitWidth: imgMetaText.implicitWidth + Tokens.padding.small * 2
                implicitHeight: imgMetaText.implicitHeight + Tokens.padding.extraSmall
                radius: Tokens.rounding.full
                color: Colours.palette.m3surfaceContainerHigh

                StyledText {
                    id: imgMetaText
                    anchors.centerIn: parent
                    text: root.previewingEntry ? root.previewingEntry.text.replace("[[ binary data ", "").replace(" ]]", "") : ""
                    font: Tokens.font.label.small
                    color: Colours.palette.m3onSurfaceVariant
                }
            }
        }

        // Large Image Container
        StyledRect {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Tokens.rounding.medium
            color: Colours.palette.m3surfaceContainerLowest
            clip: true

            Image {
                id: fullPreviewImage
                anchors.fill: parent
                anchors.margins: Tokens.padding.medium
                source: root.previewingEntry && root.previewingEntry.imagePath ? Paths.fileUrl(root.previewingEntry.imagePath) : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: false
            }

            MaterialIcon {
                anchors.centerIn: parent
                visible: fullPreviewImage.status === Image.Error
                text: "broken_image"
                fontStyle: Tokens.font.icon.large
                color: Colours.palette.m3onSurfaceVariant
            }
        }

        // Action buttons
        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            IconButton {
                icon: "delete"
                onClicked: {
                    if (root.previewingEntry) {
                        Clipboard.deleteEntry(root.previewingEntry);
                        root.previewingEntry = null;
                    }
                }
            }

            Item { Layout.fillWidth: true }

            TextButton {
                text: Tr.tr("Back")
                onClicked: root.previewingEntry = null
            }

            IconTextButton {
                icon: "content_copy"
                text: Tr.tr("Copy to clipboard")
                onClicked: {
                    if (root.previewingEntry) {
                        Clipboard.copy(root.previewingEntry);
                        root.previewingEntry = null;
                    }
                }
            }
        }
    }
}
