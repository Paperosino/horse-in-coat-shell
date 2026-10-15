pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services

ConnectedRect {
    id: borderColors

    property string label
    property string subtext
    property string value
    property QtObject palette
    property var choices: []
    property string choicePrefix: "focusBorderColor_"
    readonly property var displayChoices: {
        if (!palette)
            return [];
        const unique = [], colours = {};
        // Keep an older selection available even when it isn't one of the
        // scheme's main hues. Missing source roles resolve to the theme accent.
        const candidates = choices.slice();
        if (value && !candidates.some(choice => choice.role === value))
            candidates.push({role: value, label: value.startsWith("#") ? "Custom colour" : Colours.labelForRole(value)});
        for (const choice of candidates) {
            const colour = choice.role.startsWith("#") ? choice.role.toLowerCase()
                : Colours.colourForRole(choice.role, palette).toString();
            if (!colour)
                continue;
            const key = colour.toLowerCase();
            if (colours[key]) {
                colours[key].roles.push(choice.role);
            } else {
                const entry = {role: choice.role, label: choice.label, colour, roles: [choice.role]};
                colours[key] = entry;
                unique.push(entry);
            }
        }
        return unique;
    }

    signal selected(role: string)

    Layout.fillWidth: true
    implicitHeight: borderColorLayout.implicitHeight + Tokens.padding.medium * 2

    ColumnLayout {
        id: borderColorLayout

        anchors.fill: parent
        anchors.margins: Tokens.padding.medium
        anchors.leftMargin: Tokens.padding.largeIncreased
        anchors.rightMargin: Tokens.padding.largeIncreased
        spacing: Tokens.spacing.small

        StyledText {
            Layout.fillWidth: true
            text: borderColors.label
            font: Tokens.font.body.small
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        }

        StyledText {
            Layout.fillWidth: true
            text: borderColors.subtext
            color: Colours.palette.m3outline
            font: Tokens.font.label.small
            wrapMode: Text.WordWrap
        }

        Flow {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

            Repeater {
                model: borderColors.displayChoices

                StyledRect {
                    id: borderColorChip

                    required property var modelData
                    readonly property bool selected: modelData.roles.includes(borderColors.value)
                    readonly property string selectionRole: selected ? borderColors.value : modelData.role
                    readonly property color swatch: modelData.colour
                    readonly property string label: Tr.tr(modelData.label || Colours.labelForRole(modelData.role))
                    objectName: borderColors.choicePrefix + modelData.role
                    width: borderChipContent.implicitWidth + Tokens.padding.small * 2
                    height: 34 * Tokens.scale
                    radius: Tokens.rounding.full
                    color: selected ? Colours.palette.m3secondaryContainer : Colours.palette.m3surfaceContainerHigh
                    border.width: selected ? 2 : 1
                    border.color: selected ? swatch : Colours.palette.m3outlineVariant
                    activeFocusOnTab: true
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: label
                    Accessible.checked: selected
                    Keys.onReturnPressed: borderColors.selected(selectionRole)
                    Keys.onSpacePressed: borderColors.selected(selectionRole)

                    Row {
                        id: borderChipContent

                        anchors.centerIn: parent
                        spacing: Tokens.spacing.small

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 16 * Tokens.scale
                            height: width
                            radius: width / 2
                            color: borderColorChip.swatch
                        }

                        StyledText {
                            text: borderColorChip.label
                            font: Tokens.font.label.small
                        }
                    }

                    StateLayer {
                        color: borderColorChip.swatch
                        onClicked: borderColors.selected(borderColorChip.selectionRole)
                    }
                }
            }
        }
    }
}
