import Hyprstack.Config
import Hyprstack.I18n
import QtQuick
import QtQuick.Layouts
import qs.components
import qs.services

StyledRect {
    id: root

    property string error: ""

    property string displayedError: error
    onErrorChanged: if (error.length) displayedError = error
    property real reveal: error.length > 0 ? 1 : 0
    Behavior on reveal { Anim { type: Anim.FastEffects } }
    Layout.fillWidth: true
    visible: reveal > 0
    clip: true
    implicitHeight: (row.implicitHeight + Tokens.padding.medium * 2) * reveal
    radius: Tokens.rounding.large
    color: Colours.palette.m3errorContainer

    RowLayout {
        id: row

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Tokens.padding.medium
        opacity: root.reveal
        spacing: Tokens.spacing.medium

        MaterialIcon {
            text: "error"
            color: Colours.palette.m3onErrorContainer
            fontStyle: Tokens.font.icon.medium
        }

        StyledText {
            Layout.fillWidth: true
            text: Tr.tr(root.displayedError)
            textFormat: Text.PlainText
            color: Colours.palette.m3onErrorContainer
            wrapMode: Text.Wrap
            font: Tokens.font.body.medium
            Accessible.role: Accessible.AlertMessage
        }
    }
}
