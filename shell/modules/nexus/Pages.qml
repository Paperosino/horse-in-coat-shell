import QtQuick
import Hyprstack.Config
import qs.components
import qs.modules.nexus
import qs.modules.nexus.pages

Item {
    id: root
    required property NexusState nState
    property int generation: 0
    property bool loadScheduled: false
    function requestPage(): void {
        if (loadScheduled) return;
        loadScheduled = true;
        Qt.callLater(() => {
            root.loadScheduled = false;
            root.loadPage(root.nState.currentPageIdx);
        });
    }
    property Item currentItem
    function loadPage(idx: int): void {
        // Commit the active editor before constructing a page which may read it.
        container.forceActiveFocus();
        const request = ++generation;
        const component = nState.showingSection ? sectionComponent : (PageCompRegistry.pageComps[idx] ?? PageCompRegistry.placeholderComp);
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
            movement.y = GlobalConfig.appearance.reducedMotion ? 0 : nState.navigationDirection * 12 * Tokens.scale;
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
    Component { id: sectionComponent; SettingsOverview {} }
    Item {
        id: container
        objectName: "PageContainer"
        anchors.fill: parent
        transform: Translate {
            id: movement
        }
        Component.onCompleted: root.requestPage()
    }
    Connections {
        target: root.nState
        function onCurrentPageIdxChanged(): void {
            root.requestPage();
        }
        function onShowingSectionChanged(): void { root.requestPage(); }
        function onSectionIdChanged(): void { if(root.nState.showingSection) root.requestPage(); }
        function onSearchRequested(): void {
            root.requestPage();
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
