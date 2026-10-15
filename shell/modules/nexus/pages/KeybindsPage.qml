pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common
import "../../../services/Keybinds.js" as Bindings

PageBase {
    id: root

    title: Tr.tr("Keyboard shortcuts")
    objectName: "keyboardShortcutsPage"
    property string query
    function translated(text: string): string { return Bindings.translateDescription(text, value => Tr.tr(value)); }
    readonly property var filtered: Keybinds.bindings.filter(b => Bindings.matches(b, query, translated))

    Component.onCompleted: Keybinds.reload()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall

        StyledText {
            Layout.fillWidth: true
            text: Tr.tr("Current Hyprland shortcuts, including your custom bindings. Super is the Windows/Meta key.")
            wrapMode: Text.WordWrap
            color: Colours.palette.m3onSurfaceVariant
        }

        RowLayout {
            Layout.fillWidth: true
            StyledTextField {
                objectName: "keyboardShortcutsSearch"
                Layout.fillWidth: true
                placeholderText: Tr.tr("Search keyboard shortcuts")
                onTextChanged: root.query = text
            }
            IconButton {
                icon: "refresh"
                disabled: Keybinds.loading
                onClicked: Keybinds.reload()
                Accessible.name: Tr.tr("Refresh")
            }
        }

        Repeater {
            model: root.filtered
            ColumnLayout {
                id: entry
                required property var modelData
                required property int index
                Layout.fillWidth: true
                spacing: 0

                SectionHeader {
                    visible: entry.index === 0 || root.filtered[entry.index - 1].category !== entry.modelData.category
                    first: entry.index === 0
                    text: Tr.tr(entry.modelData.category)
                }
                ConnectedRect {
                    objectName: "keyboardShortcut_" + entry.index
                    Layout.fillWidth: true
                    first: entry.index === 0 || root.filtered[entry.index - 1].category !== entry.modelData.category
                    last: entry.index === root.filtered.length - 1 || root.filtered[entry.index + 1].category !== entry.modelData.category
                    implicitHeight: content.implicitHeight + Tokens.padding.medium * 2

                    ColumnLayout {
                        id: content
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Tokens.padding.medium
                        spacing: Tokens.spacing.extraSmall

                        StyledText {
                            Layout.fillWidth: true
                            text: root.translated(entry.modelData.action)
                            textFormat: Text.PlainText
                            wrapMode: Text.WordWrap
                        }
                        StyledText {
                            Layout.fillWidth: true
                            text: entry.modelData.shortcuts.map(value => Bindings.translateShortcut(value, text => Tr.tr(text))).join("   /   ")
                                + (entry.modelData.submap ? " · " + (entry.modelData.submap === "hyprstack-switcher"
                                    ? Tr.tr("Window switcher") : entry.modelData.submap) : "")
                            textFormat: Text.PlainText
                            color: Colours.palette.m3primary
                            font: Tokens.font.body.small
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        }

        StyledText {
            Layout.fillWidth: true
            visible: !!Keybinds.error || (!Keybinds.loading && !root.filtered.length)
            text: Keybinds.error ? Tr.tr(Keybinds.error) : Tr.tr("No matching shortcuts")
            color: Keybinds.error ? Colours.palette.m3error : Colours.palette.m3onSurfaceVariant
        }
    }
}
