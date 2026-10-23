pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root

    title: Tr.tr("Add layout")
    isSubPage: true

    property string query

    readonly property var available: KeyboardConf.layouts.filter(layout => !KeyboardConf.layoutCodes.includes(layout.code))
    readonly property var filtered: root.available.filter(layout => {
        const q = root.query.trim().toLowerCase();
        return q.length === 0 || layout.name.toLowerCase().includes(q) || layout.code.toLowerCase().includes(q);
    })

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall

        SearchBar {
            Layout.fillWidth: true
            placeholderText: Tr.tr("Search layouts")
            onTextChanged: root.query = text
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.large

            Repeater {
                model: root.filtered

                RowButton {
                    required property var modelData
                    required property int index

                    first: index === 0
                    last: index === root.filtered.length - 1
                    icon: "keyboard"
                    text: modelData.name
                    subtext: modelData.code
                    onClicked: {
                        KeyboardConf.addLayout(modelData.code);
                        root.nState.closeSubPage();
                    }
                }
            }
        }

        StyledText {
            Layout.fillWidth: true
            visible: root.filtered.length === 0
            text: root.available.length === 0 ? Tr.tr("All layouts are already added") : Tr.tr("No matching layouts")
            color: Colours.palette.m3onSurfaceVariant
        }
    }
}
