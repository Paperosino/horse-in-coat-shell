import QtQuick
import Hyprstack.Config
import qs.components
import qs.modules.nexus

Item {
    id: root
    required property NexusState nState
    property int lastPageIdx: nState.currentPageIdx
    property int generation: 0
    property Item currentItem
    function loadPage(idx: int): void {
        // Commit the active editor before constructing a page which may read it.
        container.forceActiveFocus();
        const request = ++generation;
        const component = PageCompRegistry.pageComps[idx] ?? PageCompRegistry.placeholderComp;
        const incubator = component.incubateObject(container, {
            nState
        });
        const attach = () => {
            if (request !== root.generation) {
                incubator.object.destroy();
                return;
            }
            const previous = currentItem;
            incubator.object.anchors.fill = container;
            currentItem = incubator.object;
            if (previous)
                previous.destroy();
            entrance.stop();
            container.opacity = GlobalConfig.appearance.reducedMotion ? 1 : 0;
            movement.y = GlobalConfig.appearance.reducedMotion ? 0 : (idx >= lastPageIdx ? 1 : -1) * 12 * Tokens.scale;
            lastPageIdx = idx;
            entrance.restart();
        };
        if (incubator.status === Component.Ready)
            attach();
        else
            incubator.onStatusChanged = status => {
                if (status === Component.Ready)
                    attach();
            };
    }
    Item {
        id: container
        objectName: "PageContainer"
        anchors.fill: parent
        transform: Translate {
            id: movement
        }
        Component.onCompleted: root.loadPage(root.nState.currentPageIdx)
    }
    Connections {
        target: root.nState
        function onCurrentPageIdxChanged(): void {
            root.loadPage(root.nState.currentPageIdx);
        }
        function onSearchRequested(): void {
            root.loadPage(root.nState.currentPageIdx);
        }
    }
    ParallelAnimation {
        id: entrance
        Anim {
            target: container
            property: "opacity"
            to: 1
            type: Anim.FastEffects
        }
        Anim {
            target: movement
            property: "y"
            to: 0
            type: Anim.FastSpatial
        }
    }
}
