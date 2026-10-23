pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.services
import qs.components.controls
import qs.modules.nexus.common

PageBase {
    pageIcon: "content_paste"
    id:root
    title:Tr.tr("Clipboard history")
    property var backend:ClipboardHistory
    property bool privacy:false
    property bool confirmWipe:false
    readonly property var config:backend.settings
    function set(key,value):void {backend.configure({[key]:value})}
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
        SettingsCard {
            title:Tr.tr("Your clipboard, organised")
            description:Tr.tr("Search copied text and images, keep useful entries and control what is remembered.")
            icon:"content_paste";badge:String(root.backend.entries.length)+" · "+Tr.tr("entries")
            ToggleRow {text:Tr.tr("Clipboard history");checked:root.config.enabled??true;onToggled:v=>root.set("enabled",v)}
            RowLayout {
                Layout.fillWidth:true
                RowButton {text:Tr.tr(root.config.paused?"Resume capture":"Pause capture");icon:root.config.paused?"play_arrow":"pause";onClicked:root.set("paused",!root.config.paused)}
                RowButton {text:Tr.tr("Clear unpinned");icon:"delete_sweep";onClicked:root.backend.clear(true)}
            }
            FeatureError {error:root.backend.error}
            StyledText {Layout.fillWidth:true;text:root.config.paused?Tr.tr("Capture is paused. Existing entries remain available."):(root.backend.capturing?Tr.tr("Watching for copied text and images"):Tr.tr("Clipboard capture is not running"));wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant;font:Tokens.font.body.small}
        }
        SettingsCard {
            title:Tr.tr("Recent and pinned")
            description:Tr.tr("Pinned entries stay available when ordinary history expires or is cleared.")
            icon:"keep"
            Repeater {
                model:root.backend.entries.slice(0,8)
                ConnectedRect {
                    id:entry
                    required property var modelData
                    Layout.fillWidth:true;first:true;last:true
                    implicitHeight:row.implicitHeight+20
                    RowLayout {
                        id:row;anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:10;spacing:12
                        Image {visible:entry.modelData.isBinary;source:entry.modelData.imagePath??"";Layout.preferredWidth:48;Layout.preferredHeight:48;fillMode:Image.PreserveAspectFit;asynchronous:true}
                        MaterialIcon {visible:!entry.modelData.isBinary;text:entry.modelData.pinned?"keep":"text_snippet";color:Colours.palette.m3primary}
                        ColumnLayout {
                            Layout.fillWidth:true;Layout.minimumWidth:0;spacing:2
                            StyledText {Layout.fillWidth:true;text:entry.modelData.text;textFormat:Text.PlainText;elide:Text.ElideRight;maximumLineCount:2;wrapMode:Text.WrapAnywhere}
                            StyledText {Layout.fillWidth:true;text:(entry.modelData.application??"")+" · "+new Date((entry.modelData.timestamp??0)*1000).toLocaleString();font:Tokens.font.label.small;color:Colours.palette.m3onSurfaceVariant;elide:Text.ElideRight}
                        }
                        IconButton {icon:entry.modelData.pinned?"keep_off":"keep";Accessible.name:Tr.tr(entry.modelData.pinned?"Unpin":"Pin");onClicked:root.backend.pin(entry.modelData.id)}
                        IconButton {icon:"content_copy";Accessible.name:Tr.tr("Copy");onClicked:root.backend.copy(entry.modelData.id)}
                        IconButton {icon:"delete";Accessible.name:Tr.tr("Delete");onClicked:root.backend.remove(entry.modelData.id)}
                    }
                }
            }
            StyledText {visible:!root.backend.entries.length;text:Tr.tr("Copy something to start your history");color:Colours.palette.m3onSurfaceVariant}
        }
        SettingsCard {
            title:Tr.tr("What to remember");description:Tr.tr("Choose content types and how much ordinary history to keep.");icon:"inventory_2"
            ColumnLayout {Layout.fillWidth:true;ToggleRow {text:Tr.tr("Text");checked:root.config.text??true;onToggled:v=>root.set("text",v)} ToggleRow {text:Tr.tr("Images");checked:root.config.images??true;onToggled:v=>root.set("images",v)}}
            GenericSettingRow {spec:({label:"Maximum history entries",type:"int",min:1,max:10000,step:50});value:root.config.maxEntries??500;onEdited:v=>root.set("maxEntries",v)}
            GenericSettingRow {spec:({label:"Maximum entry size (MiB)",type:"int",min:1,max:100});value:root.config.maxMiB??10;onEdited:v=>root.set("maxMiB",v)}
            GenericSettingRow {spec:({label:"Expire after days (0 keeps forever)",type:"int",min:0,max:3650});value:root.config.expiryDays??30;onEdited:v=>root.set("expiryDays",v)}
            ToggleRow {text:Tr.tr("Keep history between logins");subtext:Tr.tr("Disabled: new history is stored in the runtime directory. Previous disk history is kept until explicitly cleared.");checked:root.config.persistent??true;onToggled:v=>root.set("persistent",v)}
        }
        SettingsCard {
            title:Tr.tr("Privacy and exclusions");description:Tr.tr("Keep sensitive content out of the history and pause collection while locked.");icon:"shield_lock"
            ToggleRow {text:Tr.tr("Ignore content marked as secret");checked:root.config.ignoreSecrets??true;onToggled:v=>root.set("ignoreSecrets",v)}
            ToggleRow {text:Tr.tr("Pause while the screen is locked");checked:root.config.pauseWhenLocked??true;onToggled:v=>root.set("pauseWhenLocked",v)}
            ToggleRow {text:Tr.tr("Clear history when signing out");checked:root.config.clearOnLogout??false;onToggled:v=>root.set("clearOnLogout",v)}
            VpnTextArea {label:"Excluded active applications";hint:"One regular expression per line. Application attribution uses the active Hyprland window.";value:root.config.excludedApps??"";onEdited:v=>root.set("excludedApps",v)}
            VpnTextArea {label:"Excluded text patterns";hint:"One regular expression per line. Matching copied text is not stored.";value:root.config.excludedText??"";onEdited:v=>root.set("excludedText",v)}
            RowButton {text:Tr.tr("Import previous cliphist history");subtext:Tr.tr("Import obeys the current content filters and size limits.");icon:"history";disabled:root.backend.busy;onClicked:root.backend.importLegacy()}
            RowButton {text:Tr.tr("Delete all history including pins");icon:"delete_forever";onClicked:root.confirmWipe=!root.confirmWipe}
            RowButton {visible:root.confirmWipe;text:Tr.tr("Confirm deletion");icon:"delete_forever";onClicked:{root.backend.clear(false);root.confirmWipe=false}}
        }
    }
}
