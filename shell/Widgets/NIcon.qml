import QtQuick
import Hyprstack.Config
import qs.components

MaterialIcon {
    property string icon: "extension"
    // Historical API: pointSize is a pixel size, like the old font.pixelSize.
    property real pointSize: 20

    text: icon
    // Keep MaterialIcon's complete font binding (family, axes and rendering).
    fontStyle: Tokens.font.icon.builders.small.size(pointSize * 0.75).build()
}
