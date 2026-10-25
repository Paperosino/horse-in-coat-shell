pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.utils
import qs.modules.nexus.common
PageBase {
    id:root
    title:Tr.tr("File manager integration")
    pageIcon:"folder_open"
    property var state:({})
    property DesktopBackend backend:DesktopBackend {}
    property FileDialog archivePicker:FileDialog {nameFilters:[Tr.tr("Archives")+" (*.zip *.tar *.gz *.bz2 *.xz *.7z *.rar *.zst *.iso)",Tr.tr("All files")+" (*)"];title:Tr.tr("Open an archive");onAccepted:root.backend.call("integration.open",{target:"archive",path:Paths.toLocalFile(selectedFile)})}
    property FileDialog revealPicker:FileDialog {title:Tr.tr("Show a file in its folder");onAccepted:root.backend.call("integration.reveal",{path:Paths.toLocalFile(selectedFile)})}
    function refresh():void {backend.call("integration.status",{},value=>root.state=value);}
    function prefer(kind,id):void {backend.call("integration.prefer",{kind,id},value=>{if(!value.error)root.refresh();});}
    Component.onCompleted:refresh()
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
        SettingsCard {
            title:Tr.tr("Your familiar file manager");icon:"folder_open"
            description:Tr.tr("hics uses installed file managers and their standard desktop integration. File operations remain in the application you choose.")
            RowButton {text:Tr.tr("Refresh installed applications");icon:"refresh";disabled:root.backend.busy;onClicked:root.refresh()}
            Repeater {
                model:root.state.managers??[]
                RowButton {required property var modelData;text:modelData.name;subtext:modelData.selected?Tr.tr("Default file manager"):Tr.tr("Use for folders");icon:modelData.selected?"check_circle":"folder";disabled:root.backend.busy;onClicked:root.prefer("manager",modelData.id)}
            }
            InfoRow {visible:!(root.state.managers??[]).length;label:Tr.tr("No file manager found");value:Tr.tr("Install Nautilus, Dolphin, Thunar, Nemo, PCManFM or Caja with your package manager.")}
            RowButton {text:Tr.tr("Open home folder");icon:"home";onClicked:root.backend.call("integration.open",{target:"home"})}
            RowButton {text:Tr.tr("Open downloads");icon:"download";onClicked:root.backend.call("integration.open",{target:"downloads"})}
            RowButton {text:Tr.tr("Open trash");icon:"delete";onClicked:root.backend.call("integration.open",{target:"trash"})}
            RowButton {text:Tr.tr("Show a file in its folder");icon:"find_in_page";onClicked:root.revealPicker.open()}
        }
        SettingsCard {
            title:Tr.tr("Archive applications");icon:"folder_zip"
            description:Tr.tr("Choose an installed archive manager. Creation, extraction and encrypted archives are handled by that application, not by the shell.")
            Repeater {
                model:root.state.archivers??[]
                RowButton {required property var modelData;text:modelData.name;subtext:modelData.selected?Tr.tr("Default archive manager"):Tr.tr("Use for archive formats");icon:modelData.selected?"check_circle":"folder_zip";disabled:root.backend.busy;onClicked:root.prefer("archiver",modelData.id)}
            }
            InfoRow {visible:!(root.state.archivers??[]).length;label:Tr.tr("No archive manager found");value:Tr.tr("Install File Roller, Ark, Xarchiver or Engrampa with your package manager.")}
            RowButton {text:Tr.tr("Open an archive");icon:"open_in_new";onClicked:root.archivePicker.open()}
        }
        SettingsCard {
            ToggleRow {text:Tr.tr("Show integrated actions in the application menu");checked:GlobalConfig.utilities.comfort.launcherActions;onToggled:GlobalConfig.utilities.comfort.launcherActions=checked}
            title:Tr.tr("Restore application defaults");icon:"undo";collapsible:true;expanded:false
            description:Tr.tr("Restore the previous associations only if they have not been changed by another application since.")
            RowButton {text:Tr.tr("Undo the last default application change");icon:"undo";disabled:!root.state.canUndo||root.backend.busy;onClicked:root.backend.call("integration.undo",{},value=>{if(!value.error)root.refresh();})}
        }
        FeatureError {error:root.backend.error}
    }
}
