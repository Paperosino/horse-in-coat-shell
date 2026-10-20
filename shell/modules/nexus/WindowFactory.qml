pragma Singleton

import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus

Singleton {
    id: root

    function openPage(id: string): void { create(null, {pageId: id}); }

    function create(parent: Item, props: var): void {
        nexusComp.createObject(parent ?? dummy, props);
    }

    QtObject {
        id: dummy
    }

    Component {
        id: nexusComp

        FloatingWindow {
            id: win

            property string pageId: ""

            color: Colours.tPalette.m3surface
            surfaceFormat.opaque: false

            onVisibleChanged: {
                if (!visible)
                    destroy();
            }

            implicitWidth: nexus.implicitWidth
            implicitHeight: nexus.implicitHeight

            minimumSize.width: Math.min(contentItem.Tokens.sizes.nexus.minWidth, nexus.availableWidth)
            minimumSize.height: Math.min(contentItem.Tokens.sizes.nexus.minHeight, nexus.availableHeight)

            contentItem.Config.screen: screen.name
            contentItem.Tokens.screen: screen.name

            title: Tr.tr("Nexus — %1").arg(PageRegistry.pages[nexus.nState.currentPageIdx].label)

            Nexus {
                id: nexus

                anchors.fill: parent
                nState.screen: win.screen
                nState.isWindow: true
                Component.onCompleted: if (win.pageId) {
                    const route = PageRegistry.route(win.pageId);
                    nState.currentPageIdx = Math.max(0, PageRegistry.indexOf(route.id));
                    if (route.subPage !== undefined) nState.subPageIdxStack = [route.subPage];
                }
                onClose: win.destroy()
            }

            Behavior on color {
                CAnim {}
            }
        }
    }
}
