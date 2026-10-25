pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import qs.utils
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.services
import qs.modules.nexus.common
PageBase {
 id:root
 pageIcon:"pending_actions"
 title:Tr.tr("Background operations")
 pageDescription:Tr.tr("Progress and results remain available when settings are closed")
 property bool showFinished:true
 property var copySources:[]
 property string copyTarget:""
 property DesktopBackend transferBackend:DesktopBackend{}
 property FileDialog copyPicker:FileDialog {fileMode:FileDialog.OpenFiles;onAccepted:root.copySources=selectedFiles.map(file=>Paths.toLocalFile(file))}
 property FolderDialog targetPicker:FolderDialog {onAccepted:root.copyTarget=Paths.toLocalFile(selectedFolder)}

 readonly property var operationNames: ({"diagnostics.check":Tr.tr("Desktop checks"),"backup.run":Tr.tr("Personal file backup"),"backup.init":Tr.tr("Create backup repository"),"backup.restore":Tr.tr("Restore files"),"backup.check":Tr.tr("Check backup integrity"),"backup.snapshots":Tr.tr("Read backup snapshots"),"backup.files":Tr.tr("Browse backup files"),"maintenance.disk":Tr.tr("Disk maintenance"),"transfer.copy":Tr.tr("Copy files"),"transfer.send":Tr.tr("Send files"),"update.install":Tr.tr("System update"),"maintenance.cleanup":Tr.tr("Disk cleanup"),"backup.configure":Tr.tr("Save backup preferences"),"search.index":Tr.tr("Index documents"),"search.clear":Tr.tr("Erase document index"),"search.configure":Tr.tr("Save search preferences"),"apps.remove":Tr.tr("Remove application"),"apps.apparmor-mode":Tr.tr("Change AppArmor profile"),"apps.flatpak-override":Tr.tr("Change application permissions"),"apps.flatpak-reset":Tr.tr("Reset application permissions"),"apps.autostart":Tr.tr("Change application autostart"),"keyring.authorize":Tr.tr("Authorize vault management"),"keyring.lock":Tr.tr("Lock vault"),"keyring.unlock":Tr.tr("Unlock vault")})
 function phaseName(phase:string):string {return ({queued:Tr.tr("Queued"),running:Tr.tr("Working"),authorizing:Tr.tr("Waiting for authorization"),completed:Tr.tr("Completed"),failed:Tr.tr("Failed"),cancelled:Tr.tr("Cancelled"),interrupted:Tr.tr("Interrupted")})[phase]??Tr.tr("Background operation");}

 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("Operations centre");icon:"pending_actions"
   InfoRow {first:true;last:true;label:Tr.tr("Service");value:DesktopJobs.available?Tr.tr("Ready"):Tr.tr("Desktop operations service is unavailable")}
   ToggleRow {text:Tr.tr("Automatically show the panel widget");checked:GlobalConfig.utilities.operations.autoShow;onToggled:GlobalConfig.utilities.operations.autoShow=checked}
   ToggleRow {text:Tr.tr("Keep failed operations visible until reviewed");checked:GlobalConfig.utilities.operations.retainErrors;onToggled:GlobalConfig.utilities.operations.retainErrors=checked}
   ToggleRow {text:Tr.tr("Show progress on the panel");checked:GlobalConfig.utilities.operations.showProgress;onToggled:GlobalConfig.utilities.operations.showProgress=checked}
   StepperRow {label:Tr.tr("Completed operation visibility (seconds)");from:1;to:300;stepSize:1;value:GlobalConfig.utilities.operations.completedSeconds;onMoved:value=>GlobalConfig.utilities.operations.completedSeconds=value}
   ToggleRow {text:Tr.tr("Detect applications that stop responding");checked:GlobalConfig.utilities.operations.watchUnresponsive;onToggled:GlobalConfig.utilities.operations.watchUnresponsive=checked}
   StepperRow {label:Tr.tr("Missed response checks before showing recovery");from:1;to:20;stepSize:1;value:GlobalConfig.utilities.operations.unresponsiveMissedPings;onMoved:value=>GlobalConfig.utilities.operations.unresponsiveMissedPings=value}
   InfoRow {label:Tr.tr("Application recovery");value:Tr.tr("Hyprland checks native Wayland and X11 applications and offers Wait or Force quit using its themed recovery dialog. Force quit can discard unsaved changes.")}
   ToggleRow {first:true;last:true;text:Tr.tr("Show completed operations");checked:root.showFinished;onToggled:root.showFinished=checked}
  }
  SettingsCard {
   title:Tr.tr("File transfer");icon:"file_copy";collapsible:true;expanded:false
   RowButton {text:Tr.tr("Choose files to copy");subtext:root.copySources.join(", ");icon:"file_open";onClicked:root.copyPicker.open()}
   RowButton {text:Tr.tr("Choose destination folder");subtext:root.copyTarget;icon:"folder_open";onClicked:root.targetPicker.open()}
   RowButton {text:Tr.tr("Copy files");subtext:Tr.tr("Existing files are never overwritten. Cancel stops the current file; files already copied are kept.");icon:"file_copy";disabled:!root.copySources.length||!root.copyTarget||root.transferBackend.busy;onClicked:root.transferBackend.call("transfer.copy",{sources:root.copySources,target:root.copyTarget})}
   FeatureError {error:root.transferBackend.error}
  }
  Repeater {
   model:ScriptModel {values:BackgroundOperations.rows.filter(row=>root.showFinished||!row.data.finished)}
   SettingsCard {
    id:operationCard
    required property var modelData
    readonly property var job:modelData.data
    property bool detailsShown:false
    property var resultData:({})
    property string resultError:""
    title:root.operationNames[job.operation]??Tr.tr("Background operation")
    icon:job.phase==="failed"?"error":job.phase==="completed"?"task_alt":"pending_actions"
    badge:root.phaseName(job.phase)
    InfoRow {first:true;last:true;label:Tr.tr("Status");value:job.error?Tr.tr(job.error):root.phaseName(job.phase)}
    Rectangle {Layout.fillWidth:true;implicitHeight:6*Tokens.scale;radius:height/2;color:Colours.palette.m3surfaceContainerHighest;visible:!job.finished&&job.progress>=0;Rectangle {height:parent.height;width:parent.width*Math.max(0,Math.min(1,job.progress));radius:height/2;color:Colours.palette.m3primary}}
    RowButton {visible:job.cancellable&&!job.finished;text:Tr.tr("Cancel operation");icon:"close";onClicked:DesktopJobs.cancel(job.id)}
    RowButton {visible:job.finished>0;text:Tr.tr("View result");icon:"article";onClicked:DesktopJobs.details(job.id,value=>{operationCard.detailsShown=true;operationCard.resultData=value.result??{};operationCard.resultError=value.error??"";},operationCard)}
    FeatureError {error:operationCard.resultError}
    InfoRow {visible:operationCard.detailsShown;label:Tr.tr("Result");value:operationCard.resultError?Tr.tr("Failed"):root.phaseName(job.phase)}
    Repeater {model:operationCard.detailsShown?[{key:"count",label:"Indexed files"},{key:"reused",label:"Unchanged files reused"},{key:"files",label:"Copied files"},{key:"bytes",label:"Transferred bytes"},{key:"limited",label:"Configured limit reached"}].filter(field=>operationCard.resultData[field.key]!==undefined):[];InfoRow {required property var modelData;label:Tr.tr(modelData.label);value:String(operationCard.resultData[modelData.key])}}

    RowButton {visible:job.retryable&&job.finished>0;text:Tr.tr("Retry");icon:"refresh";onClicked:DesktopJobs.retry(job.id)}
   }
  }
 }
}
