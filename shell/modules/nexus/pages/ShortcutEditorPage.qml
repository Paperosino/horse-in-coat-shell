pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import Quickshell
import Quickshell.Wayland
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.components.controls
import qs.modules.nexus.common
import qs.services
import "../../../services/Keybinds.js" as Bindings

PageBase {
    pageIcon: "keyboard"
    id:root
    title:Tr.tr("Keyboard shortcuts")
    property var backend:ShortcutEditor
    property string query
    property var editing:({})
    property string chord
    property bool recording:false
    property bool advanced:false
    property bool confirmReset:false
    readonly property bool hasEditor:!!editing.id||editing.custom===true
    readonly property var filtered:backend.actions.filter(a=>!query.trim()||[a.description,...(a.keys??[]),a.submap].join(" ").toLowerCase().includes(query.toLowerCase()))
    readonly property var conflicts:hasEditor&&chord?backend.conflicts(editing.id??"",chord,editing.submap??""):[]
    function actionTitle(description):string {const text=description??"";const colon=text.indexOf(": ");return colon<0?Tr.tr(text):Tr.tr(text.slice(0,colon))+": "+Bindings.translateDescription(text.slice(colon+2),v=>Tr.tr(v))}
    function begin(action):void {editing=JSON.parse(JSON.stringify(action));chord=(editing.keys??[])[0]??"";recording=false;flickable.contentY=0}
    function set(key,value):void {editing=Object.assign({},editing,{[key]:value})}
    function flag(key,value):void {set("flags",Object.assign({},editing.flags??({}),{[key]:value}))}
    function save():void {backend.save(Object.assign({},editing,{keys:chord.split("\n").map(s=>s.trim()).filter(Boolean)}));if(!backend.error){editing=({});recording=false}}
    Component.onCompleted:backend.refresh()
    readonly property FileDialog importer:FileDialog {title:Tr.tr("Import keyboard shortcuts");nameFilters:["JSON (*.json)"];onAccepted:root.backend.importFile(selectedFile)}
    readonly property FileDialog exporter:FileDialog {title:Tr.tr("Export keyboard shortcuts");fileMode:FileDialog.SaveFile;defaultSuffix:"json";onAccepted:root.backend.exportFile(selectedFile)}
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
        SettingsCard {
            title:Tr.tr("Make the keyboard yours");description:Tr.tr("Record a combination, check conflicts and customise actions without editing configuration files.");icon:"keyboard_keys";badge:String(root.backend.actions.length)
            RowLayout {
                Layout.fillWidth:true
                RowButton {text:Tr.tr("Add shortcut");icon:"add";onClicked:root.begin({custom:true,description:"",command:"",keys:[],flags:{},submap:""})}
                RowButton {text:Tr.tr("Refresh");icon:"refresh";onClicked:root.backend.refresh()}
            }
            FeatureError {error:root.backend.error}
        }
        SettingsCard {
            objectName:"shortcutEditorCard";visible:root.hasEditor
            title:root.editing.custom?Tr.tr("Custom shortcut"):root.actionTitle(root.editing.description)
            description:Tr.tr("Changes apply immediately and survive compositor restarts.");icon:"edit"
            TextFieldRow {visible:root.editing.custom===true;label:Tr.tr("Name");value:root.editing.description??"";onValueEdited:v=>root.set("description",v)}
            TextFieldRow {visible:root.editing.custom===true;label:Tr.tr("Command");subtext:Tr.tr("The command runs when you press this shortcut.");value:root.editing.command??"";onValueEdited:v=>root.set("command",v)}
            ConnectedRect {
                id:recorder
                Layout.fillWidth:true;first:true;last:true
                color:root.recording?Colours.palette.m3secondaryContainer:Colours.palette.m3surfaceContainerHigh
                implicitHeight:100*Tokens.scale
                focus:root.recording
                Keys.onShortcutOverride:event=>{if(root.recording)event.accepted=true}
                Keys.onPressed:event=>{
                    if(!root.recording)return;
                    event.accepted=true;
                    if(event.key===Qt.Key_Escape){root.recording=false;return}
                    const value=root.backend.recordKey(event.key,event.modifiers,event.nativeScanCode??0);
                    if(value){root.chord=value;root.recording=false}
                }
                ColumnLayout {
                    anchors.centerIn:parent;spacing:8
                    StyledText {Layout.alignment:Qt.AlignHCenter;text:root.recording?Tr.tr("Press your new shortcut…"):root.chord||Tr.tr("No combination assigned");font:Tokens.font.title.medium;color:Colours.palette.m3primary}
                    StyledText {Layout.alignment:Qt.AlignHCenter;text:root.recording?Tr.tr("Esc cancels recording"):Tr.tr("Super is the Windows / Meta key");font:Tokens.font.label.small;color:Colours.palette.m3onSurfaceVariant}
                }
            }
            RowButton {text:Tr.tr(root.recording?"Cancel recording":"Record combination");icon:root.recording?"close":"keyboard";onClicked:{root.recording=!root.recording;if(root.recording)root.forceRecorderFocus()}}
            TextFieldRow {label:Tr.tr("Key combination");subtext:Tr.tr("For example SUPER + SHIFT + T. Physical keys can use code: followed by a Hyprland keycode.");value:root.chord;onValueEdited:v=>root.chord=v}
            FeatureError {error:root.conflicts.length?Tr.tr("Already assigned")+": "+root.conflicts.map(a=>a.description).join(", "):""}
            ToggleRow {text:Tr.tr("Enabled");checked:!root.editing.disabled;onToggled:v=>root.set("disabled",!v)}
            RowButton {text:Tr.tr("Advanced behaviour");icon:"tune";trailingIcon:root.advanced?"expand_less":"expand_more";onClicked:root.advanced=!root.advanced}
            ColumnLayout {
                visible:root.advanced;Layout.fillWidth:true
                ToggleRow {text:Tr.tr("Bind by physical key position");subtext:Tr.tr("Recorded keys use a keycode and work independently of the keyboard layout.");checked:root.backend.settings.physicalKeys??false;onToggled:v=>root.backend.configure({physicalKeys:v})}
                ToggleRow {text:Tr.tr("Repeat while held");checked:root.editing.flags?.repeating??false;onToggled:v=>root.flag("repeating",v)}
                ToggleRow {text:Tr.tr("Trigger on release");checked:root.editing.flags?.release??false;onToggled:v=>root.flag("release",v)}
                ToggleRow {text:Tr.tr("Available while locked");checked:root.editing.flags?.locked??false;onToggled:v=>root.flag("locked",v)}
                ToggleRow {text:Tr.tr("Mouse binding");checked:root.editing.flags?.mouse??false;onToggled:v=>root.flag("mouse",v)}
                ToggleRow {text:Tr.tr("Do not consume input");checked:root.editing.flags?.non_consuming??false;onToggled:v=>root.flag("non_consuming",v)}
                TextFieldRow {visible:root.editing.custom===true;label:Tr.tr("Submap");subtext:Tr.tr("Leave empty for a global shortcut.");value:root.editing.submap??"";onValueEdited:v=>root.set("submap",v)}
            }
            RowLayout {
                Layout.fillWidth:true
                RowButton {objectName:"saveShortcut";text:Tr.tr("Save shortcut");icon:"check";disabled:root.conflicts.length>0;onClicked:root.save()}
                RowButton {text:Tr.tr("Cancel");icon:"close";onClicked:{root.editing=({});root.recording=false}}
            }
            RowButton {visible:!!root.editing.id;text:Tr.tr(root.editing.custom?"Delete shortcut":"Restore default");icon:root.editing.custom?"delete":"restart_alt";onClicked:{root.backend.reset(root.editing.id);if(!root.backend.error)root.editing=({})}}
        }
        SettingsCard {
            title:Tr.tr("Actions and combinations");description:Tr.tr("Choose an action to edit its shortcut. Modified actions are marked.");icon:"category"
            StyledTextField {Layout.fillWidth:true;placeholderText:Tr.tr("Search keyboard shortcuts");onTextChanged:root.query=text}
            Repeater {
                model:root.filtered
                RowButton {
                    required property var modelData
                    text:root.actionTitle(modelData.description)
                    subtext:(modelData.disabled?Tr.tr("Disabled"):(modelData.keys??[]).join("  /  "))+(modelData.submap?" · "+modelData.submap:"")
                    icon:modelData.custom?"terminal":modelData.modified?"edit_note":"keyboard"
                    trailingIcon:"chevron_right"
                    onClicked:root.begin(modelData)
                }
            }
            StyledText {visible:!root.filtered.length;text:Tr.tr("No matching shortcuts");color:Colours.palette.m3onSurfaceVariant}
        }
        SettingsCard {
            title:Tr.tr("Import, export and defaults");description:Tr.tr("Keep a portable backup of your custom keyboard setup.");icon:"settings_backup_restore"
            RowLayout {Layout.fillWidth:true;RowButton {text:Tr.tr("Import");icon:"file_open";onClicked:root.importer.open()} RowButton {text:Tr.tr("Export");icon:"file_save";onClicked:root.exporter.open()}}
            RowButton {text:Tr.tr("Restore all default shortcuts");icon:"restart_alt";onClicked:root.confirmReset=!root.confirmReset}
            RowButton {visible:root.confirmReset;text:Tr.tr("Confirm reset");icon:"check";onClicked:{root.backend.resetAll();root.confirmReset=false}}
        }
    }
    onVisibleChanged:if(!visible)recording=false
    readonly property ShortcutInhibitor inhibitor:ShortcutInhibitor {window:root.QsWindow.window;enabled:root.recording;onCancelled:root.recording=false}
    function forceRecorderFocus():void {Qt.callLater(()=>recorder.forceActiveFocus())}
}
