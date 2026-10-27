import QtQuick
import QtQuick.Effects
import Quickshell
ShellRoot {
 id:root
 property int index:0
 property int phase:0
 property int settled:0
 property string directory:EVIDENCE_DIRECTORY
 FloatingWindow {
  id:win
  visible:true
  implicitWidth:480
  implicitHeight:320
  Rectangle {
   id:scene
   anchors.fill:parent
   color:"#1d1d2e"
   RectangularShadow {
    id:shadow
    x:120;y:90;width:220;height:130
    color:root.index%2?"#804a258a":"#a0000000"
    blur:root.index%3===0?0:root.index%3===1?16:32
    radius:root.index%3===0?0:24
    spread:root.index%2?4:0
    cached:root.index>=3
    offset:Qt.vector2d(0,8)
   }
   Rectangle {x:120;y:90;width:220;height:130;radius:shadow.radius;color:"#cab0fa"}
  }
 }
 Timer {
  interval:200;repeat:true;running:true
  onTriggered:{
   if(root.index>=CYCLES){console.log("PROFILE_COMPLETE",root.index);Qt.quit();return;}
   if(root.phase===0){if(++root.settled<3)return;root.phase=1;
    if(!scene.grabToImage(result=>{
     if(!result.saveToFile(root.directory+"/shadow-"+root.index+".png")){console.error("PROFILE_FAIL save");Qt.exit(1);return;}
     console.log("PROFILE_CYCLE",++root.index);root.phase=0;root.settled=0;
    })){root.phase=0;root.settled=0;}
   }
  }
 }
}
