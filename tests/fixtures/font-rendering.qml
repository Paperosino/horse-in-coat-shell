import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import qs.components
import qs.components.controls
import qs.modules.nexus
import qs.modules.nexus.pages
import qs.services
ShellRoot {
 id: root
 property int phase: 0
 property var modes: ["none", "slight", "medium", "full"]
 FloatingWindow {
  visible: true; implicitWidth: 1000; implicitHeight: 850; color: Colours.palette.m3surface
  Nexus { id: settings; visible:false }
  ShellStylePage { id: page; anchors.fill: parent; nState: settings.nState }
  MaterialIcon { id: glyph; text:"mic"; x:10; y:10; fontStyle:Tokens.font.icon.large }
  StyledText { id: probe; visible:false; text:"Abc" }
  TextFieldBase { id: field; visible:false }
 }
 function named(item,name){if(item.objectName===name)return item;for(const child of item.children??[]){const found=named(child,name);if(found)return found;}return null;}
 function check(value,msg){if(!value){console.error("FONT_FAIL",msg);Qt.exit(1);return false;}return true;}
 Component.onCompleted: { FontRendering.backendCommand = ["/usr/bin/true"]; settings.nState.isWindow = true; settings.nState.screen = Quickshell.screens[0]; }
 Timer {
  interval:700;repeat:true;running:true
  onTriggered:{
   if(root.phase>0){
    const previous=root.phase-1;
    const aa=previous<4;
    const hint=root.modes[previous%4];
    if(!root.check(probe.antialiasing===aa && probe.renderType===(aa&&hint==="none"?Text.QtRendering:Text.NativeRendering),"text policy"))return;
    if(!root.check(field.renderType===probe.renderType,"input policy"))return;
    if(!root.check(glyph.renderType===Text.QtRendering && glyph.antialiasing && glyph.font.hintingPreference===Font.PreferNoHinting,"icons must ignore text rendering preferences"))return;
    glyph.grabToImage(result=>result.saveToFile("/tmp/hics-icon-policy-"+previous+".png"));
    const expected=hint==="none"?Font.PreferNoHinting:hint==="slight"?Font.PreferVerticalHinting:hint==="full"?Font.PreferFullHinting:Font.PreferDefaultHinting;
    if(!root.check(probe.font.hintingPreference===expected && Tokens.font.body.builders.medium.build().hintingPreference===expected,"font token propagation"))return;
    if(!root.check(!FontRendering.busy&&!FontRendering.error,"apply completion"))return;
   }
   if(root.phase===8){root.phase++;glyph.grabToImage(result=>{result.saveToFile("/tmp/hics-icon-policy-7.png");console.log("SETTINGS_DESIGN_OK FONT_RENDERING_OK");Qt.quit();});return;}
   const toggle=root.named(page,"fontAntialias");const select=root.named(page,"fontHinting");
   if(!root.check(!!toggle&&!!select,"appearance controls missing"))return;
   GlobalConfig.appearance.font.antialias=root.phase<4;
   select.selected(select.menuItems[root.phase%4]);
   if(!root.check(select.active.value===root.modes[root.phase%4],"selected hinting item"))return;
   page.grabToImage(result=>result.saveToFile("/tmp/hics-font-rendering-"+root.phase+".png"));
   root.phase++;
  }
 }
}
