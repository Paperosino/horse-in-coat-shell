pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Config
import qs.components
import qs.components.effects
import qs.services
import qs.modules.bar
import qs.modules.bar.popouts as Popouts
ShellRoot {
 id:root
 property int phase:0
 property var sizes:[0.75,1,1.25,1.5,2]
 function check(value,message){if(!value){console.error("DESIGN_FAIL",message);Qt.exit(1);}return value;}
 FloatingWindow {
  id:win;visible:true;implicitWidth:900;implicitHeight:480;color:"#202438"
  contentItem.Config.screen:screen.name;contentItem.Tokens.screen:screen.name
  Item { id:canvas; anchors.fill:parent
  ScreenState {id:state;modelData:win.screen}
  Popouts.Wrapper {id:popouts;screen:win.screen;offsetScale:0}
  BarWrapper {id:bar;width:parent.width;height:implicitHeight;screen:win.screen;screenState:state;popouts:popouts;fullscreen:false}
  ScalableIcon {
   id:icon;parent:bar.content;x:parent.width-width-10;y:(parent.height-height)/2;implicitSize:24*Tokens.scale
   source:"file://"+Quickshell.shellPath("assets/logo.svg")
  }
  ColouredIcon {id:tinted;parent:bar.content;x:icon.x-width-10;y:icon.y;implicitSize:icon.implicitSize;source:icon.source;colour:"#c4b5fd"}
  Column {
   x:24;y:100;spacing:22
   StyledText {id:sample;text:"hics · Панель 0123456789 · Scaling";color:"#eeeeff"}
   MaterialIcon {id:glyph;text:"notifications";fontStyle:Tokens.font.icon.large}
   StyledText {text:"Fractional font: "+sample.font.pointSize+" pt";color:"#eeeeff"}
   StyledText {text:"Icon texture: "+icon.backer.sourceSize.width+" · panel scale "+bar.panelScale;color:"#eeeeff"}
  }
  }
 }
 Timer {
  interval:350;running:true;repeat:true
  onTriggered:{
   if(root.phase%2===0){
    const index=root.phase/2;
    if(index>=root.sizes.length){console.log("SETTINGS_DESIGN_OK");Qt.quit();return;}
    GlobalConfig.appearance.scale=root.sizes[index];GlobalConfig.bar.height=0;GlobalConfig.bar.scale=Math.min(1.5,root.sizes[index]);
   }else{
    const expected=GlobalConfig.appearance.font.body.small.size*GlobalConfig.appearance.scale;
    if(!root.check(Math.abs(sample.font.pointSize-expected)<.001,"fractional font size was rounded"))return;
    if(!root.check(sample.renderType===Text.QtRendering&&sample.antialiasing,"scalable antialiased rendering missing"))return;
    if(!root.check(Math.abs(glyph.font.pointSize-Tokens.font.icon.large.pointSize)<.001,"icon font lost fractional size"))return;
    if(!root.check(icon.backer.sourceSize.width>=Math.ceil(icon.actualSize*Math.max(1,bar.panelScale)),"panel icon texture undersampled"))return;
    if(!root.check(tinted.layer.textureSize.width>=tinted.width*bar.panelScale,"recolour layer texture undersampled"))return;
    if(!root.check(icon.status===Image.Ready,"scaling probe icon did not load"))return;
    if(!root.check(icon.mipmap,"icon downsampling has no mipmap"))return;
    const filename="/tmp/hics-scaling-"+root.sizes[Math.floor(root.phase/2)]+".png";
    canvas.grabToImage(result=>root.check(result.saveToFile(filename),"scaling snapshot failed"));
   }
   root.phase++;
  }
 }
}
