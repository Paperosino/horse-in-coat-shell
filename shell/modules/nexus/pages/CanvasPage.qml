import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components.controls
import qs.services
import qs.modules.nexus.common
PageBase {
    id:root
    title:Tr.tr("Infinite canvas")
    ColumnLayout {
        width:root.cappedWidth
        anchors.horizontalCenter:parent.horizontalCenter
        spacing:Tokens.spacing.extraSmall / 2
        FeatureError {error:LayoutModes.error}
        InfoRow {first:true;last:true;label:Tr.tr("Controls");value:Tr.tr("Super+O: overview; Super+middle-drag: pan; Ctrl+wheel: zoom")}
        RowButton {text:Tr.tr("Activate canvas");icon:"gesture";disabled:LayoutModes.busy||!LayoutModes.config.canvasAvailable;onClicked:LayoutModes.select("canvas")}
        InfoRow {first:true;last:true;label:Tr.tr("Keyboard");value:Tr.tr("Super+arrows: focus; Super+Ctrl+arrows: pan; Super+Ctrl + / - / 0: zoom")}
        InfoRow {first:true;last:true;label:Tr.tr("Keyboard shortcuts");value:Tr.tr("Super+F1: shortcut help and window modes")}
        SectionHeader {text:Tr.tr("Camera")}
        GenericSettingRow {spec:({label:"Overview zoom",type:"number",min:LayoutModes.config.canvasMinZoom??.1,max:Math.min(2,LayoutModes.config.canvasMaxZoom??2.5)});value:LayoutModes.config.canvasZoom;onEdited:v=>LayoutModes.save("canvasZoom",v)}
        GenericSettingRow {spec:({label:"Minimum zoom",type:"number",min:.05,max:1});value:LayoutModes.config.canvasMinZoom;onEdited:v=>LayoutModes.save("canvasMinZoom",v)}
        GenericSettingRow {spec:({label:"Maximum zoom",type:"number",min:1,max:5});value:LayoutModes.config.canvasMaxZoom;onEdited:v=>LayoutModes.save("canvasMaxZoom",v)}
        GenericSettingRow {spec:({label:"Zoom step",type:"number",min:.01,max:.5});value:LayoutModes.config.canvasZoomStep;onEdited:v=>LayoutModes.save("canvasZoomStep",v)}
        GenericSettingRow {spec:({label:"Pan sensitivity",type:"number",min:.1,max:5});value:LayoutModes.config.canvasPanSpeed;onEdited:v=>LayoutModes.save("canvasPanSpeed",v)}
        SectionHeader {text:Tr.tr("Placement")}
        GenericSettingRow {spec:({label:"New window spacing",type:"int",min:0,max:300});value:LayoutModes.config.canvasGap;onEdited:v=>LayoutModes.save("canvasGap",v)}
        ToggleRow {text:Tr.tr("Show canvas grid");checked:LayoutModes.config.canvasGrid??true;onToggled:LayoutModes.save("canvasGrid",checked)}
        ToggleRow {text:Tr.tr("Sticky windows");subtext:Tr.tr("Keep the window spacing at neighbouring edges. Drag further to detach and overlap.");checked:!!LayoutModes.config.canvasSticky;onToggled:LayoutModes.save("canvasSticky",checked)}
        ToggleRow {text:Tr.tr("Snap windows to grid");checked:!!LayoutModes.config.canvasSnap;onToggled:LayoutModes.save("canvasSnap",checked)}
        GenericSettingRow {visible:!!LayoutModes.config.canvasSnap;spec:({label:"Grid step",type:"int",min:24,max:300});value:LayoutModes.config.canvasSnapSize;onEdited:v=>LayoutModes.save("canvasSnapSize",v)}
        ToggleRow {text:Tr.tr("Focus canvas windows on hover");checked:!!LayoutModes.config.canvasHoverFocus;onToggled:LayoutModes.save("canvasHoverFocus",checked)}
        ToggleRow {text:Tr.tr("Show canvas minimap");checked:LayoutModes.config.canvasMinimap??true;onToggled:LayoutModes.save("canvasMinimap",checked)}
        ToggleRow {text:Tr.tr("Remember canvas positions");checked:LayoutModes.config.canvasRemember??true;onToggled:LayoutModes.save("canvasRemember",checked)}
        SectionHeader {text:Tr.tr("Canvas actions")}
        RowButton {text:Tr.tr("Zoom in");icon:"zoom_in";disabled:LayoutModes.mode!=="canvas"||LayoutModes.busy;onClicked:LayoutModes.action("zoom in")}
        RowButton {text:Tr.tr("Zoom out");icon:"zoom_out";disabled:LayoutModes.mode!=="canvas"||LayoutModes.busy;onClicked:LayoutModes.action("zoom out")}
        RowButton {text:Tr.tr("Reset zoom");icon:"center_focus_strong";disabled:LayoutModes.mode!=="canvas"||LayoutModes.busy;onClicked:LayoutModes.action("zoom reset")}
        RowButton {text:Tr.tr("Fit all windows");icon:"zoom_out_map";disabled:LayoutModes.mode!=="canvas"||LayoutModes.busy;onClicked:LayoutModes.action("fit")}
        RowButton {text:Tr.tr("Arrange canvas windows");icon:"grid_view";disabled:LayoutModes.mode!=="canvas"||LayoutModes.busy;onClicked:LayoutModes.action("arrange")}
        RowButton {text:Tr.tr("Undo canvas action");icon:"undo";disabled:LayoutModes.mode!=="canvas"||LayoutModes.busy;onClicked:LayoutModes.action("undo")}
    }
}
