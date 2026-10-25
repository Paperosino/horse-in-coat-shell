pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.Services
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.components.containers
import qs.modules.nexus
import qs.services
ColumnLayout {
 id:root
 required property PopoutState popouts
 implicitWidth:380*Tokens.scale
 spacing:Tokens.spacing.medium
 Component.onCompleted:{BackgroundOperations.openCount++;BackgroundOperations.acknowledge();}
 Component.onDestruction:BackgroundOperations.openCount=Math.max(0,BackgroundOperations.openCount-1)
 RowLayout {
  Layout.fillWidth:true
  MaterialIcon {text:"pending_actions";color:Colours.palette.m3primary}
  StyledText {text:Tr.tr("Background operations");Layout.fillWidth:true;font:Tokens.font.body.large}
  IconButton {icon:"settings";onClicked:{root.popouts.hasCurrent=false;WindowFactory.openPage("operations");}}
 }
 StyledFlickable {
  Layout.fillWidth:true
  implicitHeight:Math.min(contentHeight,400*Tokens.scale)
  contentHeight:list.implicitHeight
  clip:true;boundsBehavior:Flickable.StopAtBounds
  ScrollBar.vertical:ScrollBar {}
  ColumnLayout {
   id:list;width:parent.width;spacing:Tokens.spacing.small
   Repeater {
    model:ScriptModel {values:BackgroundOperations.rows.slice(0,12)}
    StyledRect {
     id:card
     required property var modelData
     readonly property var job:modelData.data
     Layout.fillWidth:true
     implicitHeight:details.implicitHeight+Tokens.padding.medium*2
     radius:Tokens.rounding.medium;color:Colours.palette.m3surfaceContainerHigh
     ColumnLayout {
      id:details;anchors.fill:parent;anchors.margins:Tokens.padding.medium;spacing:Tokens.spacing.small
      RowLayout {
       Layout.fillWidth:true
       MaterialIcon {text:!card.job.finished?"pending_actions":card.job.phase==="completed"?"task_alt":"error";color:card.job.error?Colours.palette.m3error:Colours.palette.m3primary}
       StyledText {Layout.fillWidth:true;text:BackgroundOperations.title(card.job);elide:Text.ElideRight}
       IconButton {visible:!card.job.finished&&card.job.cancellable;icon:"close";onClicked:DesktopJobs.cancel(card.job.id)}
       IconButton {visible:!!card.job.finished&&card.job.retryable;icon:"refresh";onClicked:DesktopJobs.retry(card.job.id)}
      }
      StyledText {Layout.fillWidth:true;visible:!!card.job.error;text:Tr.tr("The operation failed; open its details");wrapMode:Text.WordWrap;color:Colours.palette.m3error;font:Tokens.font.body.small}
      Rectangle {
       Layout.fillWidth:true;implicitHeight:4*Tokens.scale;radius:height/2;visible:!card.job.finished&&card.job.progress>=0;color:Colours.palette.m3surfaceContainerHighest
       Rectangle {height:parent.height;width:parent.width*Math.max(0,Math.min(1,card.job.progress));radius:height/2;color:Colours.palette.m3primary;Behavior on width {Anim {}}}
      }
     }
    }
   }
   StyledText {visible:!BackgroundOperations.rows.length;text:Tr.tr("No background operations");color:Colours.palette.m3onSurfaceVariant}
  }
 }
}
