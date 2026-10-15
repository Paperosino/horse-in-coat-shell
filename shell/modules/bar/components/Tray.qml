pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Services.SystemTray
import Hyprstack.Config
import qs.components
import qs.services

StyledRect {
    id: root

    readonly property alias layout: layout
    readonly property alias items: items
    readonly property alias expandIcon: expandIcon

    readonly property int padding: Config.bar.tray.background ? Tokens.padding.medium : Tokens.padding.extraSmall
    readonly property int spacing: Config.bar.tray.background ? Tokens.spacing.medium : Tokens.spacing.extraSmall

    property bool expanded

    function redundant(item: var): bool {
        const id = item.id.toLowerCase();
        const status = Config.bar.statusIcons.values;
        if (/^(nm-applet|networkmanager(-applet)?)$/.test(id))
            return status.some(entry => entry.id === "network" && entry.enabled);
        if (/^(blueman(-applet|-tray)?)$/.test(id))
            return status.some(entry => entry.id === "bluetooth" && entry.enabled);
        return false;
    }

    readonly property real nonAnimWidth: {
        if (items.count === 0)
            return 0;
        if (!Config.bar.tray.compact)
            return layout.implicitWidth + padding * 2;
        const pad = (Config.bar.tray.background ? Tokens.padding.extraSmall : 0) + padding;
        if (expanded)
            return expandIcon.implicitWidth + layout.implicitWidth + spacing + pad;
        return Math.max(Config.bar.tray.background ? height : 0, expandIcon.implicitWidth + pad);
    }

    clip: true
    visible: width > 0

    implicitWidth: nonAnimWidth
    implicitHeight: Tokens.sizes.bar.innerWidth

    color: "transparent"
    radius: Tokens.rounding.full

    GroupBackground {
        color: Qt.alpha(Colours.tPalette.m3surfaceContainer, (Config.bar.tray.background && root.items.count > 0) ? Colours.tPalette.m3surfaceContainer.a : 0)
    }

    Row {
        id: layout

        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: root.padding
        spacing: Tokens.spacing.small

        opacity: root.expanded || !Config.bar.tray.compact ? 1 : 0

        add: Transition {
            Anim {
                properties: "scale"
                from: 0
                to: 1
                easing: Tokens.anim.standardDecel
            }
        }

        move: Transition {
            Anim {
                properties: "scale"
                to: 1
                easing: Tokens.anim.standardDecel
            }
            Anim {
                properties: "x,y"
            }
        }

        Repeater {
            id: items

            model: ScriptModel {
                values: SystemTray.items.values.filter(i => i.status !== Status.Passive && !GlobalConfig.bar.tray.hiddenIcons.includes(i.id) && !root.redundant(i))
            }

            TrayItem {}
        }

        Behavior on opacity {
            Anim {
                type: Anim.DefaultEffects
            }
        }
    }

    Loader {
        id: expandIcon

        asynchronous: true

        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: root.padding

        active: Config.bar.tray.compact && items.count > 0

        sourceComponent: Item {
            implicitWidth: expandIconInner.implicitWidth
            implicitHeight: expandIconInner.implicitHeight

            MaterialIcon {
                id: expandIconInner

                anchors.centerIn: parent
                text: "chevron_left"
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.medium
                rotation: root.expanded ? 180 : 0

                Behavior on rotation {
                    Anim {}
                }

            }
        }
    }

    Behavior on implicitWidth {
        Anim {}
    }
}
