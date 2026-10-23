import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: groups[0]==="Touchpad" ? "touchpad_mouse" : groups[0]==="Cursor" ? "arrow_selector_tool" : groups[0]==="Gestures" ? "swipe" : "mouse"
    property list<string> groups: []
    readonly property var sections: ({
            Mouse: [
                {
                    title: "Pointer",
                    keys: ["input.sensitivity", "input.accel_profile", "input.left_handed"]
                },
                {
                    title: "Scrolling",
                    keys: ["input.natural_scroll", "input.scroll_factor", "input.scroll_method", "input.scroll_button", "input.scroll_button_lock"]
                }
            ],
            Touchpad: [
                {
                    title: "Taps and clicks",
                    keys: ["input.touchpad.tap-to-click", "input.touchpad.tap-and-drag", "input.touchpad.drag_lock", "input.touchpad.clickfinger_behavior", "input.touchpad.middle_button_emulation", "input.touchpad.tap_button_map"]
                },
                {
                    title: "Scrolling",
                    keys: ["input.touchpad.natural_scroll", "input.touchpad.scroll_factor"]
                },
                {
                    title: "Pointer movement",
                    keys: ["input.touchpad.disable_while_typing", "input.touchpad.flip_x", "input.touchpad.flip_y"]
                }
            ],
            Cursor: [
                {
                    title: "Cursor visibility",
                    keys: ["cursor.inactive_timeout", "cursor.hide_on_key_press", "cursor.hide_on_touch"]
                },
                {
                    title: "Pointer movement",
                    keys: ["cursor.no_warps", "cursor.warp_on_change_workspace", "cursor.hotspot_padding"]
                },
                {
                    title: "Magnification",
                    keys: ["cursor.zoom_factor", "cursor.zoom_rigid"]
                }
            ],
            Gestures: [
                {
                    title: "Workspace swipes",
                    keys: ["gestures.workspace_swipe_distance", "gestures.workspace_swipe_invert", "gestures.workspace_swipe_forever", "gestures.workspace_swipe_create_new", "gestures.workspace_swipe_cancel_ratio", "gestures.workspace_swipe_min_speed_to_force", "gestures.workspace_swipe_touch"]
                }
            ]
        })[groups[0]] ?? []
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large
        ToggleRow {
            visible: root.groups[0] === "Mouse"
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            objectName: "appearanceAutoscroll"
            text: Tr.tr("Middle-click autoscroll")
            subtext: Tr.tr("Hold the wheel briefly, then move. Short clicks keep tab and link actions; Esc stops.")
            checked: Tiling.autoscroll
            onToggled: Tiling.set("autoscroll", checked)
        }
        Repeater {
            model: root.sections
            delegate: SettingsCard {
                id: deviceSection
                title: Tr.tr(modelData.title)
                icon: modelData.title==="Scrolling" ? "swap_vert" : root.pageIcon
                required property var modelData
                Layout.fillWidth: true
                SystemSettingsSection {
                    keys: deviceSection.modelData.keys
                }
            }
        }
    }
}
