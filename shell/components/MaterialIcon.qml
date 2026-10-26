import QtQuick
import Hyprstack.Config
import qs.services

StyledText {
    // Symbols are artwork, independent of text grid fitting preferences.
    renderType: Text.QtRendering
    antialiasing: true
    renderTypeQuality: Text.HighRenderTypeQuality
    property real fill
    property int grade: Colours.light ? 0 : -25
    property font fontStyle: Tokens.font.icon.small

    font: Tokens.font.icon.size(fontStyle.pointSize).weight(fontStyle.weight).vaxes(fontStyle.variableAxes).fill(fill.toFixed(1)).grade(grade).build()
}
