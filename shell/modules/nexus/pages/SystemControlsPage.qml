import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components.controls
import qs.services
import qs.modules.nexus.common
PageBase {
    id: root
    title: Tr.tr("Windows & workspaces")
    objectName: "windowBehaviorPage"
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.extraSmall / 2
        FeatureError { error: LayoutModes.error }
        SectionHeader { first: true; text: Tr.tr("Window layout") }
        GenericSettingRow {
            spec: ({label:"Layout mode",type:"choice",choices:LayoutModes.modes.map(m=>({value:m.id,label:m.label}))})
            value: LayoutModes.mode
            enabled: !LayoutModes.busy
            onEdited: v => LayoutModes.select(v)
        }
        NavRow {first:true;last:true;text:Tr.tr("Infinite canvas");icon:"gesture";onClicked:root.nState.openSubPage(1)}
        SectionHeader { text: Tr.tr("Overview motion") }
        GenericSettingRow {spec:({label:"Drag smoothing (ms)",type:"int",min:0,max:120,step:5});value:LayoutModes.config.overviewDragMs;onEdited:v=>LayoutModes.save("overviewDragMs",v)}
        GenericSettingRow {spec:({label:"Overview animation duration (ms)",type:"int",min:120,max:700,step:20});value:LayoutModes.config.overviewMotionMs;onEdited:v=>LayoutModes.save("overviewMotionMs",v)}
        SectionHeader { first: true; text: Tr.tr("Window focus") }
        ToggleRow {
            text: Tr.tr("Switch windows on hover in tiling mode")
            checked: Tiling.focusOnHover
            onToggled: Tiling.set("focusOnHover", checked)
        }
        SystemSettingsSection {
            keys: ["input.float_switch_override_focus", "misc.focus_on_activate", "misc.mouse_move_focuses_monitor", "misc.new_window_takes_over_fullscreen"]
        }
        SectionHeader { text: Tr.tr("Window resizing") }
        SystemSettingsSection { keys: ["general.resize_on_border", "general.extend_border_grab_area", "general.hover_icon_on_border"] }
        SectionHeader { text: Tr.tr("Workspace navigation") }
        SystemSettingsSection { keys: ["misc.close_special_on_empty", "binds.allow_workspace_cycles", "binds.workspace_back_and_forth"] }
    }
}
