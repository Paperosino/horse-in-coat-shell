import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

ConnectedRect {
    id: root

    property alias label: label.text
    property string subtext
    property alias menuItems: splitButton.menuItems
    property alias active: splitButton.active
    property alias fallbackText: splitButton.fallbackText
    property alias fallbackIcon: splitButton.fallbackIcon
    property alias menuOnTop: splitButton.menuOnTop
    property alias updateActiveOnSelection: splitButton.menu.updateActiveOnSelection

    signal selected(item: MenuItem)

    Layout.fillWidth: true
    implicitHeight: rowLayout.implicitHeight + rowLayout.anchors.margins * 2
    clip: false
    z: splitButton.expanded ? 1 : 0

    RowLayout {
        id: rowLayout

        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        anchors.leftMargin: Tokens.padding.largeIncreased
        anchors.rightMargin: Tokens.padding.largeIncreased
        spacing: Tokens.spacing.medium

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 0

            StyledText {
                id: label

                Layout.fillWidth: true
                font: Tokens.font.body.small
                Layout.minimumWidth: 0
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }

            StyledText {
                Layout.fillWidth: true
                visible: root.subtext
                text: root.subtext
                color: Colours.palette.m3outline
                font: Tokens.font.label.small
                Layout.minimumWidth: 0
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }
        }

        SplitButton {
            id: splitButton

            Layout.maximumWidth: rowLayout.width * 0.5
            Layout.minimumWidth: Math.min(implicitWidth, 100 * Tokens.scale)
            type: SplitButton.Tonal
            stateLayer.onClicked: splitButton.expanded = !splitButton.expanded
            menu.onItemSelected: item => root.selected(item)
        }
    }
}
