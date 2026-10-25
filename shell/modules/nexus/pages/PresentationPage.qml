pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus.common
PageBase {
 id:root
 title:Tr.tr("Presentation mode");pageIcon:"present_to_all"
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
  SettingsCard {
   title:Tr.tr("Present without interruptions");icon:"present_to_all"
   description:Tr.tr("Keeps the session awake and suppresses new notification popups. Your usual idle and notification preferences are restored by ending this temporary mode.")
   StepperRow {label:Tr.tr("Duration in minutes");from:1;to:480;stepSize:5;value:Presentation.durationMinutes;onMoved:value=>Presentation.durationMinutes=value}
   ToggleRow {text:Tr.tr("Hide personal content and previews");checked:Presentation.hidePrivateContent;onToggled:Presentation.hidePrivateContent=checked}
   ToggleRow {text:Tr.tr("Hide notification popups");checked:Presentation.hideNotifications;onToggled:Presentation.hideNotifications=checked}
   InfoRow {label:Tr.tr("Screen sharing");value:Tr.tr("The selected screen identifies your presentation. Choose the actual screen or window in the sharing application's portal dialog.")}
   Repeater {model:Quickshell.screens;RowButton {required property var modelData;text:modelData.name;subtext:Tr.tr("Start presentation on this screen");icon:"monitor";onClicked:Presentation.begin(modelData.name)}}
   RowButton {visible:Presentation.active;text:Tr.tr("End presentation");icon:"stop_circle";onClicked:Presentation.end()}
  }
 }
}
