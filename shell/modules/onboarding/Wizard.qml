pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.modules.nexus
import qs.modules.nexus.common
import qs.modules.nexus.pages
import qs.services
import qs.utils
Variants {
 id:tourWindows
 model:Onboarding.running?Quickshell.screens:[]
 StyledWindow {
  id:window
  required property ShellScreen modelData
  screen:modelData
  name:"onboarding"
  property string inspectionPage:""
  readonly property bool primary:screen?.name===Onboarding.primaryScreen
  anchors.top:true;anchors.bottom:true;anchors.left:true;anchors.right:true
  exclusionMode:ExclusionMode.Ignore
  WlrLayershell.layer:WlrLayer.Top
  WlrLayershell.keyboardFocus:primary?WlrKeyboardFocus.Exclusive:WlrKeyboardFocus.None
  visible:Onboarding.running
  color:Colours.palette.m3surface
  NexusState {id:state;screen:window.screen;isWindow:true;onClose:Onboarding.skip()}
  Connections {target:Onboarding;function onStepChanged():void {window.inspectionPage="";state.subPageIdxStack=[];state.pageHistory=[];}}
  Loader {
   anchors.fill:parent
   active:window.primary
   sourceComponent:Component {
  ColumnLayout {
   visible:window.primary
   anchors.fill:parent
   anchors.margins:Math.min(40*Tokens.scale,window.width*.03)
   spacing:Tokens.spacing.medium
   Item {
    Layout.fillWidth:true
    implicitHeight:Math.max(heading.implicitHeight,exitButton.implicitHeight)
    RowLayout {
     anchors.fill:parent
     spacing:Tokens.spacing.medium
     MaterialIcon {text:Onboarding.steps[Onboarding.step].icon;fontStyle:Tokens.font.icon.large;color:Colours.palette.m3primary}
     ColumnLayout {
      id:heading
      StyledText {text:"hics";font:Tokens.font.headline.small}
      StyledText {text:Tr.tr("Step %1 of %2").arg(Onboarding.step+1).arg(Onboarding.steps.length);color:Colours.palette.m3onSurfaceVariant}
     }
     Item {Layout.fillWidth:true}
     IconButton {id:exitButton;icon:"close";Accessible.name:Tr.tr("Skip setup");onClicked:Onboarding.skip()}
    }
   }
   RowLayout {
    Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:0;Layout.preferredHeight:0
    spacing:Tokens.spacing.large
    StyledRect {
     Layout.preferredWidth:Math.min(340*Tokens.scale,window.width*.28)
     Layout.fillHeight:true;Layout.minimumHeight:0
     visible:window.width>850*Tokens.scale
     radius:Tokens.rounding.extraLarge;color:Colours.palette.m3surfaceContainerLow;clip:true
     VerticalFadeFlickable {
      id:story
      objectName:"onboarding-story"
      anchors.fill:parent;anchors.margins:Tokens.padding.large
      fadeAmount:0.03;clip:true
      contentWidth:width;contentHeight:storyContent.implicitHeight
      StyledScrollBar.vertical:StyledScrollBar {flickable:story;shouldBeActive:true}
      ColumnLayout {
       id:storyContent
       width:story.width;spacing:Tokens.spacing.large
       StyledText {Layout.fillWidth:true;text:Onboarding.steps[Onboarding.step].title;font:Tokens.font.title.large;wrapMode:Text.WordWrap}
       DemoCard {Layout.fillWidth:true;Layout.preferredHeight:width*9/16;demoId:Onboarding.steps[Onboarding.step].demo;playing:window.visible&&window.primary}
       StyledText {Layout.fillWidth:true;text:Onboarding.steps[Onboarding.step].description;wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant;font:Tokens.font.body.medium}
       ToggleRow {text:Tr.tr("Play demonstrations");checked:Onboarding.data.settings.showDemos??true;onToggled:Onboarding.configure({showDemos:checked})}
       StyledText {Layout.fillWidth:true;text:Tr.tr("Recorded in a real hics session. You can skip any step and change everything later.");wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant;font:Tokens.font.body.small}
      }
     }
    }
    Loader {
     id:body
     objectName:"onboarding-body"
     Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumWidth:0;Layout.minimumHeight:0;Layout.preferredHeight:0
     clip:true
     sourceComponent:window.inspectionPage?inspection:Onboarding.step===3?displays:Onboarding.step===7?storage:content
     onLoaded:{opacity=0;appear.restart();}
     NumberAnimation {id:appear;target:body;property:"opacity";to:1;duration:GlobalConfig.appearance.reducedMotion?0:240;easing.type:Easing.OutCubic}
    }
   }
   FeatureError {error:Onboarding.error}
   Rectangle {
    Layout.fillWidth:true;implicitHeight:4*Tokens.scale;radius:height/2;color:Colours.palette.m3surfaceContainerHighest
    Rectangle {width:parent.width*(Onboarding.step+1)/Onboarding.steps.length;height:parent.height;radius:height/2;color:Colours.palette.m3primary;Behavior on width {Anim {}}}
   }
   Item {
    Layout.fillWidth:true
    implicitHeight:Math.max(skipButton.implicitHeight,backButton.implicitHeight,nextButton.implicitHeight)
    RowLayout {
     anchors.fill:parent
     spacing:Tokens.spacing.small
     TextButton {id:skipButton;objectName:"onboarding-skip";Layout.maximumWidth:window.width*.42;text:Tr.tr("Skip setup");type:TextButton.Tonal;inactiveColour:Colours.palette.m3secondaryContainer;inactiveOnColour:Colours.palette.m3onSecondaryContainer;onClicked:Onboarding.skip()}
     Item {Layout.fillWidth:true}
     TextButton {id:backButton;text:Tr.tr("Back");type:TextButton.Tonal;disabled:Onboarding.step===0;onClicked:if(window.inspectionPage)window.inspectionPage="";else Onboarding.go(Onboarding.step-1)}
     TextButton {id:nextButton;text:Onboarding.step===Onboarding.steps.length-1?Tr.tr("Start using hics"):Tr.tr("Continue");type:TextButton.Filled;disabled:!!DisplayProfiles.pending||!!DesktopConfiguration.pending||(Onboarding.step===1&&(body.item?.localeBusy??false));onClicked:{if(Onboarding.step===1&&body.item?.applyLocale&&body.item.applyLocale())return;if(Onboarding.step===Onboarding.steps.length-1)Onboarding.finish();else Onboarding.go(Onboarding.step+1);}}
    }
   }
  }
   }
  }
  StyledText {anchors.centerIn:parent;visible:!window.primary;text:"hics";font:Tokens.font.headline.large;color:Colours.palette.m3onSurfaceVariant}
  Shortcut {sequence:"Escape";enabled:window.primary;onActivated:Onboarding.skip()}
  Component {
   id:inspection
   ColumnLayout {
    TextButton {text:Tr.tr("Back");type:TextButton.Tonal;onClicked:window.inspectionPage=""}
    Nexus {Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:0;nState.screen:window.screen;nState.isWindow:true;Component.onCompleted:nState.openPage(window.inspectionPage);onClose:window.inspectionPage=""}
   }
  }
  Component {id:displays;DisplayPage {nState:state;explicitWheelScrolling:true}}
  Component {id:storage;StoragePage {nState:state;explicitWheelScrolling:true}}
  Component {
   id:content
   PageBase {
    id:page
    explicitWheelScrolling:true
    readonly property Connections stepScroll:Connections {target:Onboarding;function onStepChanged():void {Qt.callLater(()=>{page.flickable.cancelFlick();page.flickable.contentY=-page.flickable.topMargin;page.preferredContentY=page.flickable.contentY;});}}
    nState:state;title:Onboarding.steps[Onboarding.step].title;pageIcon:Onboarding.steps[Onboarding.step].icon
    property string layoutSearch:""
    property bool advanceAfterLocale:false
    readonly property bool localeBusy:regionEditor.busy
    function applyLocale():bool {if(!regionEditor.selected)return false;advanceAfterLocale=true;regionEditor.applySelected();return true;}
    ColumnLayout {
     width:page.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.medium
     DemoCard {Layout.fillWidth:true;Layout.maximumWidth:360*Tokens.scale;Layout.preferredHeight:width*9/16;visible:window.width<=850*Tokens.scale;demoId:Onboarding.steps[Onboarding.step].demo;playing:visible&&window.visible}
     StyledText {Layout.fillWidth:true;visible:window.width<=850*Tokens.scale;text:Onboarding.steps[Onboarding.step].description;wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant}
     SettingsCard {
      visible:Onboarding.step===0||Onboarding.step===9;title:Tr.tr(Onboarding.step===0?"A few choices, then your desktop":"You stay in control");icon:"favorite"
      StyledText {Layout.fillWidth:true;text:Tr.tr("The dock brings applications and window previews together. The panel opens quick controls. Settings keep your devices, appearance and recovery tools in one place.");wrapMode:Text.WordWrap}
      ToggleRow {text:Tr.tr("Reduce interface motion");checked:GlobalConfig.appearance.reducedMotion;onToggled:GlobalConfig.appearance.reducedMotion=checked}
      RowButton {visible:Onboarding.step===9;text:Tr.tr("Open desktop settings");icon:"settings";onClicked:{Onboarding.finish();WindowFactory.openPage("desktop-profiles");}}
     }
     SettingsCard {
      visible:Onboarding.step===1;title:Tr.tr("Shell language");icon:"translate"
      RowLayout {
       TextButton {text:"Русский";type:Tr.language.startsWith("ru")?TextButton.Filled:TextButton.Tonal;onClicked:{Tr.language="ru_RU";regionEditor.selected="ru_RU.UTF-8";Onboarding.configure({language:"ru_RU"});}}
       TextButton {text:"English";type:!Tr.language.startsWith("ru")?TextButton.Filled:TextButton.Tonal;onClicked:{Tr.language="en_US";regionEditor.selected="en_US.UTF-8";Onboarding.configure({language:"en_US"});}}
      }
     }
     RegionSection {id:regionEditor;visible:Onboarding.step===1;onApplied:if(page.advanceAfterLocale){page.advanceAfterLocale=false;Onboarding.go(2);}}
     SettingsCard {
      visible:Onboarding.step===2;title:Tr.tr("Selected layouts");icon:"keyboard"
      Repeater {
       model:KeyboardConf.layoutCodes
       ColumnLayout {
        id:layout;required property string modelData;required property int index;Layout.fillWidth:true
        RowLayout {
         Layout.fillWidth:true
         StyledText {Layout.fillWidth:true;text:KeyboardConf.nameForLayout(layout.modelData);wrapMode:Text.WordWrap}
         IconButton {icon:"arrow_upward";disabled:layout.index===0;onClicked:KeyboardConf.moveLayout(layout.index,layout.index-1)}
         IconButton {icon:"delete";disabled:KeyboardConf.layoutCodes.length===1;onClicked:KeyboardConf.removeLayout(layout.index)}
        }
        GenericSettingRow {visible:KeyboardConf.variantsFor(layout.modelData).length>0;spec:({label:"Variant",type:"choice",choices:[{value:"",label:"Default"},...KeyboardConf.variantsFor(layout.modelData).map(v=>({value:v.code,label:v.name}))],value:KeyboardConf.variantByLayout[layout.modelData]??""});onEdited:v=>KeyboardConf.setVariant(layout.modelData,v)}
       }
      }
      GenericSettingRow {spec:({label:"Layout switching shortcut",type:"choice",choices:[{value:"",label:"None"},{value:"grp:alt_shift_toggle",label:"Alt+Shift"},{value:"grp:ctrl_shift_toggle",label:"Ctrl+Shift"},{value:"grp:win_space_toggle",label:"Super+Space"},{value:"grp:caps_toggle",label:"Caps Lock"}],value:KeyboardConf.switchOption});onEdited:v=>KeyboardConf.setSwitchOption(v)}
      TextFieldRow {label:Tr.tr("Find a keyboard layout");value:page.layoutSearch;onValueEdited:v=>page.layoutSearch=v}
      Repeater {model:KeyboardConf.layouts.filter(l=>!KeyboardConf.layoutCodes.includes(l.code)&&(!page.layoutSearch?["us","ru","ua","gb","de","fr","es","it"].includes(l.code):(l.name.toLowerCase().includes(page.layoutSearch.toLowerCase())||l.code.includes(page.layoutSearch)))).slice(0,25);RowButton {required property var modelData;text:modelData.name;subtext:modelData.code;icon:"add";onClicked:KeyboardConf.addLayout(modelData.code)}}
     }
     SettingsCard {
      visible:Onboarding.step===4;title:Tr.tr("Four ways to work");icon:"view_quilt"
      Repeater {
       model:[{id:"stacking",title:"Stacking",text:"Familiar overlapping windows, a task dock and expressive minimize animations.",icon:"filter_none"},{id:"tiling",title:"Tiling",text:"A structured layout that gives each window its own space.",icon:"view_quilt"},{id:"scrolling",title:"Scrolling",text:"A continuous row of windows that follows your focus.",icon:"view_column"},{id:"canvas",title:"Infinite canvas",text:"Arrange windows on a spatial desktop, pan, zoom and return to remembered groups.",icon:"pan_tool"}]
       RowButton {required property var modelData;text:Tr.tr(modelData.title);subtext:Tr.tr(modelData.text);icon:modelData.icon;trailingIcon:LayoutModes.mode===modelData.id?"check":"chevron_right";disabled:LayoutModes.busy||modelData.id==="canvas"&&!LayoutModes.config.canvasAvailable;onClicked:LayoutModes.select(modelData.id)}
      }
      FeatureError {error:LayoutModes.error}
     }
     SettingsCard {
      visible:Onboarding.step===5;title:Tr.tr("Colours across the desktop");icon:"palette"
      RowLayout {TextButton {text:Tr.tr("Light");onClicked:Colours.setMode("light")} TextButton {text:Tr.tr("Dark");onClicked:Colours.setMode("dark")}}
      GridLayout {Layout.fillWidth:true;columns:width>500*Tokens.scale?2:1;Repeater {model:ThemeSchemes.themes;RowButton {required property var modelData;text:Tr.tr(modelData.name);icon:"palette";trailingIcon:Colours.scheme===modelData.id?"check":"";disabled:ThemeSchemes.busy;onClicked:ThemeSchemes.apply(modelData.id,Colours.currentLight?"light":"dark")}}}
      FeatureError {error:ThemeSchemes.error}
     }
     SettingsCard {
      visible:Onboarding.step===6;title:Tr.tr("A collection to start with");description:"GNOME Backgrounds · CC-BY-SA-3.0-US";icon:"wallpaper"
      RowButton {text:Onboarding.downloading?Tr.tr("Downloading wallpaper collection…"):Tr.tr("Download wallpaper collection");icon:"download";disabled:Onboarding.downloading;onClicked:Onboarding.downloadWallpapers()}
      GridLayout {
       Layout.fillWidth:true;columns:width>500*Tokens.scale?2:1
       Repeater {
        model:Onboarding.data.wallpapers??[]
        StyledRect {
         id:wall;required property var modelData;Layout.fillWidth:true;implicitHeight:Math.max(120,wall.width*9/16);radius:Tokens.rounding.large;clip:true;color:Colours.palette.m3surfaceContainerHigh
         Image {anchors.fill:parent;source:Paths.fileUrl(wall.modelData.path);asynchronous:true;sourceSize.width:480;fillMode:Image.PreserveAspectCrop}
         StateLayer {anchors.fill:parent;keyboardFocusable:true;Accessible.name:wall.modelData.name;onClicked:Wallpapers.setWallpaper(wall.modelData.path)}
        }
       }
      }
     }
     SettingsCard {
      visible:Onboarding.step===8;title:Tr.tr("Keep useful tools close");icon:"auto_awesome"
      Repeater {model:[{id:"clipboard",title:"Clipboard history",icon:"content_paste",text:"Pin useful text and images, control retention and pause capture for private work."},{id:"shortcuts",title:"Keyboard shortcuts",icon:"keyboard",text:"Record shortcuts, resolve conflicts and keep original window-management actions."},{id:"projects",title:"Workspace projects",icon:"workspaces",text:"Save a set of applications and their arrangement as a named project."},{id:"configuration-history",title:"Configuration history",icon:"history",text:"Try changes knowing that your previous configuration has a way back."},{id:"desktop-health",title:"Desktop health",icon:"monitor_heart",text:"Inspect services and prepare a private diagnostic report when something needs attention."}];RowButton {required property var modelData;text:Tr.tr(modelData.title);subtext:Tr.tr(modelData.text);icon:modelData.icon;onClicked:window.inspectionPage=modelData.id}}
     }
    }
   }
  }
 }
}
