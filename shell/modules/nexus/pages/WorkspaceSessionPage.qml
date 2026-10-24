pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.services
import qs.components.controls
import qs.modules.nexus.common

PageBase {
    property bool projectsOnly: false
    property int sourceWorkspace: -1
    property int targetWorkspace: 1
    property string projectMode: "stacking"
    property bool keepTheme: false
    pageIcon: projectsOnly ? "workspaces" : "restore"
    id:root
    title:Tr.tr(projectsOnly ? "Workspace projects" : "Session recovery")
    property var backend:WorkspaceSession
    readonly property var config:backend.settings
    property string name
    property var form:({})
    property bool confirmRestore:false
    property string removing
    property string commandError
    property bool details:false
    property var desktopSessions: backend.desktopSessions?backend.desktopSessions():[]
    readonly property var selected:(form.windows??[]).filter(w=>w.enabled!==false)
    function set(key,value):void {backend.configure({[key]:value})}
    function projectChange(key,value):void {form=Object.assign({},form,{project:Object.assign({},form.project,{[key]:value})})}
    function vectorChange(index,key,slot,value):void {const vector=(form.windows[index][key]??(key==="size"?[800,600]:[0,0])).slice();vector[slot]=value;windowChange(index,key,vector)}
    function windowChange(index,key,value):void {const windows=(form.windows??[]).slice();windows[index]=Object.assign({},windows[index],{[key]:value});form=Object.assign({},form,{windows:windows})}
    Component.onCompleted:backend.refresh()
    readonly property Connections backendConnections:Connections {target:root.backend;function onChanged():void {if(root.backend.preview.id!==root.form.id||JSON.stringify(root.backend.preview)!==root.previewSignature)root.loadPreview()}}
    property string previewSignature
    function loadPreview():void {previewSignature=JSON.stringify(backend.preview);form=JSON.parse(previewSignature);confirmRestore=false;commandError=""}
    readonly property FileDialog importer:FileDialog {title:Tr.tr("Import session snapshot");nameFilters:["hics session (*.json)"];onAccepted:root.backend.importFile(selectedFile)}
    readonly property FileDialog exporter:FileDialog {title:Tr.tr("Export session snapshot");fileMode:FileDialog.SaveFile;defaultSuffix:"json";onAccepted:root.backend.exportFile(root.form.id,selectedFile,false)}
    readonly property FolderDialog portable:FolderDialog {title:Tr.tr("Export portable application starters");onAccepted:root.backend.exportFile(root.form.id,selectedFolder,true)}
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
        SettingsCard {
            title:Tr.tr(root.projectsOnly?"Launch a workspace project":"Pick up where you left off");description:Tr.tr(root.projectsOnly?"Keep a named set of applications, a window layout and optional colours. Projects stay separate from automatic session checkpoints.":"Save a workspace, choose what returns and recover applications after signing in.");icon:"restore";badge:root.backend.desktop
            ToggleRow {visible:!root.projectsOnly;text:Tr.tr("Session recovery");checked:root.config.enabled??false;onToggled:v=>root.set("enabled",v)}
            RowLayout {
                Layout.fillWidth:true
                StyledTextField {Layout.fillWidth:true;placeholderText:Tr.tr("Snapshot name");onTextChanged:root.name=text}
                IconButton {icon:"add_photo_alternate";Accessible.name:Tr.tr("Save current session");disabled:root.backend.busy;onClicked:{const name=root.name.trim()||new Date().toLocaleString();if(root.projectsOnly)root.backend.captureProject(name,root.sourceWorkspace,root.targetWorkspace,root.projectMode,root.keepTheme);else root.backend.capture(name,false);}}
            }
            ColumnLayout {
                visible:root.projectsOnly
                Layout.fillWidth:true
                GenericSettingRow {spec:({type:"choice",label:"Capture applications from",choices:[{value:-1,label:"Current workspace"},{value:0,label:"All workspaces"}],value:root.sourceWorkspace});onEdited:value=>root.sourceWorkspace=value}
                GenericSettingRow {spec:({type:"choice",label:"Project window layout",choices:["stacking","scrolling","tiling","canvas"],value:root.projectMode});onEdited:value=>root.projectMode=value}
                StepperRow {label:Tr.tr("Project workspace number");from:1;to:1000000;value:root.targetWorkspace;onMoved:value=>root.targetWorkspace=value}
                ToggleRow {text:Tr.tr("Remember current colour scheme");checked:root.keepTheme;onToggled:root.keepTheme=checked}
            }
            FeatureError {error:root.backend.error||root.commandError}
            RowButton {visible:root.backend.busy;text:Tr.tr("Working… Cancel");icon:"stop";onClicked:root.backend.cancel()}
        }
        SettingsCard {
            title:Tr.tr("Saved workspaces");description:Tr.tr("Inspect a snapshot before restoring. Applications can be selected individually.");icon:"view_quilt"
            GridLayout {
                Layout.fillWidth:true;columns:width>600?2:1;columnSpacing:Tokens.spacing.small;rowSpacing:Tokens.spacing.small
                Repeater {
                    model:root.backend.snapshots.filter(s=>root.projectsOnly?!!s.project?.enabled:!s.project?.enabled)
                    RowButton {
                        required property var modelData
                        text:modelData.name;subtext:String(modelData.count)+" · "+Tr.tr("windows")+" · "+new Date(modelData.created*1000).toLocaleString()
                        icon:modelData.id==="automatic"?"update":"bookmark";trailingIcon:"chevron_right";first:true;last:true
                        disabled:root.backend.busy;onClicked:{root.backend.inspect(modelData.id);root.loadPreview()}
                    }
                }
            }
            StyledText {visible:!root.backend.snapshots.length;text:Tr.tr("Your saved workspaces will appear here");color:Colours.palette.m3onSurfaceVariant}
        }
        SettingsCard {
            objectName:"sessionSnapshotPreview";visible:!!root.form.id
            title:root.form.name??"";description:Tr.tr("Only selected applications will be restored. Changes are saved to this snapshot.");icon:"preview";badge:String(root.selected.length)
            TextFieldRow {label:Tr.tr("Snapshot name");value:root.form.name??"";onValueEdited:v=>root.form=Object.assign({},root.form,{name:v})}
            ColumnLayout {
                Layout.fillWidth:true;visible:!!root.form.project?.enabled
                TextFieldRow {label:Tr.tr("Workspace name");value:root.form.project?.workspaceName??"";onValueEdited:value=>root.projectChange("workspaceName",value)}
                StepperRow {label:Tr.tr("Project workspace number");from:1;to:1000000;value:root.form.project?.workspace??1;onMoved:value=>root.projectChange("workspace",value)}
                GenericSettingRow {spec:({type:"choice",label:"Project window layout",choices:["stacking","scrolling","tiling","canvas"],value:root.form.mode??"stacking"});onEdited:value=>root.form=Object.assign({},root.form,{mode:value})}
                ToggleRow {text:Tr.tr("Restore saved colour scheme");checked:root.form.project?.applyTheme??false;onToggled:root.projectChange("applyTheme",checked)}
                ToggleRow {text:Tr.tr("Reuse running applications");checked:root.form.project?.skipRunning??true;onToggled:root.projectChange("skipRunning",checked)}
                ToggleRow {text:Tr.tr("Restore each captured window");checked:root.form.project?.launchPerWindow??false;onToggled:root.projectChange("launchPerWindow",checked)}
            }
            ToggleRow {text:Tr.tr("Show launch commands and window details");checked:root.details;onToggled:v=>root.details=v}
            Repeater {
                model:root.form.windows??[]
                SettingsCard {
                    id:entry
                    required property var modelData
                    required property int index
                    title:modelData.name??modelData.application??""
                    description:modelData.title??modelData.reason??""
                    icon:"apps"
                    ToggleRow {text:Tr.tr("Restore this application");checked:entry.modelData.enabled!==false;onToggled:v=>root.windowChange(entry.index,"enabled",v)}
                    ColumnLayout {
                        visible:root.details;Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall
                        StyledText {Layout.fillWidth:true;text:(entry.modelData.command??[]).join(" ");textFormat:Text.PlainText;wrapMode:Text.WrapAnywhere;color:Colours.palette.m3primary;font:Tokens.font.label.small}
                        VpnTextArea {label:"Launch arguments (JSON array)";hint:"The first element is the executable. Arguments are passed directly, without a shell.";value:JSON.stringify(entry.modelData.command??[]);onEdited:v=>{try{const argv=JSON.parse(v);if(!Array.isArray(argv)||argv.some(a=>typeof a!=="string"))throw new Error();root.windowChange(entry.index,"command",argv);root.commandError=""}catch(e){root.commandError=Tr.tr("Expected an array of command arguments")}}}
                        TextFieldRow {label:Tr.tr("Working directory");value:entry.modelData.workingDirectory??"";onValueEdited:v=>root.windowChange(entry.index,"workingDirectory",v)}
                        GenericSettingRow {spec:({label:"Delay after launch (ms)",type:"int",min:0,max:60000,step:100});value:entry.modelData.launchDelay??root.config.launchDelay??500;onEdited:v=>root.windowChange(entry.index,"launchDelay",v)}
                        GenericSettingRow {spec:({label:"Workspace",type:"int",min:1,max:1000});value:entry.modelData.workspace??1;onEdited:v=>root.windowChange(entry.index,"workspace",v)}
                        ToggleRow {text:Tr.tr("Floating window");checked:entry.modelData.floating??false;onToggled:v=>root.windowChange(entry.index,"floating",v)}
                        TextFieldRow {label:Tr.tr("Monitor");value:entry.modelData.monitor??"";onValueEdited:v=>root.windowChange(entry.index,"monitor",v)}
                        GridLayout {
                            visible:entry.modelData.floating??false;columns:2;Layout.fillWidth:true
                            GenericSettingRow {spec:({label:"X position",type:"int",min:-1000000,max:1000000,step:10});value:entry.modelData.at?.[0]??0;onEdited:v=>root.vectorChange(entry.index,"at",0,v)}
                            GenericSettingRow {spec:({label:"Y position",type:"int",min:-1000000,max:1000000,step:10});value:entry.modelData.at?.[1]??0;onEdited:v=>root.vectorChange(entry.index,"at",1,v)}
                            GenericSettingRow {spec:({label:"Window width",type:"int",min:100,max:16384,step:10});value:entry.modelData.size?.[0]??800;onEdited:v=>root.vectorChange(entry.index,"size",0,v)}
                            GenericSettingRow {spec:({label:"Window height",type:"int",min:80,max:16384,step:10});value:entry.modelData.size?.[1]??600;onEdited:v=>root.vectorChange(entry.index,"size",1,v)}
                        }
                        GenericSettingRow {spec:({label:"Window state",type:"choice",choices:[{label:Tr.tr("Normal"),value:0},{label:Tr.tr("Maximized"),value:1},{label:Tr.tr("Fullscreen"),value:2}]});value:entry.modelData.fullscreen??0;onEdited:v=>root.windowChange(entry.index,"fullscreen",v)}

                    }
                }
            }
            RowLayout {
                Layout.fillWidth:true
                RowButton {text:Tr.tr("Save snapshot changes");icon:"save";disabled:root.backend.busy||!!root.commandError;onClicked:root.backend.savePreview(root.form)}
                RowButton {text:Tr.tr("Restore selected");icon:"restore";disabled:root.backend.busy||!root.selected.length||!!root.commandError;onClicked:root.confirmRestore=!root.confirmRestore}
            }
            RowButton {objectName:"confirmSessionRestore";visible:root.confirmRestore;text:Tr.tr("Start selected applications now");subtext:Tr.tr("Existing applications follow your duplicate-handling settings.");icon:"play_arrow";disabled:root.backend.busy;onClicked:{root.backend.savePreview(root.form);if(!root.backend.error){root.backend.restore(root.form.id,root.selected.map(w=>w.key));root.confirmRestore=false}}}
            RowLayout {Layout.fillWidth:true;RowButton {text:Tr.tr("Export snapshot");icon:"file_save";disabled:root.backend.busy;onClicked:root.exporter.open()} RowButton {text:Tr.tr("Export .desktop starters");icon:"open_in_new";disabled:root.backend.busy;onClicked:root.portable.open()}}
            RowButton {text:Tr.tr("Delete snapshot");icon:"delete";disabled:root.backend.busy;onClicked:root.removing=root.removing?"":root.form.id}
            RowButton {visible:root.removing===root.form.id&&!!root.removing;text:Tr.tr("Confirm deletion");icon:"delete_forever";disabled:root.backend.busy;onClicked:{root.backend.remove(root.removing);root.removing="";root.form=({})}}
        }
        SettingsCard {
            title:Tr.tr("When signing in");description:Tr.tr("Choose a startup policy and keep an automatic recovery checkpoint.");icon:"login"
            GenericSettingRow {spec:({label:"On login",type:"choice",choices:[{label:Tr.tr("Do not restore"),value:"none"},{label:Tr.tr("Ask before restoring"),value:"ask"},{label:Tr.tr("Restore automatically"),value:"automatic"}]});value:root.config.startup??"ask";onEdited:v=>root.set("startup",v)}
            GenericSettingRow {spec:({label:"Startup snapshot",type:"choice",choices:[{label:Tr.tr("Latest automatic checkpoint"),value:"automatic"},...root.backend.snapshots.filter(s=>s.id!=="automatic").map(s=>({label:s.name,value:s.id}))]});value:root.config.startupSnapshot??"automatic";onEdited:v=>root.set("startupSnapshot",v)}
            ToggleRow {text:Tr.tr("Save automatic recovery checkpoints");checked:root.config.autosave??true;onToggled:v=>root.set("autosave",v)}
            GenericSettingRow {spec:({label:"Checkpoint interval (seconds)",type:"int",min:30,max:3600,step:30});value:root.config.interval??120;onEdited:v=>root.set("interval",v)}
            GenericSettingRow {spec:({label:"Maximum saved snapshots",type:"int",min:1,max:100});value:root.config.keepSnapshots??12;onEdited:v=>root.set("keepSnapshots",v)}
        }
        SettingsCard {
            title:Tr.tr("Window restoration");description:Tr.tr("Placement is available in hics / Hyprland. Other desktops can launch the saved applications.");icon:"dashboard_customize"
            ToggleRow {text:Tr.tr("Restore window mode");checked:root.config.restoreMode??true;onToggled:v=>root.set("restoreMode",v)}
            ToggleRow {text:Tr.tr("Restore monitors");checked:root.config.restoreMonitors??true;onToggled:v=>root.set("restoreMonitors",v)}
            ToggleRow {text:Tr.tr("Restore workspaces");checked:root.config.restoreWorkspaces??true;onToggled:v=>root.set("restoreWorkspaces",v)}
            ToggleRow {text:Tr.tr("Restore floating geometry");checked:root.config.restoreGeometry??true;onToggled:v=>root.set("restoreGeometry",v)}
            ToggleRow {text:Tr.tr("Restore fullscreen and maximized state");checked:root.config.restoreFullscreen??true;onToggled:v=>root.set("restoreFullscreen",v)}
            ToggleRow {text:Tr.tr("Focus the previously active window");checked:root.config.restoreFocus??true;onToggled:v=>root.set("restoreFocus",v)}
            GenericSettingRow {spec:({label:"Missing monitor",type:"choice",choices:[{label:Tr.tr("Move to an available screen"),value:"fallback"},{label:Tr.tr("Keep saved coordinates"),value:"keep"}]});value:root.config.monitorPolicy??"fallback";onEdited:v=>root.set("monitorPolicy",v)}
            ToggleRow {text:Tr.tr("Match exact window titles");subtext:Tr.tr("Useful for stable document titles. Changing titles may prevent matching.");checked:root.config.matchTitles??false;onToggled:v=>root.set("matchTitles",v)}
        }
        SettingsCard {
            title:Tr.tr("Application launch policy");description:Tr.tr("Control duplicate instances, launch pacing and applications excluded from recovery.");icon:"rocket_launch"
            ToggleRow {text:Tr.tr("Do not relaunch running applications");checked:root.config.skipRunning??true;onToggled:v=>root.set("skipRunning",v)}
            ToggleRow {text:Tr.tr("Launch separately for each saved window");subtext:Tr.tr("Single-instance applications may still reuse their existing process.");checked:root.config.launchPerWindow??false;onToggled:v=>root.set("launchPerWindow",v)}
            GenericSettingRow {spec:({label:"Delay between launches (ms)",type:"int",min:0,max:10000,step:100});value:root.config.launchDelay??500;onEdited:v=>root.set("launchDelay",v)}
            GenericSettingRow {spec:({label:"Wait for windows (seconds)",type:"int",min:2,max:120});value:root.config.windowTimeout??20;onEdited:v=>root.set("windowTimeout",v)}
            VpnTextArea {label:"Excluded applications";hint:"One application class regular expression per line.";value:root.config.excludedApps??"";onEdited:v=>root.set("excludedApps",v)}
        }
        SettingsCard {
            title:Tr.tr("GNOME, KDE and portable sessions");description:Tr.tr("Import saved application launch data and export standard .desktop starters. Internal application state depends on the application; window placement is specific to the compositor.");icon:"swap_horiz"
            RowLayout {Layout.fillWidth:true;RowButton {text:"GNOME";icon:"file_open";disabled:root.backend.busy;onClicked:root.backend.importDesktop("gnome")} RowButton {text:"KDE Plasma";icon:"file_open";disabled:root.backend.busy;onClicked:root.backend.importDesktop("kde")}}
            Repeater {model:root.desktopSessions;RowButton {required property var modelData;text:modelData.label;icon:"restore";disabled:root.backend.busy;onClicked:root.backend.importDesktop(modelData.value)}}
            RowButton {text:Tr.tr("Import hics snapshot");icon:"file_open";disabled:root.backend.busy;onClicked:root.importer.open()}
            ToggleRow {text:Tr.tr("Enable application recovery in other desktops");subtext:Tr.tr("Uses XDG autostart in GNOME and KDE. Avoid enabling another desktop's automatic app recovery at the same time.");checked:root.config.crossDesktop??false;onToggled:v=>root.set("crossDesktop",v)}
            StyledText {Layout.fillWidth:true;text:Tr.tr("Imported commands are shown in the preview and run only after you choose to restore. hics does not replace GNOME SessionManager or KDE KSMServer.");wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant;font:Tokens.font.body.small}
        }
        SettingsCard {
            visible:root.backend.report.length>0
            title:Tr.tr("Last recovery report");description:Tr.tr("Launch and placement results for each selected application.");icon:"fact_check"
            Repeater {model:root.backend.report;InfoRow {required property var modelData;Layout.fillWidth:true;label:modelData.name??modelData.application;value:Tr.tr(modelData.status??"")+" · "+Tr.tr(modelData.placement??"")}}
        }
    }
}
