pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus.common
PageBase {
 id:root;title:Tr.tr("First steps");pageIcon:"explore"
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
  SettingsCard {
   title:Tr.tr("Find your way around hics");description:Tr.tr("Replay the introduction, revisit initial setup or jump to a particular topic. Skipping never prevents you from using the desktop.");icon:"explore"
   RowButton {text:Tr.tr("Start the introduction");icon:"play_arrow";onClicked:Onboarding.open()}
   RowButton {text:Tr.tr("Resume from the last step");icon:"play_arrow";onClicked:Onboarding.open(Onboarding.data.settings.step??0)}
   ToggleRow {text:Tr.tr("Show setup on the next launch");checked:Onboarding.data.settings.autoShow??false;onToggled:Onboarding.configure({autoShow:checked})}
   ToggleRow {text:Tr.tr("Play recorded demonstrations");checked:Onboarding.data.settings.showDemos??true;onToggled:Onboarding.configure({showDemos:checked})}
   ToggleRow {text:Tr.tr("Reduce interface motion");checked:GlobalConfig.appearance.reducedMotion;onToggled:GlobalConfig.appearance.reducedMotion=checked}
  }
  SettingsCard {
   title:Tr.tr("Explore a topic");icon:"school"
   Repeater {model:Onboarding.steps;RowButton {required property var modelData;required property int index;text:modelData.title;subtext:modelData.description;icon:modelData.icon;onClicked:Onboarding.open(index)}}
  }
 }
}
