pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
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
    readonly property Item openSurface: appList.visible ? appList : taskMenu.visible ? taskMenu : null
    readonly property bool unifiedSurface: !vertical && openSurface !== null
        && Math.abs(openSurface.width - width) < 1 && Math.abs(openSurface.x) < 1
    property var menuTask: null
    property bool menuOpen: false
    function closeMenu(): void { menuOpen = false; }
    function closePopups(): void { listOpen = false; closeMenu(); }
    readonly property real offsetScale: 0

    readonly property real listNaturalWidth: 320 * Tokens.scale
    readonly property int popupGap: Math.round(8 * Tokens.scale)
    readonly property var appEntries: DesktopEntries.applications.values
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
            ?? DesktopEntries.heuristicLookup(app)
            ?? DesktopEntries.heuristicLookup(app.replace(/-browser$/, ""))
            ?? DesktopEntries.heuristicLookup(app.replace(/\.desktop$/, "").split(".").pop());
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
            const entry = DesktopEntries.byId(key) ?? lookup(key);
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
    onVisibleChanged: if (!visible) closePopups()
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
            anchors.fill: parent
            clip: true
            contentWidth: Math.max(width, taskRow.implicitWidth + Tokens.padding.small * 2)
            contentHeight: Math.max(height, taskRow.implicitHeight + Tokens.padding.small * 2)
            boundsBehavior: Flickable.StopAtBounds
            interactive: !root.draggedKey

            Grid {
                id: taskRow
                columns: root.vertical ? 1 : taskRepeater.count + 2

                x: Math.max(Tokens.padding.small, (taskScroll.width - width) / 2)
                y: Math.max(Tokens.padding.small, (taskScroll.height - height) / 2)
                spacing: Tokens.spacing.small
                move: Transition { Anim { properties: "x,y" } }

                Loader {
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
                        values: root.groups.map(g => g.app)
                    }

                    delegate: Item {
                        id: task

                        required property string modelData

                        readonly property var group: root.groups.find(g => g.app === modelData)
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
                        scale: taskMouse.pressed && !taskMouse.dragged ? 0.85 : 1
                        opacity: root.draggedKey === task.group.key && !root.externalDrag ? 0.35 : 1

                        Behavior on width {
                            Anim {}
                        }

                        Behavior on height {
                            Anim {}
                        }

                        Behavior on scale {
                            Anim {
                                type: Anim.FastSpatial
                            }
                        }

                        StyledRect {
                            anchors.fill: parent
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

                        function showMenu(): void {
                            root.listOpen = false;
                            root.menuTask = task;
                            root.menuOpen = true;
                            taskMenu.forceActiveFocus();
                        }

                        function act(operation: string, window: HyprlandToplevel): void {
                            root.closeMenu();
                            Hypr.windowAction(operation, window);
                        }

                        function clickAction(): var {
                            const ordered = windows.slice().sort((a, b) =>
                                (a.lastIpcObject.focusHistoryID < 0 ? 100000 : a.lastIpcObject.focusHistoryID)
                                - (b.lastIpcObject.focusHistoryID < 0 ? 100000 : b.lastIpcObject.focusHistoryID));
                            const current = ordered.find(w => w === Hypr.activeToplevel && !Hypr.isMinimized(w));
                            return { operation: "dock-activate", window: current ?? ordered[0] };
                        }

                        function launch(): void {
                            root.closeMenu();
                            if (entry) Apps.launch(entry);
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

                        MouseArea {
                            id: taskMouse

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                            preventStealing: true
                            property point pressPoint
                            property bool dragged: false
                            onPressed: event => { pressPoint = Qt.point(event.x, event.y); dragged = false; }
                            onPositionChanged: event => {
                                if (!(pressedButtons & Qt.LeftButton)) return;
                                if (!dragged && Math.hypot(event.x - pressPoint.x, event.y - pressPoint.y) > 8 * Tokens.scale) {
                                    dragged = true;
                                    root.closePopups();
                                    root.draggedKey = task.group.key;
                                    root.dragIcon = task.iconSource;
                                }
                                if (dragged) root.updateDrag(task.mapToItem(root, event.x, event.y));
                            }
                            onReleased: if (dragged) root.finishDrag()
                            onCanceled: root.cancelDrag()

                            onClicked: event => {
                                if (dragged) return;
                                if (event.button === Qt.RightButton) {
                                    task.showMenu();
                                } else if (task.windows.length === 0) {
                                    task.launch();
                                } else if (event.button === Qt.MiddleButton) {
                                    const window = task.windows.find(w => w === Hypr.activeToplevel) ?? task.windows[0];
                                    task.act("close", window);
                                } else {
                                    const action = task.clickAction();
                                    if (action.window) {
                                        root.closeMenu();
                                        Hypr.windowAction(action.operation, action.window);
                                    }
                                }
                            }
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
                text: taskMenu.selectedTask.entry?.name ?? taskMenu.selectedTask.modelData ?? ""
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
                    spacing: 4 * Tokens.scale

                    StyledText {
                        width: parent.width
                        text: menuWindow.modelData?.title ?? ""
                        elide: Text.ElideRight
                        font: Tokens.font.body.small
                        color: Colours.palette.m3onSurfaceVariant
                    }

                    Row {
                        spacing: 6 * Tokens.scale

                        WindowButton {
                            icon: "open_in_full"
                            onClicked: taskMenu.selectedTask.act("dock-activate", menuWindow.modelData)
                        }

                        WindowButton {
                            icon: "minimize"
                            onClicked: taskMenu.selectedTask.act("minimize", menuWindow.modelData)
                        }

                        WindowButton {
                            icon: Hypr.isMaximized(menuWindow.modelData) ? "filter_none" : "crop_square"
                            onClicked: taskMenu.selectedTask.act("maximize", menuWindow.modelData)
                        }

                        WindowButton {
                            icon: "close"
                            danger: true
                            onClicked: taskMenu.selectedTask.act("close", menuWindow.modelData)
                        }
                    }
                }
            }
        }
        }
    }

    component AppsButton: Item {
        id: gridButton

        readonly property bool hovered: gridMouse.containsMouse || root.listOpen

        width: root.iconSize
        height: root.iconSize
        scale: gridMouse.pressed ? 0.85 : 1

        Behavior on scale {
            Anim {
                type: Anim.FastSpatial
            }
        }

        StyledRect {
            anchors.fill: parent
            radius: Tokens.rounding.large
            color: gridButton.hovered ? Qt.alpha(Colours.palette.m3primary, 0.12) : "transparent"

            Behavior on color {
                CAnim {}
            }
        }

        MaterialIcon {
            anchors.centerIn: parent
            text: "apps"
            color: Colours.palette.m3primary
            fontStyle: Tokens.font.icon.medium
        }

        MouseArea {
            id: gridMouse

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            acceptedButtons: Qt.LeftButton

            onClicked: root.listOpen = !root.listOpen
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

        implicitHeight: 34 * Tokens.scale
        radius: Tokens.rounding.small
        color: click.containsMouse ? Colours.palette.m3surfaceContainerHigh : "transparent"

        StyledText {
            anchors.fill: parent
            anchors.leftMargin: 6 * Tokens.scale
            verticalAlignment: Text.AlignVCenter
            text: parent.text
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

    component WindowButton: Rectangle {
        required property string icon

        property bool danger

        signal clicked

        width: 38 * Tokens.scale
        height: 30 * Tokens.scale
        radius: Tokens.rounding.small
        color: buttonMouse.containsMouse ? Colours.palette.m3surfaceContainerHighest : "transparent"

        MaterialIcon {
            anchors.centerIn: parent
            text: parent.icon
            color: parent.danger ? Colours.palette.m3error : Colours.palette.m3onSurface
        }

        MouseArea {
            id: buttonMouse

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.clicked()
        }
    }
}
