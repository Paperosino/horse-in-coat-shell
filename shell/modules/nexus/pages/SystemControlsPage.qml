import Hyprstack.Config
import Hyprstack.I18n
import QtQuick
import QtQuick.Layouts
import qs.components.controls
import qs.modules.nexus.common
import qs.services

PageBase {
    id: root

    pageIcon: "window"
    title: Tr.tr("Windows & workspaces")
    objectName: "windowBehaviorPage"

    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large

        FeatureError {
            error: LayoutModes.error
        }

        SettingsCard {
            title: Tr.tr("Window layout")
            icon: "view_quilt"

            GenericSettingRow {
                spec: ({
                        "label": "Layout mode",
                        "type": "choice",
                        "choices": LayoutModes.modes.map(m => {
                            return ({
                                    "value": m.id,
                                    "label": m.label
                                });
                        })
                    })
                value: LayoutModes.mode
                enabled: !LayoutModes.busy
                onEdited: v => {
                    return LayoutModes.select(v);
                }
            }

            NavRow {
                first: true
                last: true
                text: Tr.tr("Infinite canvas")
                icon: "gesture"
                onClicked: root.nState.openSubPage(1)
            }
        }

        SettingsCard {
            title: Tr.tr("Overview motion")
            icon: "tune"

            GenericSettingRow {
                spec: ({
                        "label": "Drag smoothing (ms)",
                        "type": "int",
                        "min": 0,
                        "max": 120,
                        "step": 5
                    })
                value: LayoutModes.config.overviewDragMs
                onEdited: v => {
                    return LayoutModes.save("overviewDragMs", v);
                }
            }

            GenericSettingRow {
                spec: ({
                        "label": "Overview animation duration (ms)",
                        "type": "int",
                        "min": 120,
                        "max": 700,
                        "step": 20
                    })
                value: LayoutModes.config.overviewMotionMs
                onEdited: v => {
                    return LayoutModes.save("overviewMotionMs", v);
                }
            }
        }

        SettingsCard {
            title: Tr.tr("Window focus")
            icon: "tune"

            ToggleRow {
                text: Tr.tr("Switch windows on hover in tiling mode")
                checked: Tiling.focusOnHover
                onToggled: Tiling.set("focusOnHover", checked)
            }

            SystemSettingsSection {
                keys: ["input.float_switch_override_focus", "misc.focus_on_activate", "misc.mouse_move_focuses_monitor", "misc.new_window_takes_over_fullscreen"]
            }
        }

        SettingsCard {
            title: Tr.tr("Window resizing")
            icon: "tune"

            SystemSettingsSection {
                keys: ["general.resize_on_border", "general.extend_border_grab_area", "general.hover_icon_on_border"]
            }
        }

        SettingsCard {
            title: Tr.tr("Workspace navigation")
            icon: "tune"

            SystemSettingsSection {
                keys: ["misc.close_special_on_empty", "binds.allow_workspace_cycles", "binds.workspace_back_and_forth"]
            }
        }
    }
}
