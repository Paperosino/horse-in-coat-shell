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
 property bool tabletsOnly:false
 title:tabletsOnly?Tr.tr("Graphics tablets & pens"):Tr.tr(devicesOnly?"Individual input devices":"Application rules")
 pageIcon:devicesOnly?"devices":"rule"
 property var form:({})
 property var selectedWindow:null
 readonly property var openApplications:{
  const rows=[];
  for(const win of DesktopRules.data.windows??[]){if(win.application&&!rows.some(row=>row.value===win.application))rows.push({value:win.application,label:win.application});}
  return rows;
 }
 function pickApplication(application):void {
  root.selectedWindow=null;root.matchScope="application";
  const next=Object.assign({},form,{name:form.name||application,application,title:"",initialTitle:"",regex:false,enabled:form.enabled!==false,mode:form.mode||LayoutModes.mode||"all"});
  delete next.matchModal;delete next.matchXwayland;form=next;
 }
 function setScope(scope):void {
  root.matchScope=scope;
  const next=Object.assign({},form,{title:scope==="title"?(selectedWindow?.title??""):"",initialTitle:scope==="initial"?(selectedWindow?.initialTitle??""):"",regex:false});
  delete next.matchModal;form=next;
 }
 function pickWindow(window):void {
  if(!window)return;
  selectedWindow=window;
  const title=window.title??"";
  root.matchScope="application";
  const pip=/^picture[- ]in[- ]picture$/i.test(title)||title==="Картинка в картинке";
  root.matchScope=pip?"title":"application";
  const next=Object.assign({},form,{name:form.name||window.application,application:window.application,title:pip?title:"",initialTitle:"",regex:false,enabled:form.enabled!==false,mode:form.mode||LayoutModes.mode||"all"});
  delete next.matchModal;delete next.matchXwayland;form=next;
 }
 property var controls: DesktopRules.data.controls ?? ({side:"right",order:["minimize","maximize","close"]})
 function control(key,value):void { controls=Object.assign({},controls,{[key]:value}); }
 function toggleControl(name,enabled):void {
  const order=controls.order.filter(v=>v!==name);if(enabled)order.push(name);control("order",order);
 }
 function exactPattern(value):string {
  let pattern="^";
  for(const ch of value){if("\\^$.*+?()[]{}|".includes(ch))pattern+="\\";pattern+=ch;}
  return pattern+"$";
 }
 function preset(kind):void {
  if(kind==="pip")form=Object.assign({},form,{application:form.regex?form.application:exactPattern(form.application??""),title:"(?i)^(Picture[- ]in[- ]Picture|Картинка в картинке)$",regex:true,floating:true,pin:true,keepAspectRatio:true,noInitialFocus:true,titlebar:"hide"});
  else form=Object.assign({},form,{mode:"stacking",titlebar:"hide"});
 }
 property string deviceName:""
 property string deviceError:""
 property DesktopBackend tools:DesktopBackend {}
 property string matchScope:"application"
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
  FeatureError {error:root.deviceError}
  SettingsCard {
   title:Tr.tr(root.devicesOnly?"A different feel for each device":"Choose a window to build a rule")
   description:Tr.tr(root.devicesOnly?"Device overrides follow the device name. Reset an individual value to inherit the global setting again.":"Rules match the application rather than its temporary window address. Placement rules apply to new windows; dynamic effects also update matching windows.")
   icon:root.pageIcon
   RowButton {text:Tr.tr("Refresh connected devices and windows");icon:"refresh";onClicked:DesktopRules.refresh()}
   GenericSettingRow {
    visible:!root.devicesOnly
    spec:({label:"Choose an open application",type:"choice",choices:[{value:"",label:"Choose an open application"},...root.openApplications],value:root.form.application??""})
    onEdited:value=>{if(value)root.pickApplication(value);}
   }
   GenericSettingRow {
    visible:!root.devicesOnly
    spec:({label:"Choose an open window",type:"choice",choices:[{value:"",label:"Choose an open window"},...DesktopRules.data.windows.map(w=>({value:w.address,label:w.application+" — "+w.title}))],value:DesktopRules.data.windows.some(w=>w.address===root.selectedWindow?.address)?root.selectedWindow.address:""})
    onEdited:value=>root.pickWindow(DesktopRules.data.windows.find(w=>w.address===value))
   }
   GenericSettingRow {
    visible:!root.devicesOnly&&!!root.selectedWindow
    spec:({label:"Apply rule to",type:"choice",choices:[{value:"application",label:"All windows of this application"},{value:"title",label:"Windows with the selected title"},...(root.selectedWindow?.initialTitle?[{value:"initial",label:"Windows with the same initial title"}]:[])],value:root.matchScope})
    onEdited:value=>root.setScope(value)
   }
   InfoRow {visible:!root.devicesOnly&&!!root.selectedWindow;label:Tr.tr("Rule matching");value:(root.form.application??"")+(root.form.title?" · "+root.form.title:root.form.initialTitle?" · "+root.form.initialTitle:"")}
   ToggleRow {
    visible:!root.devicesOnly&&!!root.selectedWindow&&!!root.selectedWindow.title
    text:Tr.tr("Match the selected window title too")
    checked:!!root.selectedWindow&&root.form.title===root.selectedWindow.title
    onToggled:root.setScope(checked?"title":"application")
   }
   InfoRow {visible:!root.devicesOnly&&!!root.selectedWindow;label:Tr.tr("Selected window");value:root.selectedWindow?.title??""}
   Repeater {
    model:root.devicesOnly?(DesktopRules.data.devices??[]).filter(d=>!root.tabletsOnly||d.kind==="tablets"):[]
    RowButton {
     required property var modelData
     text:modelData.name;subtext:modelData.kind;icon:"devices"
     onClicked:root.pickDevice(modelData)
    }
   }
  }
  SettingsCard {
   visible:!root.devicesOnly;title:Tr.tr("Window controls");icon:"window"
   description:Tr.tr("One button layout for shell titlebars and GTK applications. Applications may hide unavailable actions or provide their own header.")
   GenericSettingRow {spec:({label:"Button side",type:"choice",choices:[{value:"left",label:"Left"},{value:"right",label:"Right"}],value:root.controls.side});onEdited:v=>root.control("side",v)}
   Repeater {model:[{id:"minimize",label:"Minimize"},{id:"maximize",label:"Maximize"},{id:"close",label:"Close"}];ToggleRow {required property var modelData;text:Tr.tr(modelData.label);checked:root.controls.order.includes(modelData.id);onToggled:root.toggleControl(modelData.id,checked)}}
   GenericSettingRow {spec:({label:"Button order (left to right)",type:"choice",choices:["minimize,maximize,close","minimize,close,maximize","maximize,minimize,close","maximize,close,minimize","close,minimize,maximize","close,maximize,minimize"].map(v=>({value:v,label:v.split(",").map(k=>Tr.tr(k==="close"?"Close":k==="maximize"?"Maximize":"Minimize")).join(" · ")})),value:[...root.controls.order,...["minimize","maximize","close"].filter(v=>!root.controls.order.includes(v))].join(",")});onEdited:v=>root.control("order",v.split(",").filter(k=>root.controls.order.includes(k)))}
   RowButton {text:Tr.tr("Apply window controls");icon:"check";disabled:DesktopRules.busy;onClicked:DesktopRules.call("save-controls",root.controls)}
  }
  SettingsCard {
   visible:!root.devicesOnly;title:Tr.tr("Saved application rules");icon:"rule"
   description:Tr.tr("Later rules take precedence. Editing a rule preserves its position.")
   Repeater {model:DesktopRules.data.rules;RowLayout {
    required property var modelData
    required property int index
    Layout.fillWidth:true
    RowButton {Layout.fillWidth:true;text:parent.modelData.name||parent.modelData.application;subtext:parent.modelData.application+" · "+Tr.tr(parent.modelData.mode??"all")+(parent.modelData.enabled===false?" · "+Tr.tr("Disabled"):"");icon:"rule";onClicked:root.form=JSON.parse(JSON.stringify(parent.modelData))}
    IconButton {icon:"arrow_upward";enabled:!DesktopRules.busy&&parent.index>0;onClicked:DesktopRules.call("move-rule",{id:parent.modelData.id,direction:-1})}
    IconButton {icon:"arrow_downward";enabled:!DesktopRules.busy&&parent.index<DesktopRules.data.rules.length-1;onClicked:DesktopRules.call("move-rule",{id:parent.modelData.id,direction:1})}
   }}
   RowButton {text:Tr.tr("Create a rule manually");icon:"add";onClicked:root.form={name:"",application:"",enabled:true,regex:false}}
  }
  SettingsCard {
   visible:!root.devicesOnly&&Object.keys(root.form).length>0;title:Tr.tr("Rule details");icon:"tune"
   description:Tr.tr("Dynamic appearance updates existing windows. Placement is applied when a window opens in the selected mode; switching modes does not move existing windows.")
   GenericSettingRow {spec:({label:"Apply in window mode",type:"choice",choices:[{value:"all",label:"All window modes"},{value:"stacking",label:"Stacking"},{value:"scrolling",label:"Scrolling"},{value:"tiling",label:"Tiling"},{value:"canvas",label:"Canvas"}],value:root.form.mode??"all"});onEdited:v=>root.change("mode",v)}
   TextFieldRow {label:Tr.tr("Rule name");value:root.form.name??"";onValueEdited:v=>root.change("name",v)}
   TextFieldRow {label:Tr.tr("Application class");value:root.form.application??"";onValueEdited:v=>root.change("application",v)}
   TextFieldRow {label:Tr.tr("Window title (optional)");value:root.form.title??"";onValueEdited:v=>root.change("title",v)}
   ToggleRow {text:Tr.tr("Rule enabled");checked:root.form.enabled!==false;onToggled:root.change("enabled",checked)}
   ToggleRow {text:Tr.tr("Match using regular expressions");checked:root.form.regex??false;onToggled:root.change("regex",checked)}
   SettingsCard {
    title:Tr.tr("Advanced matching");icon:"filter_alt";collapsible:true;expanded:false
    Repeater {model:[{key:"matchXwayland",label:"XWayland window"},{key:"matchModal",label:"Modal window"}];GenericSettingRow {required property var modelData;spec:({label:modelData.label,type:"choice",choices:[{value:"any",label:"Any"},{value:"yes",label:"Yes"},{value:"no",label:"No"}],value:root.form[modelData.key]===undefined?"any":root.form[modelData.key]?"yes":"no"});onEdited:v=>root.optional(modelData.key,v==="any"?null:v==="yes")}}
   }
   SettingsCard {
    title:Tr.tr("Ready-made behaviours");icon:"auto_fix_high";collapsible:true;expanded:false
    RowButton {text:Tr.tr("Application draws its own titlebar");subtext:Tr.tr("Hide the extra shell titlebar in stacking mode");icon:"window";onClicked:root.preset("csd")}
    RowButton {text:Tr.tr("Picture in picture");subtext:Tr.tr("Floating, pinned, proportional video without a shell titlebar");icon:"picture_in_picture";onClicked:root.preset("pip")}
   }
   SettingsCard {
    title:Tr.tr("Titlebar and appearance");icon:"palette";collapsible:true;expanded:true
    GenericSettingRow {spec:({label:"Shell titlebar",type:"choice",choices:[{value:"auto",label:"Follow application defaults"},{value:"show",label:"Show"},{value:"hide",label:"Hide"}],value:root.form.titlebar??"auto"});onEdited:v=>root.optional("titlebar",v==="auto"?null:v)}
    Repeater {
     model:[{key:"decorate",label:"Compositor decorations"},{key:"noShadow",label:"Disable shadow"},{key:"noBlur",label:"Disable blur"},{key:"noAnim",label:"Disable animations"},{key:"focusOnActivate",label:"Focus on application activation"}]
     GenericSettingRow {required property var modelData;spec:({label:modelData.label,type:"choice",choices:[{value:"default",label:"Default"},{value:"yes",label:"Enabled"},{value:"no",label:"Disabled"}],value:root.form[modelData.key]===undefined?"default":root.form[modelData.key]?"yes":"no"});onEdited:v=>root.optional(modelData.key,v==="default"?null:v==="yes")}
    }
    Repeater {model:[{key:"borderSize",label:"Border width",max:10},{key:"rounding",label:"Corner radius",max:60}];GenericSettingRow {required property var modelData;spec:({label:modelData.label,type:"int",min:0,max:modelData.max,value:root.form[modelData.key]??0,overridden:root.form[modelData.key]!==undefined});resettable:true;onEdited:v=>root.change(modelData.key,v);onResetRequested:root.optional(modelData.key,null)}}
   }
   SettingsCard {
   title:Tr.tr("Placement and focus");icon:"desktop_windows";collapsible:true;expanded:true
   GenericSettingRow {spec:({label:"Window placement",type:"choice",choices:[{value:"default",label:"Follow the desktop mode"},{value:"float",label:"Floating"},{value:"tile",label:"Tiled"}],value:root.form.floating===undefined?"default":root.form.floating?"float":"tile"});onEdited:v=>root.optional("floating",v==="default"?null:v==="float")}
   GenericSettingRow {spec:({label:"Monitor",type:"choice",choices:["",...Monitors.monitors.map(m=>m.name)],value:root.form.monitor??""});onEdited:v=>root.change("monitor",v)}
   StepperRow {label:Tr.tr("Workspace (0 follows defaults)");from:0;to:1000000;value:root.form.workspace??0;onMoved:v=>root.optional("workspace",v?v:null)}
   ToggleRow {text:Tr.tr("Start fullscreen");checked:root.form.fullscreen??false;onToggled:root.change("fullscreen",checked)}
   ToggleRow {text:Tr.tr("Center floating windows");checked:root.form.center??false;onToggled:root.change("center",checked)}
   ToggleRow {text:Tr.tr("Show on every workspace");checked:root.form.pin??false;onToggled:root.change("pin",checked)}
   GenericSettingRow {spec:({label:"Prevent idle sleep",type:"choice",choices:["none","focus","fullscreen","always"],value:root.form.idleInhibit??"none"});onEdited:v=>root.change("idleInhibit",v)}
   ToggleRow {text:Tr.tr("Keep aspect ratio");checked:root.form.keepAspectRatio??false;onToggled:root.change("keepAspectRatio",checked)}
   ToggleRow {text:Tr.tr("Do not take focus when opening");checked:root.form.noInitialFocus??false;onToggled:root.change("noInitialFocus",checked)}
   }
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
    model:(root.deviceKind==="keyboards"?[{key:"kb_layout",label:"Keyboard layouts (comma separated)",type:"string"},{key:"kb_variant",label:"Keyboard variants",type:"string"},{key:"kb_options",label:"Keyboard options",type:"string"},{key:"repeat_rate",label:"Repeat rate",type:"int",min:1,max:100},{key:"repeat_delay",label:"Repeat delay",type:"int",min:100,max:2000}]:root.deviceKind==="tablets"?[{key:"output",label:"Map to monitor",type:"choice",choices:[{value:"",label:"All monitors"},{value:"current",label:"Current monitor"},...Monitors.monitors.map(m=>({value:m.name,label:m.description||m.name}))]},{key:"transform",label:"Rotation / flip (0–7)",type:"int",min:0,max:7},{key:"relative_input",label:"Relative input",type:"bool"},{key:"left_handed",label:"Left handed",type:"bool"},{key:"absolute_region_position",label:"Absolute mapped region position",type:"bool"}]:[{key:"sensitivity",label:"Pointer sensitivity",type:"slider",min:-1,max:1},{key:"accel_profile",label:"Pointer acceleration",type:"choice",choices:["","flat","adaptive"]},{key:"left_handed",label:"Left handed",type:"bool"},{key:"natural_scroll",label:"Natural scrolling",type:"bool"},{key:"scroll_factor",label:"Scroll speed",type:"slider",min:.1,max:10},...(/touchpad|trackpad|synaptics|elan/i.test(root.deviceName)?[{key:"tap-to-click",label:"Tap to click",type:"bool"},{key:"disable_while_typing",label:"Disable while typing",type:"bool"}]:[])])
    GenericSettingRow {
     required property var modelData
     spec:Object.assign({},modelData,{value:root.deviceValues[modelData.key]??(modelData.type==="bool"?false:modelData.type==="string"||modelData.type==="choice"?"":modelData.key==="repeat_rate"?25:modelData.key==="repeat_delay"?600:modelData.key==="sensitivity"||modelData.key==="transform"?0:1),step:.01,overridden:root.deviceValues[modelData.key]!==undefined})
     resettable:true
     onEdited:v=>root.deviceValues=Object.assign({},root.deviceValues,{[modelData.key]:v})
     onResetRequested:{const next=Object.assign({},root.deviceValues);delete next[modelData.key];root.deviceValues=next;}
    }
   }
   Repeater {
    model:root.deviceKind==="tablets"?[{key:"active_area_size",label:"Active area size in mm (width, height)"},{key:"active_area_position",label:"Active area offset in mm (x, y)"},{key:"region_size",label:"Mapped region size in pixels (width, height)"},{key:"region_position",label:"Mapped region position in pixels (x, y)"}]:[]
    TextFieldRow {
     required property var modelData
     label:Tr.tr(modelData.label);subtext:Tr.tr("Two numbers separated by a comma; 0, 0 uses the default area.")
     value:(root.deviceValues[modelData.key]??[0,0]).join(", ")
     onEditingFinished:value=>{const parts=value.split(",").map(s=>Number(s.trim()));if(parts.length===2&&parts.every(Number.isFinite)&&(!modelData.key.endsWith("size")||parts.every(v=>v>=0))){root.deviceError="";root.deviceValues=Object.assign({},root.deviceValues,{[modelData.key]:parts});}else root.deviceError=Tr.tr("Enter two valid numbers separated by a comma.");}
    }
   }
   RowButton {text:Tr.tr("Save device overrides");icon:"save";disabled:DesktopRules.busy;onClicked:DesktopRules.call("save-device",{name:root.deviceName,values:root.deviceValues})}
   RowButton {text:Tr.tr("Use global settings for this device");icon:"restart_alt";onClicked:{root.deviceValues={};DesktopRules.call("save-device",{name:root.deviceName,values:{}});}}
  }
  SettingsCard {
   visible:root.tabletsOnly;title:Tr.tr("Pen and tablet buttons");icon:"touch_app";collapsible:true;expanded:false
   description:Tr.tr("Drawing applications can handle tablet buttons themselves. For device-wide remapping, use the installed input-remapper tool; ordinary keyboard shortcuts remain separate.")
   RowButton {text:Tr.tr("Open device button mapping");icon:"tune";disabled:root.tools.busy;onClicked:root.tools.call("professional.remapper",{})}
   RowButton {text:Tr.tr("Open keyboard shortcuts");icon:"keyboard";onClicked:root.nState?.openPage("shortcuts")}
   FeatureError {error:root.tools.error}
  }

 }
}
