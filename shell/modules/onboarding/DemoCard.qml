pragma ComponentBehavior: Bound
import QtQuick
import QtMultimedia
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.components.controls
import qs.services
StyledRect {
 id:root
 objectName:"onboarding-demo"
 readonly property string playbackError:player.error
 function renderedFrames():real {return player.frames();}
 required property string demoId
 property bool playing:true
 readonly property bool animate:visible&&playing&&!PerformancePolicy.locked&&(Onboarding.data.settings.showDemos??true)&&!GlobalConfig.appearance.reducedMotion
 radius:Tokens.rounding.large
 color:Colours.palette.m3surfaceContainerHighest
 activeFocusOnTab:true
 Keys.onSpacePressed:Onboarding.configure({showDemos:!(Onboarding.data.settings.showDemos??true)})
 Keys.onReturnPressed:Onboarding.configure({showDemos:!(Onboarding.data.settings.showDemos??true)})
 border.width:activeFocus?2:1
 border.color:Colours.palette.m3outlineVariant
 clip:true
 Image {anchors.fill:parent;source:root.visible?Onboarding.poster(root.demoId):"";asynchronous:true;cache:false;fillMode:Image.PreserveAspectFit}
 VideoOutput {id:video;anchors.fill:parent;anchors.margins:1;fillMode:VideoOutput.PreserveAspectFit}
 WallpaperPlayer {id:player;source:root.visible?Onboarding.video(root.demoId):"";videoSink:video.videoSink;muted:true;volume:0;paused:!root.animate}
 AnimatedImage {anchors.fill:parent;visible:!!player.error;source:visible?Onboarding.demo(root.demoId):"";asynchronous:true;cache:false;fillMode:Image.PreserveAspectFit;playing:root.animate}
 Rectangle {
  anchors.right:parent.right;anchors.top:parent.top;anchors.margins:8*Tokens.scale
  width:status.implicitWidth+16*Tokens.scale;height:status.implicitHeight+8*Tokens.scale;radius:height/2
  color:Colours.palette.m3surfaceContainerHigh
  MaterialIcon {id:status;anchors.centerIn:parent;text:root.animate?"pause":"play_arrow";color:Colours.palette.m3onSurface;fontStyle:Tokens.font.icon.small}
 }
 TapHandler {onTapped:Onboarding.configure({showDemos:!(Onboarding.data.settings.showDemos??true)})}
 Accessible.role:Accessible.Button
 Accessible.name:Tr.tr("Play demonstrations")
 Accessible.onPressAction:Onboarding.configure({showDemos:!(Onboarding.data.settings.showDemos??true)})
}
