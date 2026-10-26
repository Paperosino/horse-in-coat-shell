pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import QtQuick.Controls as QQC
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.Services
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.utils

FocusScope {
    id:root
    required property ShellScreen screen
    property var selected:[]
    property string current:""
    readonly property bool contextMenuOpen:menu.opened
    readonly property bool editorOpen:editor.opened
    readonly property real iconSize:Math.max(32,Math.min(96,DesktopIcons.config.iconSize))*Tokens.scale
    readonly property real cellWidth:Math.max(100*Tokens.scale,iconSize+32*Tokens.scale)
    readonly property real cellHeight:iconSize+60*Tokens.scale
    readonly property int columns:Math.max(1,Math.floor(view.width/cellWidth))
    readonly property var entries:DesktopFiles.entries.slice().sort((a,b)=>{
        const mode=DesktopIcons.config.sortBy;
        if(mode==="modified")return b.modified-a.modified||a.name.localeCompare(b.name);
        if(mode==="type" && a.directory!==b.directory)return a.directory?-1:1;
        return a.name.localeCompare(b.name,undefined,{numeric:true});
    })
    readonly property var placements:{
        const positions=DesktopFiles.positions[screen.name]??{};const used={},result={};
        for(const entry of entries){const saved=positions[entry.fileName];if(saved){const col=Math.min(columns-1,Math.max(0,saved[0]));const row=Math.max(0,saved[1]);const key=col+":"+row;if(!used[key]){used[key]=true;result[entry.url]={col,row};}}}
        let index=0;
        for(const entry of entries)if(!result[entry.url]){while(used[(index%columns)+":"+Math.floor(index/columns)])index++;const col=index%columns,row=Math.floor(index/columns);used[col+":"+row]=true;result[entry.url]={col,row};}
        return result;
    }
    readonly property var visibleEntries:entries.filter(entry=>{
        const row=placements[entry.url]?.row??0;
        return (row+1)*cellHeight>=view.contentY-cellHeight && row*cellHeight<=view.contentY+view.height+cellHeight;
    })
    readonly property var selectionSet:new Set(selected)
    readonly property var selectedEntries:entries.filter(entry=>selectionSet.has(entry.url))
    readonly property bool privateHidden:Presentation.privateOn(screen)
    visible:!privateHidden
    onPrivateHiddenChanged:if(privateHidden){menu.close();editor.close();selected=[];}
    Connections {
        target:root.Window.window
        function onActiveChanged():void {if(!root.Window.window?.active)menu.close();}
    }
    Connections {target:DesktopFiles;function onChanged():void {const available=new Set(DesktopFiles.entries.map(entry=>entry.url));root.selected=root.selected.filter(url=>available.has(url));}}
    function focusDesktop():void {forceActiveFocus();}
    function select(url:string,modifiers:int):void {
        focusDesktop();current=url;
        if(modifiers&Qt.ControlModifier)selected=selected.includes(url)?selected.filter(item=>item!==url):selected.concat([url]);
        else if(!selected.includes(url))selected=[url];
    }
    function ask(action:string):void {
        if(action!=="mkdir"&&!selectedEntries.length)return;
        editor.action=action;editor.paths=selectedEntries.map(entry=>entry.path);
        input.text=action==="rename"?selectedEntries[0].fileName:"";editor.open();
        if(action!=="trash")Qt.callLater(()=>{input.forceActiveFocus();input.selectAll();});
    }
    function openMenu(x:real,y:real):void {focusDesktop();menu.x=Math.min(width-menu.width,Math.max(0,x));menu.y=Math.min(height-menu.height,Math.max(0,y));menu.open();}
    Keys.onPressed:event=>{
        if(event.key===Qt.Key_Escape){selected=[];event.accepted=true;}
        else if(event.matches(StandardKey.SelectAll)){selected=entries.map(entry=>entry.url);event.accepted=true;}
        else if(event.matches(StandardKey.Copy)){DesktopFiles.copy(selected,false);event.accepted=true;}
        else if(event.matches(StandardKey.Cut)){DesktopFiles.copy(selected,true);event.accepted=true;}
        else if(event.matches(StandardKey.Paste)){DesktopIcons.paste();event.accepted=true;}
        else if(event.key===Qt.Key_F2){ask("rename");event.accepted=true;}
        else if(event.key===Qt.Key_Delete){ask("trash");event.accepted=true;}
        else if(event.key===Qt.Key_F5){DesktopFiles.refresh();event.accepted=true;}
        else if(event.key===Qt.Key_Return||event.key===Qt.Key_Enter){if(current)DesktopFiles.open(current);event.accepted=true;}
        else if([Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down].includes(event.key)){
            let index=entries.findIndex(entry=>entry.url===current);index=Math.max(0,Math.min(entries.length-1,index+(event.key===Qt.Key_Left?-1:event.key===Qt.Key_Right?1:event.key===Qt.Key_Up?-columns:columns)));
            if(entries[index]){current=entries[index].url;selected=[current];}event.accepted=true;
        }
    }
    MouseArea {
        anchors.fill:parent;acceptedButtons:Qt.LeftButton|Qt.RightButton
        property point start:Qt.point(0,0)
        onPressed:mouse=>{root.focusDesktop();start=Qt.point(mouse.x,mouse.y);if(!(mouse.modifiers&Qt.ControlModifier))root.selected=[];}
        onClicked:mouse=>{if(mouse.button===Qt.RightButton)root.openMenu(mouse.x,mouse.y);}
    }
    Flickable {
        id:view
        anchors.fill:parent;clip:true
        contentHeight:Math.max(height,...root.entries.map(entry=>((root.placements[entry.url]?.row??0)+1)*root.cellHeight))
        boundsBehavior:Flickable.StopAtBounds
        Repeater {
            model:ScriptModel {values:root.visibleEntries.map(entry=>entry.url)}
            delegate:Item {
                id:tile
                required property string modelData
                readonly property var entry:root.entries.find(entry=>entry.url===modelData)??({name:"",icon:"text-x-generic"})
                readonly property bool selected:root.selectionSet.has(modelData)
                readonly property var placement:root.placements[modelData]??({col:0,row:0})
                x:placement.col*root.cellWidth;y:placement.row*root.cellHeight
                width:root.cellWidth;height:root.cellHeight
                Drag.active:drag.active
                Drag.dragType:Drag.Automatic
                Drag.supportedActions:Qt.CopyAction|Qt.MoveAction
                Drag.mimeData:({"text/uri-list":root.selected.join("\r\n"),"application/x-hics-desktop-item":modelData})
                Drag.imageSource:image.source
                Drag.onDragStarted:root.select(modelData,0)
                Accessible.role:Accessible.Button
                Accessible.name:entry.name
                Accessible.selected:selected
                Accessible.onPressAction:DesktopFiles.open(modelData)
                Rectangle {
                    anchors.fill:parent;anchors.margins:4*Tokens.scale;radius:Tokens.rounding.large
                    color:tile.selected?Colours.palette.m3secondaryContainer:Colours.tPalette.m3surfaceContainer
                    opacity:tile.selected?0.9:mouse.containsMouse?0.55:0
                    border.width:tile.selected?1:0;border.color:Colours.palette.m3primary
                    Behavior on opacity {NumberAnimation {duration:GlobalConfig.appearance.reducedMotion?0:120}}
                }
                Image {id:image;anchors.top:parent.top;anchors.topMargin:12*Tokens.scale;anchors.horizontalCenter:parent.horizontalCenter;width:root.iconSize;height:width;sourceSize.width:width;sourceSize.height:height;source:Quickshell.iconPath(tile.entry.icon,true);fillMode:Image.PreserveAspectFit;asynchronous:true}
                MaterialIcon {anchors.centerIn:image;visible:!image.source.toString()||image.status===Image.Error;text:tile.entry.directory?"folder":"description";fontStyle:Tokens.font.icon.size(root.iconSize*0.6).build();color:Colours.palette.m3primary}
                StyledText {
                    anchors.top:image.bottom;anchors.topMargin:5*Tokens.scale;anchors.left:parent.left;anchors.right:parent.right;anchors.margins:8*Tokens.scale
                    text:tile.entry.name;horizontalAlignment:Text.AlignHCenter;maximumLineCount:2;elide:Text.ElideRight;wrapMode:Text.WrapAtWordBoundaryOrAnywhere
                    color:"white";style:Text.Outline;styleColor:"#a0000000";font:Tokens.font.label.medium
                }
                MouseArea {
                    id:mouse;anchors.fill:parent;hoverEnabled:true;acceptedButtons:Qt.LeftButton|Qt.RightButton
                    onPressed:event=>{root.select(tile.modelData,event.modifiers);if(event.button===Qt.RightButton){const point=tile.mapToItem(root,event.x,event.y);root.openMenu(point.x,point.y);}}
                    onClicked:event=>{if(event.button===Qt.LeftButton&&DesktopIcons.config.singleClick&&!(event.modifiers&Qt.ControlModifier))DesktopFiles.open(tile.modelData);}
                    onDoubleClicked:event=>{if(event.button===Qt.LeftButton&&!DesktopIcons.config.singleClick)DesktopFiles.open(tile.modelData);}
                }
                DragHandler {id:drag;target:null;acceptedButtons:Qt.LeftButton;onActiveChanged:if(active)root.select(tile.modelData,0)}
            }
        }
    }
    DropArea {
        anchors.fill:parent
        onDropped:drop=>{
            const internal=drop.formats.includes("application/x-hics-desktop-item");
            if(internal){const url=drop.getDataAsString("application/x-hics-desktop-item");DesktopFiles.place(root.screen.name,url,Math.max(0,Math.floor(drop.x/root.cellWidth)),Math.max(0,Math.floor((drop.y+view.contentY)/root.cellHeight)));drop.accept(Qt.MoveAction);}
            else if(drop.hasUrls){const paths=drop.urls.map(url=>Paths.toLocalFile(url)).filter(path=>path.startsWith("/"));if(paths.length){DesktopIcons.copyToDesktop(paths);drop.accept(Qt.CopyAction);}}
        }
    }
    QQC.Popup {
        id:menu
        objectName:"desktopFileMenu"
        width:270*Tokens.scale;padding:8*Tokens.scale
        closePolicy:QQC.Popup.CloseOnEscape|QQC.Popup.CloseOnPressOutside
        background:Rectangle {radius:Tokens.rounding.large;color:Colours.palette.m3surfaceContainer;border.width:1;border.color:Colours.palette.m3outlineVariant}
        enter:Transition {NumberAnimation {property:"opacity";from:0;to:1;duration:GlobalConfig.appearance.reducedMotion?0:100}}
        contentItem:Column {
            spacing:2*Tokens.scale
            Action {text:Tr.tr("Open");icon:"open_in_new";visible:root.selected.length===1;onTriggered:DesktopFiles.open(root.selected[0])}
            Action {text:Tr.tr("Copy");icon:"content_copy";visible:root.selected.length>0;onTriggered:DesktopFiles.copy(root.selected,false)}
            Action {text:Tr.tr("Cut");icon:"content_cut";visible:root.selected.length>0;onTriggered:DesktopFiles.copy(root.selected,true)}
            Action {text:Tr.tr("Paste");icon:"content_paste";onTriggered:DesktopIcons.paste()}
            Action {text:Tr.tr("Rename");icon:"edit";visible:root.selected.length===1;onTriggered:root.ask("rename")}
            Action {text:Tr.tr("Move to trash");icon:"delete";visible:root.selected.length>0;onTriggered:root.ask("trash")}
            Action {text:Tr.tr("New folder");icon:"create_new_folder";onTriggered:root.ask("mkdir")}
            Action {text:Tr.tr("Show in file manager");icon:"folder_open";visible:root.selected.length===1;onTriggered:DesktopFiles.reveal(root.selected[0])}
            Action {text:Tr.tr("Properties");icon:"info";visible:root.selected.length===1;onTriggered:DesktopFiles.reveal(root.selected[0],true)}
            Action {text:Tr.tr("Open desktop folder");icon:"folder_open";onTriggered:DesktopIcons.openFolder()}
            Action {text:Tr.tr("Open trash");icon:"delete";onTriggered:DesktopFiles.open("trash:///")}
            Action {text:Tr.tr("Arrange desktop icons");icon:"grid_view";onTriggered:DesktopFiles.tidy()}
            Action {text:Tr.tr("Refresh");icon:"refresh";onTriggered:DesktopFiles.refresh()}
        }
    }
    QQC.Popup {
        id:editor
        objectName:"desktopFileEditor"
        property string action:""
        property var paths:[]
        anchors.centerIn:parent;width:Math.min(root.width-32*Tokens.scale,440*Tokens.scale);padding:24*Tokens.scale
        modal:true;closePolicy:QQC.Popup.CloseOnEscape|QQC.Popup.CloseOnPressOutside
        background:Rectangle {radius:Tokens.rounding.extraLarge;color:Colours.palette.m3surfaceContainerHigh}
        contentItem:Column {
            spacing:16*Tokens.scale
            StyledText {width:parent.width;wrapMode:Text.Wrap;text:editor.action==="trash"?Tr.tr("Move selected items to trash?"):editor.action==="mkdir"?Tr.tr("New folder"):Tr.tr("Rename");font:Tokens.font.title.medium}
            StyledTextField {id:input;width:parent.width;visible:editor.action!=="trash";onAccepted:confirm.clicked()}
            Row {
                spacing:12*Tokens.scale
                TextButton {text:Tr.tr("Cancel");onClicked:editor.close()}
                TextButton {id:confirm;text:Tr.tr("Confirm");onClicked:{DesktopIcons.operation(editor.action,{path:editor.paths[0]??"",sources:editor.paths,name:input.text});editor.close();}}
            }
        }
    }
    Rectangle {
        anchors.bottom:parent.bottom;anchors.horizontalCenter:parent.horizontalCenter
        width:Math.min(parent.width,620*Tokens.scale);height:message.implicitHeight+24*Tokens.scale;radius:Tokens.rounding.large;color:Colours.palette.m3surfaceContainerHigh
        visible:!!(DesktopIcons.error||DesktopFiles.error)
        StyledText {id:message;anchors.fill:parent;anchors.margins:12*Tokens.scale;text:Tr.tr(DesktopIcons.error||DesktopFiles.error);wrapMode:Text.Wrap;color:Colours.palette.m3error}
    }
    component Action:Rectangle {
        id:action
        required property string text
        required property string icon
        signal triggered()
        width:menu.availableWidth;height:42*Tokens.scale;radius:Tokens.rounding.medium
        color:hover.containsMouse?Colours.palette.m3secondaryContainer:"transparent"
        Row {anchors.verticalCenter:parent.verticalCenter;anchors.left:parent.left;anchors.leftMargin:12*Tokens.scale;spacing:12*Tokens.scale;MaterialIcon {text:action.icon;fontStyle:Tokens.font.icon.medium} StyledText {text:action.text;anchors.verticalCenter:parent.verticalCenter}}
        MouseArea {id:hover;anchors.fill:parent;hoverEnabled:true;onClicked:{menu.close();action.triggered();}}
    }
}
