import Hyprstack.Config
import Hyprstack.I18n
import QtQuick
import QtQuick.Layouts
import qs.components
import qs.services

StyledRect {
    id: root

    property string error: ""

    Layout.fillWidth: true
    visible: error.length > 0
    implicitHeight: row.implicitHeight + Tokens.padding.medium * 2
    radius: Tokens.rounding.large
    color: Colours.palette.m3errorContainer

    RowLayout {
        id: row

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Tokens.padding.medium
        spacing: Tokens.spacing.medium

        MaterialIcon {
            text: "error"
            color: Colours.palette.m3onErrorContainer
            fontStyle: Tokens.font.icon.medium
        }

        StyledText {
            Layout.fillWidth: true
            text: Tr.tr(root.error)
            textFormat: Text.PlainText
            color: Colours.palette.m3onErrorContainer
            wrapMode: Text.Wrap
            font: Tokens.font.body.medium
            Accessible.role: Accessible.AlertMessage
        }
    }
}
