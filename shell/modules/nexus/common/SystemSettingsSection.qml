pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.services

ColumnLayout {
    id: root
    property list<string> groups: []
    property list<string> keys: []
    property list<string> excludedKeys: []
    readonly property var fields: SystemControls.fields.filter(f => f.available && !excludedKeys.includes(f.key) && applicable(f.key) && (keys.includes(f.key) || groups.includes(f.group)))
    function applicable(key: string): bool {
        function current(name, fallback) { return SystemControls.fields.find(f => f.key === name)?.value ?? fallback; }
        if (key === "input.scroll_button" || key === "input.scroll_button_lock") return current("input.scroll_method", "") === "on_button_down";
        if (key === "cursor.zoom_rigid") return current("cursor.zoom_factor", 1) > 1;
        if (key === "input.touchpad.drag_lock") return current("input.touchpad.tap-and-drag", true);
        return true;
    }
    function displaySpec(field: var): var {
        const names = ({
            "input.accel_profile": ["Default", "No acceleration", "Adaptive"],
            "input.scroll_method": ["Default", "Two fingers", "Edge scrolling", "Hold a button", "Disabled"],
            "input.touchpad.tap_button_map": ["Left, right, middle", "Left, middle, right"]
        })[field.key];
        const spec = Object.assign({}, field);
        if (field.type === "number") spec.type = "slider";
        if (names) spec.choices = field.choices.map((v, i) => ({value: v, label: Tr.tr(names[i])}));
        return spec;
    }
    Layout.fillWidth: true
    spacing: Tokens.spacing.extraSmall / 2
    visible: fields.length > 0
    Component.onCompleted: if (!SystemControls.fields.length && !SystemControls.busy) SystemControls.reload()
    FeatureError { error: SystemControls.error }
    Repeater {
        model: root.fields
        delegate: GenericSettingRow {
            required property var modelData
            spec: root.displaySpec(modelData)
            objectName: "system_" + modelData.key
            resettable: true
            onEdited: value => SystemControls.set(modelData.key, value)
            onResetRequested: SystemControls.reset(modelData.key)
        }
    }
}
