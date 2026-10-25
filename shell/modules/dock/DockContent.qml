pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Hyprstack.Services
import Quickshell.Hyprland
import Quickshell.Wayland
import Quickshell.Widgets
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.components.effects
import qs.services
import qs.utils
import qs.modules.launcher as Launcher
import qs.modules.launcher.services

Item {
    id: root

    required property ShellScreen screen
    required property ScreenState screenState
    required property bool panelVisible
    readonly property bool atBottom: DockConf.atBottom
    readonly property bool vertical: DockConf.vertical
    property real maxWidth: screen.width
    property real maxHeight: screen.height
    property real viewportHeight: screen.height
    readonly property real iconSize: DockConf.iconSize * Tokens.scale
    readonly property alias listSurface: appList
    readonly property alias menuSurface: taskMenu
    readonly property alias previewSurface: windowPreview
    readonly property bool motionEnabled: DockConf.animations && !GlobalConfig.appearance.reducedMotion && !GameMode.reduceDockMotion
    readonly property real motionPadding: motionEnabled ? (DockConf.lift + root.iconSize * 0.3 + 12 * Tokens.scale) : 0
    property real wavePosition: vertical ? height / 2 : width / 2
    readonly property real hoverAmount: hoverSpring.value
    MotionSpring {id:hoverSpring;target:root.motionEnabled && pointerField.hovered && !root.menuOpen && !root.listOpen && !root.draggedKey ? 1 : 0;enabled:root.motionEnabled;damping:DockConf.damping}
    readonly property var motionButtons: {
        const buttons = [];
        if (startAppsButton.item) buttons.push(startAppsButton.item);
        for (const item of taskRow.children)
            if (item.objectName === "dockTaskButton") buttons.push(item);
        if (endAppsButton.item) buttons.push(endAppsButton.item);
        return buttons;
    }
    // Sample actual animated icon geometry, never the cursor coordinate.
    // Seven overlapping lobes cover the wave and fit the shared SDF budget.
    readonly property var membraneShapes: {
        const shapes = [];
        if (!motionEnabled) return shapes;
        for (let i=0; i<motionButtons.length; ++i) {
            const button=motionButtons[i];
            if (!button || button.wave<0.015) continue;
            const p=button.mapToItem(root,button.width/2,button.height/2);
            if ((vertical ? p.y<0 || p.y>height : p.x<0 || p.x>width)) continue;
            // Scale follows Translate in the icon transform list, so it also
            // scales the displacement. Keep the membrane in that same space.
            const lift=DockConf.lift*Tokens.scale*button.wave*button.visualScale;
            const normal=vertical ? (DockConf.position==="left"?1:-1) : (atBottom?-1:1);
            const padding=6*Tokens.scale;
            const w=button.width*button.visualScale*(vertical?1+0.08*button.wave:1)+2*padding;
            const h=button.height*button.visualScale*(vertical?1:1+0.08*button.wave)+2*padding;
            const cx=p.x+(vertical?normal*lift:0), cy=p.y+(vertical?0:normal*lift);
            shapes.push({x:cx-w/2,y:cy-h/2,w:w,h:h,weight:button.wave,index:i});
        }
        return shapes.sort((a,b)=>b.weight-a.weight).slice(0,7).sort((a,b)=>a.index-b.index);
    }
    readonly property rect membraneBounds: {
        if (!membraneShapes.length) return Qt.rect(0,0,0,0);
        let x=Infinity,y=Infinity,right=-Infinity,bottom=-Infinity;
        for (const shape of membraneShapes) {
            x=Math.min(x,shape.x); y=Math.min(y,shape.y);
            right=Math.max(right,shape.x+shape.w); bottom=Math.max(bottom,shape.y+shape.h);
        }
        return Qt.rect(x,y,right-x,bottom-y);
    }
    property point absorptionCenter: Qt.point(0,0)
    property real absorptionAmount: 0
    property string lastTargets: ""
    function waveWeight(item: Item): real {
        const p = item.mapToItem(root, item.width/2,item.height/2);
        const d = (vertical ? p.y : p.x) - wavePosition;
        const sigma = DockConf.spread * Tokens.scale;
        return Math.exp(-d*d/(2*sigma*sigma)) * hoverSpring.target;
    }
    function reportTargets(): void {
        if (!Hypr.stacking || !screen || !QsWindow.window) return;
        const targets = [];
        const monitor = Hypr.monitorFor(screen)?.lastIpcObject;
        const ox = monitor?.x ?? screen.x, oy = monitor?.y ?? screen.y;
        if (visible) for (let i=0;i<taskRepeater.count;i++) {
            const button=taskRepeater.itemAt(i);
            if(!button)continue;
            const p=button.visual.mapToItem(QsWindow.window.contentItem,button.width/2,button.height/2);
            const edge=button.mapToItem(root,button.width/2,button.height/2);
            if ((vertical ? edge.y < 0 || edge.y > height : edge.x < 0 || edge.x > width)) continue;
            const size=button.width;
            const icon=button.entry && DockConf.windowAnimations && !GlobalConfig.appearance.reducedMotion ? button.entry.animationIcon() : "";
            for(const window of button.windows) targets.push({address:window.lastIpcObject.address,id:window.lastIpcObject.stableId,
                x:ox+p.x-size/2,y:oy+p.y-size/2,w:size,h:size,barTop:oy+p.y+size/2,icon:icon});
        }
        const serialized=JSON.stringify(targets);
        if(serialized!==lastTargets){lastTargets=serialized;Hypr.setTaskTargets(screen.name,serialized,"dock");}
    }
    function scheduleTargets(): void { if (!targetRefresh.running) targetRefresh.start(); }
    Connections {target:ExtraPanels;function onLiveHeightsChanged():void {root.scheduleTargets();}function onPanelsChanged():void {root.scheduleTargets();}}
    onXChanged:scheduleTargets()
    onYChanged:scheduleTargets()
    onWidthChanged:scheduleTargets()
    onHeightChanged:scheduleTargets()
    onGroupsChanged:scheduleTargets()
    Timer {id:targetRefresh;interval:80;onTriggered:root.reportTargets()}
    Timer {interval:80;repeat:true;running:Hypr.stacking && root.visible && (pointerField.hovered || root.hoverAmount>0.002);onTriggered:root.reportTargets()}
    Connections {target:Hypr;function onStackingChanged(){root.scheduleTargets();}function onConfigReloaded(){root.lastTargets="";root.scheduleTargets();}}
    Connections {target:Hypr.monitorFor(root.screen);function onLastIpcObjectChanged(){root.scheduleTargets();}}
    Item {
        z:1000
        x:-root.motionPadding;y:-root.motionPadding
        width:root.width+2*root.motionPadding;height:root.height+2*root.motionPadding
        HoverHandler {
            id:pointerField
            blocking:false
            onPointChanged: if(hovered) root.wavePosition = root.vertical ? point.position.y-root.motionPadding : point.position.x-root.motionPadding
        }
    }
    property var raisedPressTask: null
    function raisedTaskAt(point: point): var {
        // Original slots stay with the scroll view. Raised pixels need a hit
        // layer outside its scene subtree (which also includes hidden drawers).
        if (point.x>=0 && point.x<=width && point.y>=0 && point.y<=height) return null;
        let selected=null, nearest=Infinity;
        for(let i=0;i<motionButtons.length;++i) {
            const task=motionButtons[i];
            if(!task || task.wave<0.015)continue;
            const p=task.mapToItem(root,task.width/2,task.height/2);
            if(vertical ? p.y<0 || p.y>height : p.x<0 || p.x>width)continue;
            const scale=(1+(DockConf.magnification-1)*task.wave)*Math.max(1,task.impulseScale);
            const lift=DockConf.lift*Tokens.scale*task.wave*scale;
            const cx=p.x+(vertical?(DockConf.position==="left"?1:-1)*lift:0);
            const cy=p.y+(vertical?0:(atBottom?-1:1)*lift);
            const dx=point.x-cx,dy=point.y-cy;
            if(Math.abs(dx)<=task.width*scale/2+2 && Math.abs(dy)<=task.height*scale/2+2 && dx*dx+dy*dy<nearest) {
                selected=task; nearest=dx*dx+dy*dy;
            }
        }
        return selected;
    }
    MouseArea {
        id:raisedInput
        // Rendering beyond the dock must have input in the same window space,
        // independently of the scroll view and other drawer contents.
        parent:root.QsWindow.window?.contentItem ?? root
        z:9000
        enabled:root.visible && root.motionEnabled && !root.menuOpen && !root.listOpen
        property rect pressBounds:Qt.rect(0,0,0,0)
        property bool holdingBounds:false
        readonly property rect inputBounds:holdingBounds ? pressBounds : root.membraneBounds
        readonly property point origin:root.mapToItem(parent,inputBounds.x,inputBounds.y)
        x:origin.x;y:origin.y
        width:inputBounds.width;height:inputBounds.height
        containmentMask:QtObject {
            function contains(point: point): bool {
                return raisedInput.pressed || root.raisedTaskAt(raisedInput.mapToItem(root,point.x,point.y))!==null;
            }
        }
        acceptedButtons:Qt.LeftButton|Qt.RightButton|Qt.MiddleButton
        cursorShape:Qt.PointingHandCursor
        preventStealing:true
        property point pressPoint
        property bool dragged:false
        onPressed:event=>{
            pressBounds=root.membraneBounds;holdingBounds=true;
            pressPoint=mapToItem(root,event.x,event.y);
            root.raisedPressTask=root.raisedTaskAt(pressPoint);
            dragged=false;
            if(!root.raisedPressTask)event.accepted=false;
        }
        onPositionChanged:event=>{
            const task=root.raisedPressTask;
            if(!task || !task.group || !(pressedButtons & Qt.LeftButton))return;
            const p=mapToItem(root,event.x,event.y);
            if(!dragged && Math.hypot(p.x-pressPoint.x,p.y-pressPoint.y)>8*Tokens.scale) {
                dragged=true;root.closePopups();root.draggedKey=task.group.key;root.dragIcon=task.iconSource;
            }
            if(dragged)root.updateDrag(p);
        }
        onReleased:{if(dragged)root.finishDrag();Qt.callLater(()=>holdingBounds=false);}
        onCanceled:{holdingBounds=false;root.raisedPressTask=null;root.cancelDrag();}
        onClicked:event=>{
            const task=root.raisedPressTask;root.raisedPressTask=null;
            if(task && !dragged)task.activate(event.button);
        }
        onWheel:event=>{
            const task=root.raisedTaskAt(mapToItem(root,event.x,event.y));
            if(!task || !task.windows.length){event.accepted=false;return;}
            const current=task.windows.findIndex(w=>w===Hypr.activeToplevel);
            const next=(current+(event.angleDelta.y>0?1:-1)+task.windows.length)%task.windows.length;
            task.act("dock-activate",task.windows[next]);event.accepted=true;
        }
    }
    SequentialAnimation {
        id:membraneImpulse
        NumberAnimation {target:root;property:"absorptionAmount";to:1;duration:70}
        NumberAnimation {target:root;property:"absorptionAmount";to:0;duration:240;easing.type:Easing.OutCubic}
    }
    property var previewWindow: null
    property var hoveredWindow: null
    property bool previewWarm: false
    function hoverWindow(window): void {
        hoveredWindow = window;
        previewReset.stop();
        if (previewWarm) previewWindow = window;
        else previewDelay.restart();
    }
    function leaveWindow(window): void {
        if (hoveredWindow !== window) return;
        hoveredWindow = null;
        previewDelay.stop();
        previewReset.restart();
    }
    Timer { id: previewDelay; interval: 1000; onTriggered: { if (root.hoveredWindow) { root.previewWarm = true; root.previewWindow = root.hoveredWindow; } } }
    Timer { id: previewReset; interval: 5000; onTriggered: { root.previewWarm = false; root.previewWindow = null; } }
    readonly property Item openSurface: appList.visible ? appList : taskMenu.visible ? taskMenu : null
    readonly property bool unifiedSurface: !vertical && openSurface !== null
        && Math.abs(openSurface.width - width) < 1 && Math.abs(openSurface.x) < 1
    property var menuTask: null
    property bool menuOpen: false
    function closeMenu(): void { menuOpen = false; previewDelay.stop(); previewReset.stop(); hoveredWindow = previewWindow = null; previewWarm = false; }
    function closePopups(): void { listOpen = false; closeMenu(); }
    function dismissOutside(item: Item, x: real, y: real): void {
        if (!menuOpen && !listOpen) return;
        const surfaces = menuOpen ? [taskMenu, windowPreview] : [root, appList];
        const inside = surfaces.some(surface => {
            if (!surface.visible) return false;
            const p = surface.mapFromItem(item, x, y);
            return p.x >= 0 && p.y >= 0 && p.x <= surface.width && p.y <= surface.height;
        });
        if (!inside) closePopups();
    }
    readonly property real offsetScale: 0

    readonly property real listNaturalWidth: 320 * Tokens.scale
    readonly property int popupGap: Math.round(8 * Tokens.scale)
    readonly property var appEntries: ApplicationCatalogue.applications.values
    property bool listOpen: false

    property string draggedKey: ""
    property string dropKey: ""
    property bool dropAfter: false
    property point dragPoint: Qt.point(0, 0)
    property string dragIcon: ""
    property bool externalDrag: false

    function updateDrag(point: point): void {
        dragPoint = point;
        dropKey = "";
        const coordinate = vertical ? point.y : point.x;
        for (let i = 0; i < taskRepeater.count; ++i) {
            const item = taskRepeater.itemAt(i);
            if (!item || item.group.key === draggedKey) continue;
            const start = item.mapToItem(root, 0, 0);
            dropKey = item.group.key;
            dropAfter = coordinate > (vertical ? start.y + item.height / 2 : start.x + item.width / 2);
            if (!dropAfter) break;
        }
    }
    function cancelDrag(): void { draggedKey = dropKey = ""; externalDrag = false; }
    function finishDrag(): void {
        const key = draggedKey, target = dropKey, after = dropAfter;
        const inside = dragPoint.x >= 0 && dragPoint.y >= 0 && dragPoint.x <= width && dragPoint.y <= height;
        cancelDrag();
        if (inside && target) Qt.callLater(() => Taskbar.move(key, target, after, groups.map(g => g.key)));
    }
    function dragApplication(entry: var, point: point): void {
        externalDrag = true;
        draggedKey = entry.id;
        dragIcon = Quickshell.iconPath(entry.icon, "image-missing");
        updateDrag(point);
    }
    function dropApplication(entry: var): void {
        const inside = dragPoint.x >= 0 && dragPoint.y >= 0 && dragPoint.x <= width && dragPoint.y <= height;
        const target = dropKey, after = dropAfter;
        cancelDrag();
        if (!DockConf.enabled || !inside) return;
        if (!Taskbar.pinned.includes(entry.id)) Taskbar.togglePin(entry.id);
        if (target) Qt.callLater(() => Taskbar.move(entry.id, target, after, groups.map(g => g.key)));
        listOpen = false;
    }

    function lookup(app: string): var {
        return appEntries.find(e => !!e.startupClass && e.startupClass.toLowerCase() === app.toLowerCase())
            ?? ApplicationCatalogue.heuristicLookup(app)
            ?? ApplicationCatalogue.heuristicLookup(app.replace(/-browser$/, ""))
            ?? ApplicationCatalogue.heuristicLookup(app.replace(/\.desktop$/, "").split(".").pop());
    }

    readonly property var groups: {
        const groups = new Map();
        const windows = Hypr.taskWindows(screen).slice().sort((a, b) =>
            a.lastIpcObject.stableId.localeCompare(b.lastIpcObject.stableId));
        for (const window of windows) {
            const app = window.lastIpcObject.class;
            const entry = lookup(app);
            const key = entry?.id ?? app.toLowerCase();
            if (!groups.has(key))
                groups.set(key, { app: app, key: key, entry: entry, windows: [] });
            groups.get(key).windows.push(window);
        }
        for (const key of Taskbar.pinned) {
            if (groups.has(key)) continue;
            const entry = ApplicationCatalogue.byId(key) ?? lookup(key);
            if (entry) groups.set(key, { app: key, key: key, entry: entry, windows: [] });
        }
        return Array.from(groups.values()).sort((a, b) => {
            const ai = Taskbar.order.indexOf(a.key), bi = Taskbar.order.indexOf(b.key);
            return (ai < 0 ? 100000 : ai) - (bi < 0 ? 100000 : bi);
        });
    }

    visible: DockConf.enabled && panelVisible
    implicitWidth: Math.min(maxWidth, dock.implicitWidth)
    implicitHeight: Math.min(maxHeight, dock.implicitHeight)
    onVisibleChanged: { if (!visible) closePopups(); Qt.callLater(reportTargets); }
    onVerticalChanged: listOpen = false
    Connections {
        target: DockConf
        function onPositionChanged() { root.closePopups(); }
    }
    onListOpenChanged: {
        if (listOpen) {
            closeMenu();
            screenState.launcher = screenState.sidebar = screenState.session = false;
            search.text = "";
            Qt.callLater(() => search.forceActiveFocus());
        }
    }

    Connections {
        target: root.screenState
        function onLauncherChanged() { if (root.screenState.launcher) root.closePopups(); }
        function onSidebarChanged() { if (root.screenState.sidebar) root.closePopups(); }
        function onSessionChanged() { if (root.screenState.session) root.closePopups(); }
        function onDashboardChanged() { if (root.screenState.dashboard) root.closePopups(); }
    }

    // Dock surface
    Item {
        id: dock

        readonly property real contentWidth: taskRow.implicitWidth + Tokens.padding.small * 2

        implicitWidth: !root.vertical && (root.listOpen || root.menuOpen) ? Math.max(root.listOpen ? root.listNaturalWidth : taskMenu.naturalWidth, contentWidth) : contentWidth
        implicitHeight: taskRow.implicitHeight + Tokens.padding.small * 2

        width: root.width
        height: root.height
        anchors.centerIn: parent

        Behavior on implicitWidth { Anim { type: Anim.Standard } }

        Flickable {
            id: taskScroll
            x:root.vertical && DockConf.position === "right" ? -root.motionPadding : 0
            y:!root.vertical && root.atBottom ? -root.motionPadding : 0
            width:parent.width+(root.vertical ? root.motionPadding : 0)
            height:parent.height+(!root.vertical ? root.motionPadding : 0)
            clip: true
            onContentXChanged:root.scheduleTargets()
            onContentYChanged:root.scheduleTargets()
            contentWidth: Math.max(width, taskRow.implicitWidth + Tokens.padding.small * 2)
            contentHeight: Math.max(height, taskRow.implicitHeight + Tokens.padding.small * 2)
            boundsBehavior: Flickable.StopAtBounds
            interactive: !root.draggedKey

            Grid {
                id: taskRow
                columns: root.vertical ? 1 : taskRepeater.count + 2

                x: (root.vertical && DockConf.position === "right" ? root.motionPadding : 0) + Math.max(Tokens.padding.small, (root.width - width) / 2)
                y: (!root.vertical && root.atBottom ? root.motionPadding : 0) + Math.max(Tokens.padding.small, (root.height - height) / 2)
                spacing: Tokens.spacing.small
                move: Transition { Anim { properties: "x,y" } }

                Loader {
                    id: startAppsButton
                    active: DockConf.menuButtonPosition === "start"
                    visible: active
                    width: active ? root.iconSize : 0
                    height: width
                    sourceComponent: AppsButton {}
                }
                DockSeparator { visible: taskRepeater.count > 0 && DockConf.menuButtonPosition === "start" }


                Repeater {
                    id: taskRepeater

                    model: ScriptModel {
                        values: root.groups.map(g => g.key)
                    }

                    delegate: Item {
                        id: task
                        objectName: "dockTaskButton"
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button
                        Accessible.name: task.entry?.name ?? task.group?.app ?? ""
                        Accessible.onPressAction: task.activate(Qt.LeftButton)
                        Keys.onReturnPressed: task.activate(Qt.LeftButton)
                        Keys.onSpacePressed: task.activate(Qt.LeftButton)

                        required property string modelData

                        readonly property var group: root.groups.find(g => g.key === modelData) ?? ({key:modelData,app:modelData,windows:[],entry:null})
                        readonly property var windows: group?.windows ?? []
                        readonly property bool active: windows.some(w => w === Hypr.activeToplevel && !Hypr.isMinimized(w))
                        readonly property bool allMinimized: windows.length > 0 && windows.every(w => Hypr.isMinimized(w))
                        readonly property bool pinned: Taskbar.pinned.includes(group.key)
                        readonly property var entry: group?.entry
                        readonly property string iconSource: entry?.icon ? Quickshell.iconPath(entry.icon, true) : ""
                        readonly property bool hovered: taskMouse.containsMouse || popupOpen
                        readonly property bool popupOpen: root.menuOpen && root.menuTask === task

                        width: root.iconSize
                        height: root.iconSize
                        readonly property alias visual: taskVisual
                        readonly property real wave: waveSpring.value
                        MotionSpring {id:waveSpring;target:root.motionEnabled ? root.waveWeight(task) : 0;enabled:root.motionEnabled;stiffness:360;damping:DockConf.damping}
                        readonly property int minimizedCount: windows.filter(w=>Hypr.isMinimized(w)).length
                        property bool motionReady: false
                        property int previousMinimized: minimizedCount
                        property real impulseScale: 1
                        readonly property real visualScale: (1+(DockConf.magnification-1)*wave)*(GlobalConfig.appearance.reducedMotion?1:impulseScale)*((taskMouse.pressed&&!taskMouse.dragged)||(raisedInput.pressed && root.raisedPressTask===task && !raisedInput.dragged)?0.9:1)
                        property real accentPulse: 0
                        Component.onCompleted: Qt.callLater(()=>{previousMinimized=minimizedCount;motionReady=true;})
                        onMinimizedCountChanged: {
                            if(motionReady && DockConf.windowAnimations && !GlobalConfig.appearance.reducedMotion && Hypr.stacking) {
                                if(minimizedCount>previousMinimized) absorbDelay.restart(); else absorption.restart();
                            }
                            previousMinimized=minimizedCount;
                        }
                        Timer {id:absorbDelay;interval:DockConf.animationDuration*0.72;onTriggered:absorption.restart()}
                        ParallelAnimation {
                            id:absorption
                            NumberAnimation {target:task;property:"accentPulse";from:1;to:0;duration:360;easing.type:Easing.OutQuad}
                            SequentialAnimation {
                            ScriptAction {script:{root.absorptionCenter=task.mapToItem(root,task.width/2,task.height/2);membraneImpulse.restart();}}
                            NumberAnimation {target:task;property:"impulseScale";to:0.86;duration:65}
                            NumberAnimation {target:task;property:"impulseScale";to:1.12;duration:95;easing.type:Easing.OutQuad}
                            NumberAnimation {target:task;property:"impulseScale";to:1;duration:180;easing.type:Easing.OutCubic}
                            }
                        }
                        opacity: root.draggedKey === task.group.key && !root.externalDrag ? 0.35 : 1

                        Behavior on width {
                            Anim {}
                        }

                        Behavior on height {
                            Anim {}
                        }

                        function showMenu(): void {
                            root.closePopups();
                            root.menuTask = task;
                            root.menuOpen = true;
                            taskMenu.forceActiveFocus();
                        }

                        function act(operation: string, window: HyprlandToplevel): void {
                            root.reportTargets();
                            root.closeMenu();
                            Hypr.windowAction(operation, window);
                        }

                        function clickAction(): var {
                            const ordered = windows.slice().sort((a, b) =>
                                (a.lastIpcObject.focusHistoryID < 0 ? 100000 : a.lastIpcObject.focusHistoryID)
                                - (b.lastIpcObject.focusHistoryID < 0 ? 100000 : b.lastIpcObject.focusHistoryID));
                            const current = ordered.find(w => w === Hypr.activeToplevel && !Hypr.isMinimized(w));
                            return { operation: Hypr.stacking ? "task-click" : "dock-activate", window: current ?? ordered[0] };
                        }

                        function launch(): void {
                            root.closeMenu();
                            if (entry) Apps.launch(entry);
                        }

                        Item {
                            id:taskVisual
                            anchors.fill:parent
                            transform:[
                                Translate {x:root.vertical ? (DockConf.position==="left"?1:-1)*DockConf.lift*Tokens.scale*task.wave : 0;y:root.vertical ? 0 : (root.atBottom?-1:1)*DockConf.lift*Tokens.scale*task.wave},
                                Scale {origin.x:task.width/2;origin.y:task.height/2;xScale:task.visualScale;yScale:xScale}
                            ]
                        StyledRect {
                            anchors.fill: parent
                            transform:Scale {origin.x:task.width/2;origin.y:task.height/2;xScale:root.vertical?1+0.08*task.wave:1;yScale:root.vertical?1:1+0.08*task.wave}
                            radius: Tokens.rounding.large
                            color: task.active ? Colours.palette.m3primary
                                : task.hovered ? Qt.alpha(Colours.palette.m3onSurface, 0.12) : "transparent"

                            Behavior on color {
                                CAnim {}
                            }
                        }

                        Rectangle {
                            visible: root.draggedKey !== "" && root.dropKey === task.group.key
                            color: Colours.palette.m3primary
                            radius: Tokens.rounding.full
                            width: root.vertical ? parent.width : 3 * Tokens.scale
                            height: root.vertical ? 3 * Tokens.scale : parent.height
                            x: root.vertical || !root.dropAfter ? 0 : parent.width - width
                            y: !root.vertical || !root.dropAfter ? 0 : parent.height - height
                        }

                        Rectangle {
                            anchors.centerIn:parent
                            width:parent.width*(1+0.45*task.accentPulse);height:width;radius:width/2
                            color:task.active ? Colours.palette.m3onPrimary : Colours.palette.m3primary
                            opacity:GlobalConfig.appearance.reducedMotion ? 0 : task.accentPulse*0.22+task.wave*0.06
                        }

                        IconImage {
                            id: appIcon

                            anchors.centerIn: parent
                            implicitSize: Math.round(parent.width * 0.62)
                            visible: !!task.iconSource && status !== Image.Error
                            source: task.iconSource
                            opacity: task.allMinimized ? 0.55 : 1

                            Behavior on opacity {
                                NumberAnimation {
                                    duration: 180
                                }
                            }
                        }

                        Grid {
                            id: indicators
                            columns: root.vertical ? 1 : 4
                            spacing: 2 * Tokens.scale
                            x: root.vertical ? (DockConf.position === "left" ? parent.width - width : 0) : (parent.width - width) / 2
                            y: root.vertical ? (parent.height - height) / 2 : parent.height - height
                            move: Transition { Anim { properties: "x,y"; type: Anim.StandardSmall } }
                            Repeater {
                                model: 4
                                delegate: Item {
                                    id: indicator
                                    required property int index
                                    readonly property bool overflow: index === 3 && task.windows.length > 4
                                    readonly property color tint: task.active ? Colours.palette.m3onPrimary : Colours.palette.m3primary
                                    property bool initialized: false
                                    property real reveal: initialized && index < Math.min(4, task.windows.length) ? 1 : 0
                                    Component.onCompleted: Qt.callLater(() => initialized = true)
                                    width: (overflow ? 8 : 4) * Tokens.scale * reveal
                                    height: 5 * Tokens.scale * reveal
                                    opacity: reveal
                                    scale: 0.5 + reveal * 0.5
                                    visible: reveal > 0
                                    Behavior on reveal { Anim { type: Anim.FastSpatial } }
                                    Behavior on width { Anim { type: Anim.StandardSmall } }
                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 4 * Tokens.scale
                                        height: width
                                        radius: width / 2
                                        color: indicator.tint
                                        opacity: indicator.overflow ? 0 : 1
                                        visible: opacity > 0
                                        Behavior on opacity { Anim { type: Anim.DefaultEffects } }
                                        Behavior on color { CAnim {} }
                                    }
                                    StyledText {
                                        anchors.centerIn: parent
                                        text: "+"
                                        font.pixelSize: 11 * Tokens.scale
                                        color: indicator.tint
                                        opacity: indicator.overflow ? 1 : 0
                                        visible: opacity > 0
                                        Behavior on opacity { Anim { type: Anim.DefaultEffects } }
                                    }
                                }
                            }
                        }

                        MaterialIcon {
                            anchors.centerIn: parent
                            width: Math.round(parent.width * 0.62)
                            visible: !appIcon.visible
                            text: Icons.getAppCategoryIcon(task.entry?.id ?? task.modelData, "apps")
                            color: task.active ? Colours.palette.m3onPrimary : Colours.palette.m3onSurface
                            Behavior on color {
                                CAnim {}
                            }
                            opacity: task.allMinimized ? 0.55 : 1
                        }

                        }
                        function activate(button: int): void {
                                if (button === Qt.RightButton) {
                                    task.showMenu();
                                } else if (task.windows.length === 0) {
                                    task.launch();
                                } else if (button === Qt.MiddleButton) {
                                    const window = task.windows.find(w => w === Hypr.activeToplevel) ?? task.windows[0];
                                    task.act("close", window);
                                } else {
                                    const action = task.clickAction();
                                    if (action.window) {
                                        root.reportTargets();
                                        root.closeMenu();
                                        Hypr.windowAction(action.operation, action.window);
                                    }
                                }
                            }
                        MouseArea {
                            id: taskMouse
                            // Union the stable slot with the displayed icon. Qt
                            // scales its translation too; the old unscaled lift
                            // left the upper part of the raised icon unclickable.
                            // Keep the press-shrink inside a stable hitbox so a
                            // press near the edge cannot cancel its own click.
                            readonly property real hitScale: (1+(DockConf.magnification-1)*task.wave)*Math.max(1,task.impulseScale)
                            readonly property real lift: DockConf.lift*Tokens.scale*task.wave*hitScale
                            readonly property real dx:root.vertical ? (DockConf.position==="left"?1:-1)*lift : 0
                            readonly property real dy:root.vertical ? 0 : (root.atBottom?-1:1)*lift
                            readonly property real extraX:task.width*(hitScale-1)/2
                            readonly property real extraY:task.height*(hitScale-1)/2
                            x:Math.min(0,dx-extraX)
                            y:Math.min(0,dy-extraY)
                            width:Math.max(task.width,dx+task.width+extraX)-x
                            height:Math.max(task.height,dy+task.height+extraY)-y
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                            preventStealing: true
                            property point pressPoint
                            property bool dragged: false
                            onPressed: event => { pressPoint = taskMouse.mapToItem(root,event.x,event.y); dragged = false; }
                            onPositionChanged: event => {
                                if (!(pressedButtons & Qt.LeftButton)) return;
                                const position=taskMouse.mapToItem(root,event.x,event.y);
                                if (!dragged && Math.hypot(position.x - pressPoint.x, position.y - pressPoint.y) > 8 * Tokens.scale) {
                                    dragged = true;
                                    root.closePopups();
                                    root.draggedKey = task.group.key;
                                    root.dragIcon = task.iconSource;
                                }
                                if (dragged) root.updateDrag(position);
                            }
                            onReleased: if (dragged) root.finishDrag()
                            onCanceled: root.cancelDrag()

                            onClicked: event => { if (!dragged) task.activate(event.button); }
                            onWheel: event => {
                                if (task.windows.length === 0)
                                    return;
                                const current = task.windows.findIndex(w => w === Hypr.activeToplevel);
                                const next = (current + (event.angleDelta.y > 0 ? 1 : -1) + task.windows.length) % task.windows.length;
                                task.act("dock-activate", task.windows[next]);
                                event.accepted = true;
                            }
                        }


                    }
                }

                DockSeparator { visible: taskRepeater.count > 0 && DockConf.menuButtonPosition !== "start" }

                Loader {
                    id: endAppsButton
                    active: DockConf.menuButtonPosition !== "start"
                    visible: active
                    width: active ? root.iconSize : 0
                    height: width
                    sourceComponent: AppsButton {}
                }

            }
        }
    }

    // Same AppList and search control as the launcher, inside the drawer surface.
    Item {
        id: appList
        width: Math.min(root.listNaturalWidth, root.vertical ? root.screen.width - root.width - 32 * Tokens.scale : root.width)
        height: openProgress * naturalHeight
        readonly property real naturalHeight: Math.max(0, Math.min(root.screen.height * 0.6, 440 * Tokens.scale,
            root.vertical ? root.viewportHeight : root.atBottom ? root.y : root.viewportHeight - root.y - root.height))
        property real openProgress: root.listOpen && root.visible ? 1 : 0
        x: root.vertical ? (DockConf.position === "left" ? root.width : -width) : (root.width - width) / 2
        y: root.vertical ? (root.height - height) / 2 : (root.atBottom ? -height : root.height)
        visible: height > 0
        clip: true
        Behavior on openProgress { Anim { type: Anim.Emphasized } }
        Item {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: appList.naturalHeight
            opacity: appList.openProgress
            SearchBar {
                id: search
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: Tokens.padding.medium
                Keys.onEscapePressed: root.listOpen = false
                Keys.onUpPressed: apps.decrementCurrentIndex()
                Keys.onDownPressed: apps.incrementCurrentIndex()
                onAccepted: {
                    if (apps.currentItem?.modelData) {
                        Apps.launch(apps.currentItem.modelData);
                        root.listOpen = false;
                    }
                }
            }
            Launcher.AppList {
                id: apps
                search: search
                screenState: root.screenState
                active: root.listOpen
                appsOnly: true
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: search.top
                anchors.margins: Tokens.padding.medium
                clip: true
                onAppLaunched: root.listOpen = false
            }
        }
    }

    Item {
        id: taskMenu
        readonly property var selectedTask: root.menuTask ?? ({ entry: null, windows: [], group: {key: ""}, pinned: false })
        readonly property point buttonPoint: root.menuTask ? root.menuTask.mapToItem(root, 0, 0) : Qt.point(0, 0)
        readonly property real naturalWidth: Math.min(root.screen.width - 32 * Tokens.scale, 300 * Tokens.scale)
        readonly property real naturalHeight: Math.max(0, Math.min(menuColumn.implicitHeight + 24 * Tokens.scale,
            root.vertical ? root.viewportHeight : root.atBottom ? root.y : root.viewportHeight - root.y - root.height))
        property real progress: root.menuOpen && root.visible ? 1 : 0
        width: root.vertical ? naturalWidth * progress : Math.min(naturalWidth, root.width)
        height: naturalHeight * (root.vertical ? 1 : progress)
        x: root.vertical ? (DockConf.position === "left" ? root.width : -width)
            : root.width <= naturalWidth ? 0 : Math.max(-root.x, Math.min(root.maxWidth - root.x - width, buttonPoint.x + root.iconSize / 2 - width / 2))
        y: root.vertical ? Math.max(-root.y, Math.min(root.viewportHeight - root.y - height, buttonPoint.y + root.iconSize / 2 - height / 2))
            : root.atBottom ? -height : root.height
        visible: progress > 0
        clip: true
        focus: root.menuOpen
        Keys.onEscapePressed: root.closeMenu()
        Behavior on progress { Anim { type: Anim.Emphasized } }
        Flickable {
            anchors.fill: parent
            contentHeight: menuColumn.implicitHeight + 24 * Tokens.scale
            contentWidth: width
            clip: true
            opacity: taskMenu.progress
        Column {
            id: menuColumn

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 12 * Tokens.scale
            spacing: 4 * Tokens.scale

            StyledText {
                width: parent.width
                text: taskMenu.selectedTask.entry?.name ?? taskMenu.selectedTask.group?.app ?? taskMenu.selectedTask.modelData ?? ""
                elide: Text.ElideRight
                font: Tokens.font.body.medium
            }

            TaskMenuButton {
                width: parent.width
                visible: !!taskMenu.selectedTask.entry
                text: taskMenu.selectedTask.pinned ? Tr.tr("Unpin from dock") : Tr.tr("Pin to dock")
                onClicked: {
                    root.closeMenu();
                    Taskbar.togglePin(taskMenu.selectedTask.group.key);
                }
            }

            TaskMenuButton {
                width: parent.width
                visible: !!taskMenu.selectedTask.entry
                text: Tr.tr("Open new window")
                onClicked: taskMenu.selectedTask.launch()
            }

            Repeater {
                model: taskMenu.selectedTask.entry?.actions ?? []
                delegate: TaskMenuButton {
                    required property var modelData
                    width: menuColumn.width
                    text: modelData.name
                    onClicked: {
                        root.closeMenu();
                        modelData.execute();
                    }
                }
            }

            Repeater {
                model: ScriptModel {
                    values: taskMenu.selectedTask.windows
                }

                delegate: Column {
                    id: menuWindow
                    required property HyprlandToplevel modelData
                    width: menuColumn.width
                    spacing: 2 * Tokens.scale
                    TaskMenuButton {
                        width: parent.width
                        objectName: "dockWindowTitle"
                        text: menuWindow.modelData?.title ?? ""
                        onClicked: taskMenu.selectedTask.act("dock-activate", menuWindow.modelData)
                        onHoveredChanged: hovered ? root.hoverWindow(menuWindow.modelData) : root.leaveWindow(menuWindow.modelData)
                    }
                    Row {
                        spacing: 6 * Tokens.scale
                        TaskMenuButton {
                            width: (menuColumn.width - 6 * Tokens.scale) * 0.3
                            text: Tr.tr("Close")
                            onClicked: taskMenu.selectedTask.act("close", menuWindow.modelData)
                        }
                        TaskMenuButton {
                            width: (menuColumn.width - 6 * Tokens.scale) * 0.7
                            text: Tr.tr("Force quit")
                            onClicked: {
                                taskMenu.selectedTask.act("force-quit", menuWindow.modelData);
                            }
                        }
                    }
                }
            }
        }
        }
    }

    Item {
        id: windowPreview
        visible: root.menuOpen && !!root.previewWindow && taskMenu.visible && !(Presentation.privateOn(root.screen))
        width: Math.min(320 * Tokens.scale, root.screen.width - 32 * Tokens.scale)
        height: 200 * Tokens.scale
        // Overlap the menu edge so both surfaces form one continuous blob.
        x: taskMenu.x + taskMenu.width + width - 14 * Tokens.scale <= root.maxWidth - root.x
            ? taskMenu.x + taskMenu.width - 14 * Tokens.scale : taskMenu.x - width + 14 * Tokens.scale
        y: Math.max(-root.y, Math.min(root.viewportHeight - root.y - height, taskMenu.y))
        HoverHandler { onHoveredChanged: { if (hovered) previewReset.stop(); else if (!root.hoveredWindow) previewReset.restart(); } }
        Column {
            anchors.fill: parent
            anchors.margins: 18 * Tokens.scale
            spacing: 8 * Tokens.scale
            StyledText { width: parent.width; text: root.previewWindow?.title ?? ""; elide: Text.ElideRight; font: Tokens.font.body.small }
            StyledClippingRect {
                width: parent.width
                height: parent.height - 30 * Tokens.scale
                radius: Tokens.rounding.medium
                color: Colours.palette.m3surfaceContainerLowest
                clip: true
                Loader {
                    anchors.fill: parent
                    active: windowPreview.visible && !!root.previewWindow?.wayland
                    sourceComponent: ScreencopyView {
                        objectName: "dockWindowCapture"
                        captureSource: root.previewWindow?.wayland ?? null
                        live: true
                        constraintSize: Qt.size(320, 180)
                    }
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: taskMenu.selectedTask.act("dock-activate", root.previewWindow) }
            }
        }
    }

    component AppsButton: Item {
        id: gridButton
        objectName: "dockAppsButton"
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: Tr.tr("Applications")
        Accessible.onPressAction: gridButton.activate(Qt.LeftButton)
        Keys.onReturnPressed: gridButton.activate(Qt.LeftButton)
        Keys.onSpacePressed: gridButton.activate(Qt.LeftButton)
        readonly property bool hovered: gridMouse.containsMouse || root.listOpen
        readonly property var group: null
        readonly property var windows: []
        readonly property real impulseScale: Math.max(1, pressScale)
        readonly property real wave: waveSpring.value
        readonly property real hitScale: (1 + (DockConf.magnification - 1) * wave) * impulseScale
        property real pressScale: gridMouse.pressed || (raisedInput.pressed && root.raisedPressTask === gridButton) ? 0.85 : 1
        Behavior on pressScale { Anim { type: Anim.FastSpatial } }
        readonly property real visualScale: (1 + (DockConf.magnification - 1) * wave) * pressScale
        readonly property alias visual: gridVisual
        MotionSpring { id: waveSpring; target: root.motionEnabled ? root.waveWeight(gridButton) : 0; enabled: root.motionEnabled; stiffness: 360; damping: DockConf.damping }
        width: root.iconSize
        height: root.iconSize
        function activate(button: int): void {
            if (button === Qt.LeftButton) root.listOpen = !root.listOpen;
        }
        Item {
            id: gridVisual
            anchors.fill: parent
            transform: [
                Translate { x: root.vertical ? (DockConf.position === "left" ? 1 : -1) * DockConf.lift * Tokens.scale * gridButton.wave : 0; y: root.vertical ? 0 : (root.atBottom ? -1 : 1) * DockConf.lift * Tokens.scale * gridButton.wave },
                Scale { origin.x: gridButton.width / 2; origin.y: gridButton.height / 2; xScale: gridButton.visualScale; yScale: xScale }
            ]
            StyledRect {
                anchors.fill: parent
                transform: Scale { origin.x: gridButton.width / 2; origin.y: gridButton.height / 2; xScale: root.vertical ? 1 + 0.08 * gridButton.wave : 1; yScale: root.vertical ? 1 : 1 + 0.08 * gridButton.wave }
                radius: Tokens.rounding.large
                color: gridButton.hovered ? Qt.alpha(Colours.palette.m3primary, 0.12) : "transparent"
                Behavior on color { CAnim {} }
            }
            MaterialIcon {
                anchors.centerIn: parent
                text: "apps"
                color: Colours.palette.m3primary
                fontStyle: Tokens.font.icon.medium
            }
        }
        MouseArea {
            id: gridMouse
            // Keep both the original slot and the raised visual clickable.
            readonly property real lift: DockConf.lift * Tokens.scale * gridButton.wave * gridButton.hitScale
            readonly property real dx: root.vertical ? (DockConf.position === "left" ? 1 : -1) * lift : 0
            readonly property real dy: root.vertical ? 0 : (root.atBottom ? -1 : 1) * lift
            readonly property real extra: gridButton.width * (gridButton.hitScale - 1) / 2
            x: Math.min(0, dx - extra)
            y: Math.min(0, dy - extra)
            width: Math.max(gridButton.width, dx + gridButton.width + extra) - x
            height: Math.max(gridButton.height, dy + gridButton.height + extra) - y
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            acceptedButtons: Qt.LeftButton
            onClicked: gridButton.activate(Qt.LeftButton)
        }
    }

    component DockSeparator: Rectangle {
        width: root.vertical ? root.iconSize * 0.6 : Math.max(1, Math.round(Tokens.scale))
        height: root.vertical ? Math.max(1, Math.round(Tokens.scale)) : root.iconSize * 0.6
        radius: Tokens.rounding.full
        color: Colours.palette.m3outlineVariant
    }

    IconImage {
        visible: root.draggedKey !== ""
        x: root.dragPoint.x - width / 2
        y: root.dragPoint.y - height / 2
        width: root.iconSize
        height: width
        source: root.dragIcon
        opacity: 0.85
        z: 10
    }

    component TaskMenuButton: Rectangle {
        required property string text

        signal clicked
        readonly property bool hovered: click.containsMouse

        implicitHeight: 34 * Tokens.scale
        radius: Tokens.rounding.small
        color: click.containsMouse ? Colours.palette.m3surfaceContainerHigh : "transparent"

        StyledText {
            anchors.fill: parent
            anchors.leftMargin: 6 * Tokens.scale
            verticalAlignment: Text.AlignVCenter
            text: parent.text
            elide: Text.ElideRight
            font: Tokens.font.body.small
        }

        MouseArea {
            id: click

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.clicked()
        }
    }

}
