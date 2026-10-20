pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.I18n
import qs.components.controls
import qs.services

Flow {
    width: parent.width
    spacing: 6
    Repeater {
        model: LayoutModes.modes
        TextButton {
            required property var modelData
            text: modelData.label
            isToggle: true
            checked: LayoutModes.mode === modelData.id
            disabled: LayoutModes.busy
            activeFocusOnTab: true
            border.width: activeFocus ? 1 : 0
            border.color: Colours.palette.m3primary
            function choose(): void {
                if (disabled) return;
                internalChecked = checked;
                if (!checked) LayoutModes.select(modelData.id);
            }
            onClicked: choose()
            Keys.onReturnPressed: choose()
            Keys.onEnterPressed: choose()
            Keys.onSpacePressed: choose()
            Accessible.name: Tr.tr("Window layout") + ": " + modelData.label
        }
    }
}
