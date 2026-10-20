pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components.controls

RowLayout {
    id: root
    required property var spec
    property var value: spec.value ?? spec.default
    property bool resettable: false
    signal edited(var value)
    signal resetRequested()
    Layout.fillWidth: true
    spacing: Tokens.spacing.small
    Loader {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        sourceComponent: root.spec.type === "bool" ? boolRow : root.spec.type === "int" ? intRow : root.spec.type === "choice" ? choiceRow : root.spec.type === "slider" ? sliderRow : textRow
    }
    IconButton { visible: root.resettable && !!root.spec.overridden; icon: "restart_alt"; onClicked: root.resetRequested() }
    Component {
        id: sliderRow
        SliderRow {
            property real currentNum: Number(root.value)
            label: Tr.tr(root.spec.label)
            icon: "tune"
            valueLabel: currentNum.toFixed(2)
            value: (Number(root.value) - root.spec.min) / (root.spec.max - root.spec.min)
            onMoved: v => {
                const nextVal = Math.round((root.spec.min + v * (root.spec.max - root.spec.min)) * 100) / (root.spec.step ? (1 / root.spec.step) : 100);
                currentNum = nextVal;
                root.edited(nextVal);
            }
        }
    }
    Component {
        id: boolRow
        ToggleRow { text: Tr.tr(root.spec.label); checked: !!root.value; onToggled: root.edited(checked) }
    }
    Component {
        id: intRow
        StepperRow {
            label: Tr.tr(root.spec.label)
            value: Number(root.value ?? 0)
            from: root.spec.min ?? 0
            to: root.spec.max ?? 10000
            stepSize: root.spec.step ?? 1
            onMoved: v => root.edited(Math.round(v))
        }
    }
    Component {
        id: choiceRow
        SelectRow {
            readonly property list<MenuItem> options: (root.spec.choices ?? []).map(v => choice.createObject(root, {text: v === "" ? Tr.tr("Default") : String(typeof v === "object" ? v.label ?? v.name ?? v.value : v), value: typeof v === "object" ? v.value : v}))
            label: Tr.tr(root.spec.label)
            menuItems: options
            active: options.find(o => o.value === root.value) ?? null
            fallbackText: String(root.value ?? "")
            onSelected: item => root.edited(item.value)
        }
    }
    Component { id: choice; MenuItem {} }
    Component {
        id: textRow
        TextFieldRow {
            label: Tr.tr(root.spec.label)
            subtext: root.spec.type === "number" ? String(root.spec.min ?? "") + " … " + String(root.spec.max ?? "") : (root.spec.description ?? "")
            value: typeof root.value === "object" ? JSON.stringify(root.value) : String(root.value ?? "")
            validate: text => {
                if (root.spec.type === "json") { try { JSON.parse(text); return true; } catch (e) { return false; } }
                return root.spec.type !== "number" || Number.isFinite(Number(text)) && (root.spec.min === undefined || Number(text) >= root.spec.min) && (root.spec.max === undefined || Number(text) <= root.spec.max);
            }
            onEditingFinished: text => {
                if (root.spec.type === "json") { try { root.edited(JSON.parse(text)); } catch (e) {} }
                else if (root.spec.type === "number") { if (Number.isFinite(Number(text))) root.edited(Number(text)); }
                else root.edited(text);
            }
        }
    }
}
