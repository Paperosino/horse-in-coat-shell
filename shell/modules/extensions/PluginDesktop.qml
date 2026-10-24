pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
Item {
    id: root
    required property ShellScreen screen
    function relayout(): void { for(let i=0;i<widgets.count;i++) widgets.itemAt(i)?.applyGeometry(); }
    onWidthChanged: relayout()
    onHeightChanged: relayout()
    StyledRect {
        visible:Plugins.desktopEditing;z:1000
        anchors.top:parent.top;anchors.horizontalCenter:parent.horizontalCenter;anchors.topMargin:Tokens.spacing.large
        width:tools.implicitWidth+Tokens.padding.large*2;height:tools.implicitHeight+Tokens.padding.medium*2
        radius:Tokens.rounding.full;color:Colours.tPalette.m3surfaceContainerHigh
        Row {
            id:tools;anchors.centerIn:parent;spacing:Tokens.spacing.small
            StyledText {anchors.verticalCenter:parent.verticalCenter;text:Tr.tr("Desktop widget layout")}
            IconButton {icon:"grid_on";Accessible.name:Tr.tr("Grid spacing");onClicked:{for(let i=0;i<widgets.count;i++){const frame=widgets.itemAt(i);frame.persist({grid:frame.grid===16?32:frame.grid===32?8:16});}}}
            IconButton {icon:"check";Accessible.name:Tr.tr("Finish editing");onClicked:Plugins.desktopEditing=false}
        }
    }
    Repeater {
        id: widgets
        model: ScriptModel { values: Plugins.enabled.filter(p => !!p.entryPoints.desktopWidget).map(p => p.id) }
        delegate: StyledRect {
            id: frame
            objectName:"desktopWidget-"+modelData
            required property string modelData
            readonly property var manifest: Plugins.byId(modelData)
            readonly property var geometry: manifest?.desktopLayout?.[root.screen.name] ?? ({})
            readonly property bool locked: geometry.locked ?? false
            readonly property bool editing: Plugins.desktopEditing
            readonly property int grid: geometry.grid ?? 16
            property point pressPosition: Qt.point(0,0)
            property real originX: 0
            property real originY: 0
            property real originWidth: 0
            property real originHeight: 0
            function align(value: real): real { return geometry.snap === false ? value : Math.round(value / grid) * grid; }
            function applyGeometry(): void {
                if (move.active || resize.active) return;
                width = Math.min(Math.max(64,root.width), Math.max(64, Number(geometry.width ?? widget.implicitWidth + Tokens.padding.medium * 2)));
                height = Math.min(Math.max(48,root.height), Math.max(48, Number(geometry.height ?? widget.implicitHeight + Tokens.padding.medium * 2)));
                x = Math.max(0, Math.min(root.width - width, Number(geometry.x ?? manifest?.settings.desktopX ?? 32)));
                y = Math.max(0, Math.min(root.height - height, Number(geometry.y ?? manifest?.settings.desktopY ?? 32)));
            }
            function persist(changes: var): void { Plugins.saveDesktopLayout(modelData, root.screen.name, changes); }
            function savePlacement(): void {
                x = Math.max(0, Math.min(root.width - width, align(x)));
                y = Math.max(0, Math.min(root.height - height, align(y)));
                persist({x:x,y:y,width:width,height:height});
            }
            onGeometryChanged: applyGeometry()
            Component.onCompleted: Qt.callLater(applyGeometry)
            radius: Tokens.rounding.large
            color: Colours.tPalette.m3surfaceContainer
            border.width: editing ? 2 * Tokens.scale : 0
            border.color: locked ? Colours.palette.m3outline : Colours.palette.m3primary
            clip: true
            Accessible.role: Accessible.Pane
            Accessible.name: manifest?.name ?? modelData
            activeFocusOnTab: editing
            Keys.onPressed: event => {
                if (!editing || locked) return;
                const dx = event.key === Qt.Key_Left ? -grid : event.key === Qt.Key_Right ? grid : 0;
                const dy = event.key === Qt.Key_Up ? -grid : event.key === Qt.Key_Down ? grid : 0;
                if (!dx && !dy) return;
                if (event.modifiers & Qt.ControlModifier) { width=Math.max(64,width+dx);height=Math.max(48,height+dy); }
                else { x+=dx;y+=dy; }
                savePlacement();event.accepted=true;
            }
            PluginSlot {
                id: widget
                anchors.fill: parent
                anchors.margins: Tokens.padding.medium
                pluginId: frame.modelData
                slot: "desktopWidget"
                onLoaded: {
                    if ("screenName" in item) item.screenName=root.screen.name;
                    if ("width" in item) item.width=Qt.binding(() => widget.width);
                    if ("height" in item) item.height=Qt.binding(() => widget.height);
                    Qt.callLater(frame.applyGeometry);
                }
            }
            DragHandler {
                id: move
                enabled: frame.editing && !frame.locked
                target: null
                onActiveChanged: {
                    if (active) { frame.originX=frame.x;frame.originY=frame.y;frame.pressPosition=centroid.scenePosition;frame.forceActiveFocus(); }
                    else frame.savePlacement();
                }
                onTranslationChanged: if (active) {
                    frame.x=Math.max(0,Math.min(root.width-frame.width,frame.originX+centroid.scenePosition.x-frame.pressPosition.x));
                    frame.y=Math.max(0,Math.min(root.height-frame.height,frame.originY+centroid.scenePosition.y-frame.pressPosition.y));
                }
            }
            Row {
                visible: frame.editing
                anchors.top: parent.top;anchors.right: parent.right
                IconButton { icon:frame.locked?"lock":"lock_open";Accessible.name:Tr.tr("Lock widget");onClicked:frame.persist({locked:!frame.locked}) }
                IconButton { icon:"grid_on";Accessible.name:Tr.tr("Snap widget to grid");onClicked:frame.persist({snap:frame.geometry.snap===false}) }
                IconButton { icon:"restart_alt";Accessible.name:Tr.tr("Reset widget size");onClicked:frame.persist({width:null,height:null}) }
            }
            StyledRect {
                visible: frame.editing && !frame.locked
                anchors.right:parent.right;anchors.bottom:parent.bottom
                width:28*Tokens.scale;height:width;radius:Tokens.rounding.small
                color:Colours.palette.m3primaryContainer
                MaterialIcon {anchors.centerIn:parent;text:"open_in_full";fontStyle:Tokens.font.icon.small}
                DragHandler {
                    id: resize
                    target:null
                    onActiveChanged: {
                        if(active){frame.originWidth=frame.width;frame.originHeight=frame.height;frame.pressPosition=centroid.scenePosition;}
                        else frame.savePlacement();
                    }
                    onTranslationChanged: if(active) {
                        frame.width=Math.max(64,Math.min(root.width-frame.x,frame.align(frame.originWidth+centroid.scenePosition.x-frame.pressPosition.x)));
                        frame.height=Math.max(48,Math.min(root.height-frame.y,frame.align(frame.originHeight+centroid.scenePosition.y-frame.pressPosition.y)));
                    }
                }
            }
        }
    }
}
