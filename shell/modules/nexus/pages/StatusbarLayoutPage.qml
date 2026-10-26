pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "view_week"

    title: Tr.tr("Statusbar layout")

    property string panelId: nState.requestedPanelId
    property string editedScreen: ""
    property string selectedScreen: Screens.screens[0]?.name ?? ""
    readonly property var selectedPanel: ExtraPanels.panels.find(p=>p.id===panelId)??null
    readonly property QtObject panelLayer: QtObject { Config.screen:root.panelId?"panel-"+root.panelId:(Screens.screens[0]?.name??"default");readonly property var bar:Config.bar }
    readonly property var editedBar: panelId ? panelLayer.bar : editedScreen ? GlobalConfig.forScreen(editedScreen).bar : GlobalConfig.bar
    onEditedBarChanged: Qt.callLater(reloadZones)
    readonly property Connections panelChanges: Connections {target:ExtraPanels;function onPanelsChanged():void {if(root.panelId&&!root.selectedPanel)root.panelId="";}}
    property var leftWidgets: []
    property var centerWidgets: []
    property var rightWidgets: []

    function reloadZones(): void {
        const raw = root.editedBar.entries.values || [];
        const left = [];
        const center = [];
        const right = [];
        let zone = 0;
        for (let i = 0; i < raw.length; i++) {
            const item = raw[i];
            if (!item || !item.enabled)
                continue;
            if (item.id === "spacer") {
                if (zone < 2)
                    zone++;
                continue;
            }
            if (zone === 0)
                left.push(item.id);
            else if (zone === 1)
                center.push(item.id);
            else
                right.push(item.id);
        }
        leftWidgets = left;
        centerWidgets = center;
        rightWidgets = right;
    }

    function saveZones(l: var, c: var, r: var): void {
        const list = root.editedBar.entries;
        list.clear();
        for (const id of l)
            list.insert({
                id: id,
                enabled: true
            });
        list.insert({
            id: "spacer",
            enabled: true
        });
        for (const id of c)
            list.insert({
                id: id,
                enabled: true
            });
        list.insert({
            id: "spacer",
            enabled: true
        });
        for (const id of r)
            list.insert({
                id: id,
                enabled: true
            });
        // Explicit disabled entries prevent automatic compatibility insertion
        // from resurrecting a widget the user deliberately removed.
        const active = new Set([...l, ...c, ...r]);
        for (const widget of allCatalogWidgets)
            if (!active.has(widget.id)) list.insert({id: widget.id, enabled: false});
        root.editedBar.showNotifications = active.has("notifications");
        reloadZones();
    }

    property var draggedWidget: null
    property bool dragActive: false
    property point dragPosition: Qt.point(0,0)
    readonly property StyledRect dragProxy: StyledRect {
        parent: root.QsWindow.window?.contentItem ?? root
        z:10000
        visible:root.dragActive
        width:160*Tokens.scale;height:44*Tokens.scale;radius:Tokens.rounding.large
        color:Colours.palette.m3primaryContainer
        readonly property point cursor: parent.mapFromItem(null,root.dragPosition.x,root.dragPosition.y)
        x:cursor.x-width/2;y:cursor.y-height/2
        Drag.active:root.dragActive
        Drag.keys:["hics-panel-widget"]
        Drag.source:dragProxy
        Drag.supportedActions:Qt.MoveAction
        Drag.hotSpot.x:width/2;Drag.hotSpot.y:height/2
        StyledText {anchors.centerIn:parent;text:root.draggedWidget?root.widgetMeta(root.draggedWidget.id).name:"";color:Colours.palette.m3onPrimaryContainer}
    }
    function dropWidget(zone: int, index: int): void {
        const source = draggedWidget;
        draggedWidget = null;
        if (!source) return;
        const zones = [[...leftWidgets],[...centerWidgets],[...rightWidgets]];
        if (!zones[source.zone] || zones[source.zone][source.index] !== source.id || !zones[zone]) return;
        const value=zones[source.zone].splice(source.index,1)[0];
        if(source.zone===zone && source.index<index)index--;
        zones[zone].splice(Math.max(0,Math.min(index,zones[zone].length)),0,value);
        saveZones(zones[0],zones[1],zones[2]);
    }
    function moveLeft(zoneIndex: int, itemIndex: int): void {
        const l = [...leftWidgets];
        const c = [...centerWidgets];
        const r = [...rightWidgets];
        if (zoneIndex === 1) { // Center -> Left
            const it = c.splice(itemIndex, 1)[0];
            l.push(it);
        } else if (zoneIndex === 2) { // Right -> Center
            const it = r.splice(itemIndex, 1)[0];
            c.push(it);
        }
        saveZones(l, c, r);
    }

    function moveRight(zoneIndex: int, itemIndex: int): void {
        const l = [...leftWidgets];
        const c = [...centerWidgets];
        const r = [...rightWidgets];
        if (zoneIndex === 0) { // Left -> Center
            const it = l.splice(itemIndex, 1)[0];
            c.push(it);
        } else if (zoneIndex === 1) { // Center -> Right
            const it = c.splice(itemIndex, 1)[0];
            r.push(it);
        }
        saveZones(l, c, r);
    }

    function reorder(zoneIndex: int, fromIndex: int, delta: int): void {
        const l = [...leftWidgets];
        const c = [...centerWidgets];
        const r = [...rightWidgets];
        const arr = zoneIndex === 0 ? l : zoneIndex === 1 ? c : r;
        const target = fromIndex + delta;
        if (target < 0 || target >= arr.length)
            return;
        arr.splice(target, 0, arr.splice(fromIndex, 1)[0]);
        saveZones(l, c, r);
    }

    function removeWidget(zoneIndex: int, itemIndex: int): void {
        const l = [...leftWidgets];
        const c = [...centerWidgets];
        const r = [...rightWidgets];
        if (zoneIndex === 0)
            l.splice(itemIndex, 1);
        else if (zoneIndex === 1)
            c.splice(itemIndex, 1);
        else
            r.splice(itemIndex, 1);
        saveZones(l, c, r);
    }

    function addWidget(zoneIndex: int, id: string): void {
        const l = leftWidgets.filter(value => value !== id);
        const c = centerWidgets.filter(value => value !== id);
        const r = rightWidgets.filter(value => value !== id);
        if (zoneIndex === 0)
            l.push(id);
        else if (zoneIndex === 1)
            c.push(id);
        else if (zoneIndex === 2)
            r.push(id);
        saveZones(l, c, r);
    }

    function widgetZone(id: string): int {
        return leftWidgets.includes(id) ? 0 : centerWidgets.includes(id) ? 1 : rightWidgets.includes(id) ? 2 : -1;
    }

    readonly property var allCatalogWidgets: [
        {
            id: "logo",
            icon: "apps",
            name: Tr.tr("Logo / App Menu"),
            desc: Tr.tr("Application launcher and system menu icon")
        },
        {
            id: "workspaces",
            icon: "workspaces",
            name: Tr.tr("Workspaces"),
            desc: Tr.tr("Workspace indicators and active window dots")
        },
        {
            id: "activeWindow",
            icon: "web_asset",
            name: Tr.tr("Active window"),
            desc: Tr.tr("Current focused window title and icon")
        },
        {
            id: "layoutSwitcher",
            icon: "view_carousel",
            name: Tr.tr("Window layout"),
            desc: Tr.tr("Switch tiling, scrolling, stacking and infinite canvas")
        },
        {
            id: "clock",
            icon: "schedule",
            name: Tr.tr("Clock & Date"),
            desc: Tr.tr("Current time, date, and calendar popout")
        },
        {
            id: "tray",
            icon: "widgets",
            name: Tr.tr("System Tray"),
            desc: Tr.tr("Background application icons and status menus")
        },
        {
            id: "statusIcons",
            icon: "signal_cellular_alt",
            name: Tr.tr("Status icons"),
            desc: Tr.tr("Network, Bluetooth, battery, and audio indicators")
        },
        {
            id: "notifications",
            icon: "notifications",
            name: Tr.tr("Notification Centre"),
            desc: Tr.tr("Notification drawer toggle and unread badge")
        },
        {
            id: "power",
            icon: "power_settings_new",
            name: Tr.tr("Power menu"),
            desc: Tr.tr("Lock, logout, restart, and power off button")
        },
        {
            id: "plugins",
            icon: "extension",
            name: Tr.tr("Plugin widgets"),
            desc: Tr.tr("Widgets provided by active Hyprstack plugins")
        }
    ]

    function widgetMeta(id: string): var {
        const found = allCatalogWidgets.find(w => w.id === id);
        if (found)
            return found;
        if (id.startsWith("plugin:")) {
            const pId = id.slice(7);
            const p = Plugins.byId(pId);
            return {
                id: id,
                icon: "extension",
                name: p?.name ?? pId,
                desc: Tr.tr("Plugin widget")
            };
        }
        return {
            id: id,
            icon: "widgets",
            name: id,
            desc: ""
        };
    }

    Component.onCompleted: { if (panelId && !selectedPanel) panelId = ""; reloadZones(); }

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.medium

        SettingsCard {
            title:Tr.tr("Panels and monitors")
            description:Tr.tr("Each additional panel has its own widgets, position, size and visibility. The main panel remains available.")
            icon:"view_quilt"
            FeatureError {error:ExtraPanels.error}
            GenericSettingRow {spec:({type:"choice",label:"Monitor for a new panel",choices:Screens.screens.map(s=>s.name),value:root.selectedScreen});onEdited:value=>root.selectedScreen=value}
            RowButton {text:Tr.tr("Add panel");icon:"add";disabled:ExtraPanels.busy||!root.selectedScreen;onClicked:ExtraPanels.add(root.selectedScreen)}
            GenericSettingRow {
                visible: !root.panelId
                spec: ({type:"choice",label:"Main panel monitor",value:root.editedScreen,
                    choices:[{value:"",label:"All screens"}].concat(Screens.screens.map(screen=>({value:screen.name,label:screen.name})))})
                onEdited: value => root.editedScreen = value
            }
            RowButton {text:Tr.tr("Main panel");icon:"view_week";trailingIcon:root.panelId?"chevron_right":"check";onClicked:root.panelId=""}
            Repeater {
                model:ExtraPanels.panels
                RowButton {
                    required property var modelData
                    text:modelData.name+" · "+modelData.screen+" · "+modelData.edge
                    icon:"view_week";trailingIcon:root.panelId===modelData.id?"check":"chevron_right"
                    onClicked:root.panelId=modelData.id
                }
            }
            ColumnLayout {
                visible:!!root.selectedPanel
                Layout.fillWidth:true
                TextFieldRow {label:Tr.tr("Panel name");value:root.selectedPanel?.name??"";onEditingFinished:value=>ExtraPanels.update(root.panelId,{name:value})}
                GenericSettingRow {spec:({type:"choice",label:"Panel position",choices:[{value:"top",label:"Top"},{value:"bottom",label:"Bottom"}],value:root.selectedPanel?.edge??"bottom"});onEdited:value=>ExtraPanels.update(root.panelId,{edge:value})}
                GenericSettingRow {spec:({type:"choice",label:"Panel monitor",choices:Screens.screens.map(s=>s.name),value:root.selectedPanel?.screen??root.selectedScreen});onEdited:value=>ExtraPanels.update(root.panelId,{screen:value})}
                StepperRow {label:Tr.tr("Panel thickness");from:28;to:96;value:root.selectedPanel?.thickness??48;onMoved:value=>ExtraPanels.update(root.panelId,{thickness:value})}
                ToggleRow {text:Tr.tr("Auto-hide panel");checked:root.selectedPanel?.autoHide??false;onToggled:ExtraPanels.update(root.panelId,{autoHide:checked})}
                StepperRow {label:Tr.tr("Hide delay (milliseconds)");from:100;to:3000;stepSize:100;value:root.selectedPanel?.hideDelay??500;onMoved:value=>ExtraPanels.update(root.panelId,{hideDelay:value})}
                RowButton {text:Tr.tr("Remove panel");icon:"delete";onClicked:ExtraPanels.remove(root.panelId)}
            }
            Repeater {
                model:ExtraPanels.removed
                RowButton {required property var modelData;text:Tr.tr("Restore removed panel")+" · "+modelData.name;icon:"undo";onClicked:ExtraPanels.restore(modelData.id)}
            }
        }
        // Statusbar 3-column layout section
        SettingsCard {
            title: Tr.tr("Statusbar layout")
            icon: "tune"

            StyledText {
                Layout.fillWidth: true
                font: Tokens.font.body.small
                color: Colours.palette.m3onSurfaceVariant
                wrapMode: Text.Wrap
                text: Tr.tr("Configure widgets across Left, Center, and Right zones. Move items between zones or reorder them.")
            }

            GridLayout {
                Layout.fillWidth: true
                columns: width < 760 * Tokens.scale ? 1 : 3
                columnSpacing: Tokens.spacing.small
                rowSpacing: Tokens.spacing.small

                // 1. LEFT COLUMN
                ZoneColumn {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignTop
                    zoneTitle: Tr.tr("Left")
                    zoneIcon: "format_align_left"
                    zoneIndex: 0
                    widgets: root.leftWidgets
                    onMoveLeft: (zi, ii) => root.moveLeft(zi, ii)
                    onMoveRight: (zi, ii) => root.moveRight(zi, ii)
                    onReorder: (zi, ii, d) => root.reorder(zi, ii, d)
                    onRemoveWidget: (zi, ii) => root.removeWidget(zi, ii)
                }

                // 2. CENTER COLUMN
                ZoneColumn {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignTop
                    zoneTitle: Tr.tr("Center")
                    zoneIcon: "format_align_center"
                    zoneIndex: 1
                    widgets: root.centerWidgets
                    onMoveLeft: (zi, ii) => root.moveLeft(zi, ii)
                    onMoveRight: (zi, ii) => root.moveRight(zi, ii)
                    onReorder: (zi, ii, d) => root.reorder(zi, ii, d)
                    onRemoveWidget: (zi, ii) => root.removeWidget(zi, ii)
                }

                // 3. RIGHT COLUMN
                ZoneColumn {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.minimumWidth: 0
                    Layout.alignment: Qt.AlignTop
                    zoneTitle: Tr.tr("Right")
                    zoneIcon: "format_align_right"
                    zoneIndex: 2
                    widgets: root.rightWidgets
                    onMoveLeft: (zi, ii) => root.moveLeft(zi, ii)
                    onMoveRight: (zi, ii) => root.moveRight(zi, ii)
                    onReorder: (zi, ii, d) => root.reorder(zi, ii, d)
                    onRemoveWidget: (zi, ii) => root.removeWidget(zi, ii)
                }
            }

            StepperRow {
                label: Tr.tr("Panel scale (%)")
                subtext: Tr.tr("Resize panel icons, text and spacing without changing other interface elements")
                from: 65; to: 150; stepSize: 5
                value: Math.round(root.editedBar.scale * 100)
                onMoved: value => root.editedBar.scale = value / 100
            }

            // Widget Catalog Section
        }
        SettingsCard {
            title: Tr.tr("Widget catalog")
            icon: "tune"

            StyledText {
                Layout.fillWidth: true
                font: Tokens.font.body.small
                color: Colours.palette.m3onSurfaceVariant
                wrapMode: Text.Wrap
                text: Tr.tr("Add available widgets to any zone of the statusbar:")
            }

            Repeater {
                model: root.allCatalogWidgets
                delegate: StyledRect {
                    id: catalogRow
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: catContent.implicitHeight + Tokens.padding.medium * 2
                    radius: Tokens.rounding.medium
                    color: Colours.palette.m3surfaceContainer

                    GridLayout {
                        id: catContent
                        columns: width < 560 * Tokens.scale ? 1 : 2
                        columnSpacing: Tokens.spacing.medium
                        rowSpacing: Tokens.spacing.small
                        anchors.fill: parent
                        anchors.margins: Tokens.padding.medium

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            MaterialIcon {
                                text: catalogRow.modelData.icon
                                fontStyle: Tokens.font.icon.medium
                                color: Colours.palette.m3primary
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                StyledText {
                                    Layout.fillWidth: true
                                    text: catalogRow.modelData.name
                                    font: Tokens.font.body.medium
                                    wrapMode: Text.Wrap
                                }
                                StyledText {
                                    Layout.fillWidth: true
                                    text: catalogRow.modelData.desc
                                    font: Tokens.font.label.small
                                    color: Colours.palette.m3onSurfaceVariant
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                        GenericSettingRow {
                            Layout.preferredWidth: 190 * Tokens.scale
                            Layout.maximumWidth: 220 * Tokens.scale
                            spec: ({type:"choice", label:"Position", value:root.widgetZone(catalogRow.modelData.id), choices:[
                                {value:-1,label:"Not on panel"}, {value:0,label:"Left"},
                                {value:1,label:"Center"}, {value:2,label:"Right"}]})
                            onEdited: value => root.addWidget(Number(value), catalogRow.modelData.id)
                        }
                    }
                }
            }
        }
    }

    // ZoneColumn Component
    component ZoneColumn: StyledRect {
        id: zoneRoot
        objectName:"panelZone-"+zoneIndex
        required property string zoneTitle
        required property string zoneIcon
        required property int zoneIndex
        required property var widgets

        signal moveLeft(int zoneIndex, int itemIndex)
        signal moveRight(int zoneIndex, int itemIndex)
        signal reorder(int zoneIndex, int itemIndex, int delta)
        signal removeWidget(int zoneIndex, int itemIndex)

        radius: Tokens.rounding.large
        clip: true
        color: Colours.palette.m3surfaceContainerLowest
        implicitHeight: colContent.implicitHeight + Tokens.padding.medium * 2
        DropArea {
            anchors.fill:parent
            keys:["hics-panel-widget"]
            onDropped: drop => { root.dropWidget(zoneRoot.zoneIndex,zoneRoot.widgets.length);drop.acceptProposedAction(); }
        }

        ColumnLayout {
            id: colContent
            anchors.fill: parent
            anchors.margins: Tokens.padding.medium
            spacing: Tokens.spacing.small

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall

                MaterialIcon {
                    text: zoneRoot.zoneIcon
                    fontStyle: Tokens.font.icon.small
                    color: Colours.palette.m3primary
                }

                StyledText {
                    text: zoneRoot.zoneTitle
                    font: Tokens.font.title.small
                    color: Colours.palette.m3onSurface
                }

                Item {
                    Layout.fillWidth: true
                }

                StyledRect {
                    implicitWidth: countText.implicitWidth + 12
                    implicitHeight: countText.implicitHeight + 4
                    radius: Tokens.rounding.full
                    color: Colours.palette.m3surfaceContainerHigh

                    StyledText {
                        id: countText
                        anchors.centerIn: parent
                        text: String(zoneRoot.widgets.length)
                        font: Tokens.font.label.small
                        color: Colours.palette.m3onSurfaceVariant
                    }
                }
            }

            // Widget List
            Repeater {
                model: zoneRoot.widgets
                delegate: StyledRect {
                    id: wCard
                    objectName:"panelWidget-"+zoneRoot.zoneIndex+"-"+modelData
                    required property var modelData
                    required property int index

                    readonly property var meta: root.widgetMeta(wCard.modelData)
                    opacity: dragHandle.active ? 0.55 : 1
                    DragHandler {
                        id: dragHandle
                        target:null
                        onTranslationChanged: if(active)root.dragPosition=centroid.scenePosition
                        onActiveChanged: {
                            if(active){root.dragPosition=centroid.scenePosition;root.draggedWidget={zone:zoneRoot.zoneIndex,index:wCard.index,id:wCard.modelData};root.dragActive=true;}
                            else {root.dragProxy.Drag.drop();root.dragActive=false;root.draggedWidget=null;}
                        }
                    }
                    DropArea {
                        anchors.fill:parent
                        keys:["hics-panel-widget"]
                        onDropped: drop => {root.dropWidget(zoneRoot.zoneIndex,wCard.index);drop.acceptProposedAction();}
                    }

                    Layout.fillWidth: true
                    implicitHeight: cardCol.implicitHeight + Tokens.padding.small * 2
                    radius: Tokens.rounding.medium
                    color: Colours.palette.m3surfaceContainer

                    ColumnLayout {
                        id: cardCol
                        anchors.fill: parent
                        anchors.margins: Tokens.padding.small
                        spacing: Tokens.spacing.extraSmall

                        // Row 1: Icon + Name + Remove Button
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Tokens.spacing.extraSmall

                            MaterialIcon {
                                text: wCard.meta.icon
                                fontStyle: Tokens.font.icon.small
                                color: Colours.palette.m3primary
                            }

                            StyledText {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                text: wCard.meta.name
                                font: Tokens.font.body.small
                                elide: Text.ElideRight
                                color: Colours.palette.m3onSurface
                            }

                            IconButton {
                                icon: "close"
                                onClicked: zoneRoot.removeWidget(zoneRoot.zoneIndex, wCard.index)
                            }
                        }

                        // Row 2: Navigation & Reorder Buttons
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Tokens.spacing.extraSmall

                            // Move Left
                            IconButton {
                                icon: "arrow_back"
                                disabled: zoneRoot.zoneIndex <= 0
                                opacity: zoneRoot.zoneIndex > 0 ? 1 : 0.25
                                onClicked: zoneRoot.moveLeft(zoneRoot.zoneIndex, wCard.index)
                            }

                            // Reorder Up
                            IconButton {
                                icon: "arrow_upward"
                                disabled: wCard.index <= 0
                                opacity: wCard.index > 0 ? 1 : 0.25
                                onClicked: zoneRoot.reorder(zoneRoot.zoneIndex, wCard.index, -1)
                            }

                            // Reorder Down
                            IconButton {
                                icon: "arrow_downward"
                                disabled: wCard.index >= zoneRoot.widgets.length - 1
                                opacity: wCard.index < zoneRoot.widgets.length - 1 ? 1 : 0.25
                                onClicked: zoneRoot.reorder(zoneRoot.zoneIndex, wCard.index, 1)
                            }

                            // Move Right
                            IconButton {
                                icon: "arrow_forward"
                                disabled: zoneRoot.zoneIndex >= 2
                                opacity: zoneRoot.zoneIndex < 2 ? 1 : 0.25
                                onClicked: zoneRoot.moveRight(zoneRoot.zoneIndex, wCard.index)
                            }

                            Item {
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }

            // Empty placeholder
            StyledText {
                visible: zoneRoot.widgets.length === 0
                Layout.fillWidth: true
                Layout.topMargin: Tokens.spacing.medium
                Layout.bottomMargin: Tokens.spacing.medium
                horizontalAlignment: Text.AlignHCenter
                text: Tr.tr("Zone is empty")
                font: Tokens.font.body.small
                color: Colours.palette.m3outline
            }
        }
    }
}
