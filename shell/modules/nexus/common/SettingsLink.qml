pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.services
StyledRect {
    id: root
    required property string title
    property string description
    property string icon: "settings"
    property bool compact: false
    signal clicked
    Layout.fillWidth: true
    implicitHeight: Math.max((compact ? 64 : 96) * Tokens.scale, content.implicitHeight + (compact ? Tokens.padding.medium : Tokens.padding.large) * 2)
    radius: Tokens.rounding.large
    color: layer.containsMouse ? Colours.palette.m3surfaceContainerHigh : Colours.tPalette.m3surfaceContainerLow
    border.width: compact ? 0 : Tokens.scale
    border.color: Qt.alpha(Colours.palette.m3outlineVariant, GlobalConfig.appearance.highContrast ? 1 : 0.3)
    scale: layer.pressed ? 0.985 : 1
    Behavior on color { CAnim {} }
    Behavior on scale { Anim { type: Anim.FastSpatial } }
    StateLayer {
        id: layer
        radius: root.radius
        keyboardFocusable: true
        Accessible.name: root.title
        Accessible.description: root.description
        Accessible.role: Accessible.Button
        onClicked: root.clicked()
    }
    RowLayout {
        id: content
        anchors.fill: parent
        anchors.margins: root.compact ? Tokens.padding.medium : Tokens.padding.large
        spacing: Tokens.spacing.medium
        StyledRect {
            implicitWidth: (root.compact ? 32 : 40) * Tokens.scale
            implicitHeight: implicitWidth
            radius: Tokens.rounding.large
            color: Colours.palette.m3secondaryContainer
            MaterialIcon { anchors.centerIn: parent; text: root.icon; color: Colours.palette.m3onSecondaryContainer }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Tokens.spacing.extraSmall
            StyledText { Layout.fillWidth: true; text: root.title; font: root.compact ? Tokens.font.body.medium : Tokens.font.title.small; wrapMode: Text.WrapAtWordBoundaryOrAnywhere }
            StyledText { Layout.fillWidth: true; visible: !!text; text: root.description; color: Colours.palette.m3onSurfaceVariant; font: Tokens.font.body.small; wrapMode: Text.WrapAtWordBoundaryOrAnywhere }
        }
        MaterialIcon { text: "chevron_right"; color: Colours.palette.m3onSurfaceVariant }
    }
}
