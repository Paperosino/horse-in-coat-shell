import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
StyledText {
    property string error: ""
    Layout.fillWidth: true
    visible: error.length > 0
    text: Tr.tr(error)
    color: Colours.palette.m3error
    wrapMode: Text.Wrap
    textFormat: Text.PlainText
    font: Tokens.font.body.small
}
