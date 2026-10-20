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

    title: Tr.tr("Statusbar layout")

    property var leftWidgets: []
    property var centerWidgets: []
    property var rightWidgets: []

    function reloadZones(): void {
        const raw = GlobalConfig.bar.entries.values || [];
        const left = [];
        const center = [];
        const right = [];
        let zone = 0;
        for (let i = 0; i < raw.length; i++) {
            const item = raw[i];
            if (!item || !item.enabled) continue;
            if (item.id === "spacer") {
                if (zone < 2) zone++;
                continue;
            }
            if (zone === 0) left.push(item.id);
            else if (zone === 1) center.push(item.id);
            else right.push(item.id);
        }
        // Fallback to reasonable defaults if unconfigured
        if (left.length === 0 && center.length === 0 && right.length === 0) {
            left.push("logo", "workspaces");
            center.push("activeWindow");
            right.push("plugins", "tray", "clock", "statusIcons", "notifications", "power");
        }
        leftWidgets = left;
        centerWidgets = center;
        rightWidgets = right;
    }

    function saveZones(l: var, c: var, r: var): void {
        const list = GlobalConfig.bar.entries;
        list.clear();
        for (const id of l) list.insert({ id: id, enabled: true });
        list.insert({ id: "spacer", enabled: true });
        for (const id of c) list.insert({ id: id, enabled: true });
        list.insert({ id: "spacer", enabled: true });
        for (const id of r) list.insert({ id: id, enabled: true });
        reloadZones();
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
        if (target < 0 || target >= arr.length) return;
        arr.splice(target, 0, arr.splice(fromIndex, 1)[0]);
        saveZones(l, c, r);
    }

    function removeWidget(zoneIndex: int, itemIndex: int): void {
        const l = [...leftWidgets];
        const c = [...centerWidgets];
        const r = [...rightWidgets];
        if (zoneIndex === 0) l.splice(itemIndex, 1);
        else if (zoneIndex === 1) c.splice(itemIndex, 1);
        else r.splice(itemIndex, 1);
        saveZones(l, c, r);
    }

    function addWidget(zoneIndex: int, id: string): void {
        const l = [...leftWidgets];
        const c = [...centerWidgets];
        const r = [...rightWidgets];
        if (zoneIndex === 0) l.push(id);
        else if (zoneIndex === 1) c.push(id);
        else r.push(id);
        saveZones(l, c, r);
    }

    readonly property var allCatalogWidgets: [
        { id: "logo", icon: "apps", name: Tr.tr("Logo / App Menu"), desc: Tr.tr("Application launcher and system menu icon") },
        { id: "workspaces", icon: "workspaces", name: Tr.tr("Workspaces"), desc: Tr.tr("Workspace indicators and active window dots") },
        { id: "activeWindow", icon: "web_asset", name: Tr.tr("Active window"), desc: Tr.tr("Current focused window title and icon") },
        { id: "layoutSwitcher", icon: "view_carousel", name: Tr.tr("Window layout"), desc: Tr.tr("Switch tiling, scrolling, stacking and infinite canvas") },
        { id: "clock", icon: "schedule", name: Tr.tr("Clock & Date"), desc: Tr.tr("Current time, date, and calendar popout") },
        { id: "tray", icon: "widgets", name: Tr.tr("System Tray"), desc: Tr.tr("Background application icons and status menus") },
        { id: "statusIcons", icon: "signal_cellular_alt", name: Tr.tr("Status icons"), desc: Tr.tr("Network, Bluetooth, battery, and audio indicators") },
        { id: "notifications", icon: "notifications", name: Tr.tr("Notification Centre"), desc: Tr.tr("Notification drawer toggle and unread badge") },
        { id: "power", icon: "power_settings_new", name: Tr.tr("Power menu"), desc: Tr.tr("Lock, logout, restart, and power off button") },
        { id: "plugins", icon: "extension", name: Tr.tr("Plugin widgets"), desc: Tr.tr("Widgets provided by active Hyprstack plugins") }
    ]

    function widgetMeta(id: string): var {
        const found = allCatalogWidgets.find(w => w.id === id);
        if (found) return found;
        if (id.startsWith("plugin:")) {
            const pId = id.slice(7);
            const p = Plugins.byId(pId);
            return { id: id, icon: "extension", name: p?.name ?? pId, desc: Tr.tr("Plugin widget") };
        }
        return { id: id, icon: "widgets", name: id, desc: "" };
    }

    Component.onCompleted: reloadZones()

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.medium


        // Statusbar 3-column layout section
        SectionHeader {
            first: true
            text: Tr.tr("Statusbar layout")
        }

        StyledText {
            Layout.fillWidth: true
            font: Tokens.font.body.small
            color: Colours.palette.m3onSurfaceVariant
            wrapMode: Text.Wrap
            text: Tr.tr("Configure widgets across Left, Center, and Right zones. Move items between zones or reorder them.")
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small

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

        // Widget Catalog Section
        SectionHeader {
            text: Tr.tr("Widget catalog")
        }

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

                RowLayout {
                    id: catContent
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.medium
                    spacing: Tokens.spacing.medium

                    MaterialIcon {
                        text: catalogRow.modelData.icon
                        fontStyle: Tokens.font.icon.medium
                        color: Colours.palette.m3primary
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        StyledText {
                            text: catalogRow.modelData.name
                            font: Tokens.font.body.medium
                            color: Colours.palette.m3onSurface
                        }

                        StyledText {
                            text: catalogRow.modelData.desc
                            font: Tokens.font.label.small
                            color: Colours.palette.m3onSurfaceVariant
                        }
                    }

                    RowLayout {
                        spacing: Tokens.spacing.extraSmall

                        TextButton {
                            text: "+ " + Tr.tr("Left")
                            onClicked: root.addWidget(0, catalogRow.modelData.id)
                        }

                        TextButton {
                            text: "+ " + Tr.tr("Center")
                            onClicked: root.addWidget(1, catalogRow.modelData.id)
                        }

                        TextButton {
                            text: "+ " + Tr.tr("Right")
                            onClicked: root.addWidget(2, catalogRow.modelData.id)
                        }
                    }
                }
            }
        }


    }

    // ZoneColumn Component
    component ZoneColumn: StyledRect {
        id: zoneRoot
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

                Item { Layout.fillWidth: true }

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
                    required property var modelData
                    required property int index

                    readonly property var meta: root.widgetMeta(wCard.modelData)

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

                            Item { Layout.fillWidth: true }
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
