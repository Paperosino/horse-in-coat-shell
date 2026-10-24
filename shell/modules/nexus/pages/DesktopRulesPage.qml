pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common
PageBase {
 id:root
 property bool devicesOnly:false
 title:Tr.tr(devicesOnly?"Individual input devices":"Application rules")
 pageIcon:devicesOnly?"devices":"rule"
 property var form:({})
 property string deviceName:""
 property string deviceKind:""
 property var deviceValues:({})
 function change(key,value):void {
  const next=Object.assign({},form,{[key]:value});
  if(key==="x"||key==="y"){const other=key==="x"?"y":"x";if(next[other]===undefined)next[other]=0;next.floating=true;}
  if(key==="width"||key==="height"){const other=key==="width"?"height":"width";if(next[other]===undefined)next[other]=other==="width"?800:600;next.floating=true;}
  form=next;
 }
 function optional(key,value):void {const next=Object.assign({},form);if(value===null)delete next[key];else next[key]=value;form=next;}
 function pickDevice(d):void {deviceName=d.name;deviceKind=d.kind;deviceValues=Object.assign({},DesktopRules.data.deviceRules.find(r=>r.name===d.name)?.values??{});}
 Component.onCompleted:DesktopRules.refresh()
 ColumnLayout {
  width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
  FeatureError {error:DesktopRules.error}
  SettingsCard {
   title:Tr.tr(root.devicesOnly?"A different feel for each device":"Choose a window to build a rule")
   description:Tr.tr(root.devicesOnly?"Device overrides follow the device name. Reset an individual value to inherit the global setting again.":"Rules match the application rather than its temporary window address. Placement rules apply to new windows; dynamic effects also update matching windows.")
   icon:root.pageIcon
   RowButton {text:Tr.tr("Refresh connected devices and windows");icon:"refresh";onClicked:DesktopRules.refresh()}
   Repeater {
    model:root.devicesOnly?DesktopRules.data.devices:DesktopRules.data.windows
    RowButton {
     required property var modelData
     text:root.devicesOnly?modelData.name:modelData.application
     subtext:root.devicesOnly?modelData.kind:modelData.title
     icon:root.devicesOnly?"devices":"window"
     onClicked:{if(root.devicesOnly)root.pickDevice(modelData);else root.form={name:modelData.application,application:modelData.application,title:"",enabled:true,regex:false};}
    }
   }
  }
  SettingsCard {
   visible:!root.devicesOnly;title:Tr.tr("Saved application rules");icon:"rule"
   Repeater {model:DesktopRules.data.rules;RowButton {required property var modelData;text:modelData.name||modelData.application;subtext:modelData.application+(modelData.enabled===false?" · "+Tr.tr("Disabled"):"");icon:"rule";onClicked:root.form=JSON.parse(JSON.stringify(modelData))}}
   RowButton {text:Tr.tr("Create a rule manually");icon:"add";onClicked:root.form={name:"",application:"",enabled:true,regex:false}}
  }
  SettingsCard {
   visible:!root.devicesOnly&&Object.keys(root.form).length>0;title:Tr.tr("Rule details");icon:"tune"
   TextFieldRow {label:Tr.tr("Rule name");value:root.form.name??"";onValueEdited:v=>root.change("name",v)}
   TextFieldRow {label:Tr.tr("Application class");value:root.form.application??"";onValueEdited:v=>root.change("application",v)}
   TextFieldRow {label:Tr.tr("Window title (optional)");value:root.form.title??"";onValueEdited:v=>root.change("title",v)}
   ToggleRow {text:Tr.tr("Rule enabled");checked:root.form.enabled!==false;onToggled:root.change("enabled",checked)}
   ToggleRow {text:Tr.tr("Match using regular expressions");checked:root.form.regex??false;onToggled:root.change("regex",checked)}
   GenericSettingRow {spec:({label:"Window placement",type:"choice",choices:[{value:"default",label:"Follow the desktop mode"},{value:"float",label:"Floating"},{value:"tile",label:"Tiled"}],value:root.form.floating===undefined?"default":root.form.floating?"float":"tile"});onEdited:v=>root.optional("floating",v==="default"?null:v==="float")}
   GenericSettingRow {spec:({label:"Monitor",type:"choice",choices:["",...Monitors.monitors.map(m=>m.name)],value:root.form.monitor??""});onEdited:v=>root.change("monitor",v)}
   StepperRow {label:Tr.tr("Workspace (0 follows defaults)");from:0;to:1000000;value:root.form.workspace??0;onMoved:v=>root.optional("workspace",v?v:null)}
   ToggleRow {text:Tr.tr("Start fullscreen");checked:root.form.fullscreen??false;onToggled:root.change("fullscreen",checked)}
   ToggleRow {text:Tr.tr("Center floating windows");checked:root.form.center??false;onToggled:root.change("center",checked)}
   ToggleRow {text:Tr.tr("Show on every workspace");checked:root.form.pin??false;onToggled:root.change("pin",checked)}
   GenericSettingRow {spec:({label:"Prevent idle sleep",type:"choice",choices:["none","focus","fullscreen","always"],value:root.form.idleInhibit??"none"});onEdited:v=>root.change("idleInhibit",v)}
   SliderRow {label:Tr.tr("Window opacity");value:root.form.opacity??1;valueLabel:Math.round((root.form.opacity??1)*100)+"%";onMoved:v=>root.change("opacity",Math.max(.1,v))}
   SettingsCard {
    title:Tr.tr("Initial floating geometry");icon:"aspect_ratio";collapsible:true;expanded:false
    GridLayout {
     Layout.fillWidth:true;columns:width>450*Tokens.scale?2:1
     Repeater {model:[{key:"x",label:"X position",min:-100000,max:100000,value:0},{key:"y",label:"Y position",min:-100000,max:100000,value:0},{key:"width",label:"Window width",min:100,max:16384,value:800},{key:"height",label:"Window height",min:80,max:16384,value:600}];StepperRow {required property var modelData;label:Tr.tr(modelData.label);from:modelData.min;to:modelData.max;value:root.form[modelData.key]??modelData.value;onMoved:v=>root.change(modelData.key,v)}}
    }
   }
   RowButton {text:Tr.tr("Save application rule");icon:"save";disabled:DesktopRules.busy||!root.form.application;onClicked:DesktopRules.call("save-rule",root.form)}
   RowButton {visible:!!root.form.id;text:Tr.tr("Delete application rule");icon:"delete";disabled:DesktopRules.busy;onClicked:{DesktopRules.call("delete-rule",{id:root.form.id});root.form={};}}
  }
  SettingsCard {
   visible:root.devicesOnly&&!!root.deviceName;title:root.deviceName;icon:root.deviceKind==="keyboards"?"keyboard":"mouse"
   Repeater {
    model:(root.deviceKind==="keyboards"?[{key:"kb_layout",label:"Keyboard layouts (comma separated)",type:"string"},{key:"kb_variant",label:"Keyboard variants",type:"string"},{key:"kb_options",label:"Keyboard options",type:"string"},{key:"repeat_rate",label:"Repeat rate",type:"int",min:1,max:100},{key:"repeat_delay",label:"Repeat delay",type:"int",min:100,max:2000}]:[{key:"sensitivity",label:"Pointer sensitivity",type:"slider",min:-1,max:1},{key:"accel_profile",label:"Pointer acceleration",type:"choice",choices:["","flat","adaptive"]},{key:"left_handed",label:"Left handed",type:"bool"},{key:"natural_scroll",label:"Natural scrolling",type:"bool"},{key:"scroll_factor",label:"Scroll speed",type:"slider",min:.1,max:10},...(/touchpad|trackpad|synaptics|elan/i.test(root.deviceName)?[{key:"tap-to-click",label:"Tap to click",type:"bool"},{key:"disable_while_typing",label:"Disable while typing",type:"bool"}]:[])])
    GenericSettingRow {
     required property var modelData
     spec:Object.assign({},modelData,{value:root.deviceValues[modelData.key]??(modelData.type==="bool"?false:modelData.type==="string"||modelData.type==="choice"?"":modelData.key==="repeat_rate"?25:modelData.key==="repeat_delay"?600:modelData.key==="sensitivity"?0:1),step:.01,overridden:root.deviceValues[modelData.key]!==undefined})
     resettable:true
     onEdited:v=>root.deviceValues=Object.assign({},root.deviceValues,{[modelData.key]:v})
     onResetRequested:{const next=Object.assign({},root.deviceValues);delete next[modelData.key];root.deviceValues=next;}
    }
   }
   RowButton {text:Tr.tr("Save device overrides");icon:"save";disabled:DesktopRules.busy;onClicked:DesktopRules.call("save-device",{name:root.deviceName,values:root.deviceValues})}
   RowButton {text:Tr.tr("Use global settings for this device");icon:"restart_alt";onClicked:{root.deviceValues={};DesktopRules.call("save-device",{name:root.deviceName,values:{}});}}
  }
 }
}
