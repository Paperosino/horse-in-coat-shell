pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.utils
import qs.modules.nexus.common
PageBase {
 id:root;title:Tr.tr("Desktop health");pageIcon:"monitor_heart"
 property var report:({checks:[],units:[]})
 property bool logs:false
 readonly property FeatureBackend backend:FeatureBackend {helper:"desktop_diagnostics.py"}
 readonly property FileDialog exporter:FileDialog {fileMode:FileDialog.SaveFile;defaultSuffix:"json";nameFilters:["hics report (*.json)"];onAccepted:root.backend.call(["export"],{path:Paths.toLocalFile(selectedFile),logs:root.logs},root.accept)}
 function accept(data:var):void {if(!data.error)report=data;}
 Component.onCompleted:backend.call(["status"],null,accept)
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
  FeatureError {error:root.backend.error}
  SettingsCard {
   title:Tr.tr("See what needs attention");description:Tr.tr("Inspect desktop components and prepare a local issue report. Reports are never sent automatically; logs are optional and private paths are redacted.");icon:"monitor_heart"
   RowButton {text:Tr.tr("Run checks");icon:"refresh";disabled:root.backend.busy;onClicked:root.backend.call(["report"],{logs:root.logs},root.accept)}
   ToggleRow {text:Tr.tr("Include recent service logs");checked:root.logs;onToggled:root.logs=checked}
   RowButton {text:Tr.tr("Save diagnostic report");icon:"file_save";disabled:root.backend.busy;onClicked:root.exporter.open()}
  }
  SettingsCard {
   title:Tr.tr("Installation checks");icon:"fact_check"
   Repeater {model:root.report.checks??[];InfoRow {required property var modelData;label:(modelData.ok?"✓ ":"! ")+Tr.tr(modelData.check);value:modelData.value??""}}
   InfoRow {visible:!!root.report.hyprlandErrors;label:Tr.tr("Compositor configuration");value:root.report.hyprlandErrors??""}
  }
  SettingsCard {
   title:Tr.tr("Desktop services");icon:"settings_suggest"
   Repeater {model:root.report.units??[];RowButton {required property var modelData;text:modelData.id;subtext:(modelData.ActiveState??"unknown")+" · "+(modelData.SubState??"")+" · "+(modelData.Result??"");icon:"restart_alt";disabled:root.backend.busy;onClicked:root.backend.call(["restart"],{unit:modelData.id,logs:root.logs},root.accept)}}
  }
  SettingsCard {
   visible:root.logs&&!!root.report.logs;title:Tr.tr("Recent logs");icon:"article";collapsible:true;expanded:false
   StyledText {Layout.fillWidth:true;text:root.report.logs??"";textFormat:Text.PlainText;wrapMode:Text.WrapAnywhere;font:Tokens.font.body.small}
  }
 }
}
