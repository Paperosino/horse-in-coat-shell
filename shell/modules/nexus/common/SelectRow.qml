import Hyprstack.Config
import QtQuick
import QtQuick.Layouts
import qs.components
import qs.components.controls
import qs.modules.nexus.common
import qs.services

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

    signal selected(MenuItem item)

    Layout.fillWidth: true
    implicitHeight: rowLayout.implicitHeight + rowLayout.anchors.margins * 2
    clip: false
    z: splitButton.expanded ? 1 : 0

    GridLayout {
        id: rowLayout

        columns: root.width < 440 * Tokens.scale ? 1 : 2
        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        anchors.leftMargin: Tokens.padding.largeIncreased
        anchors.rightMargin: Tokens.padding.largeIncreased
        rowSpacing: Tokens.spacing.medium
        columnSpacing: Tokens.spacing.medium

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 3 * Tokens.scale

            StyledText {
                id: label

                Layout.fillWidth: true
                font: Tokens.font.body.medium
                Layout.minimumWidth: 0
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }

            StyledText {
                Layout.fillWidth: true
                visible: root.subtext
                text: root.subtext
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small
                Layout.minimumWidth: 0
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            }
        }

        SplitButton {
            id: splitButton

            Layout.maximumWidth: root.width < 440 * Tokens.scale ? rowLayout.width : rowLayout.width * 0.5
            Layout.minimumWidth: Math.min(implicitWidth, 100 * Tokens.scale)
            type: SplitButton.Tonal
            stateLayer.onClicked: splitButton.expanded = !splitButton.expanded
            menu.onItemSelected: item => {
                return root.selected(item);
            }
        }
    }
}
