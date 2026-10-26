import QtQuick
import Quickshell
import Quickshell.Bluetooth
import qs.modules.nexus

QtObject {
    property ShellScreen screen
    property bool isWindow
    property bool animatingContainer
    property var pageHistory: []
    property int previousPageIdx: 0
    property bool returning: false
    property int navigationDirection: 1
    property bool showingSection: true
    property string requestedPanelId: ""
    property string sectionId: "home"
    readonly property bool canGoBack: subPageIdxStack.length > 0 || pageHistory.length > 0 || !showingSection
    function snapshot(page): var {
        return {page, section:sectionId, hub:showingSection, subpages:Array.from(subPageIdxStack)};
    }
    function remember(value): void { pageHistory = [...pageHistory.slice(-31), value]; }
    function openSection(id: string): void {
        const section = PageRegistry.section(id);
        if (section.landing) { openPage(section.landing); return; }
        if (showingSection && sectionId === id) return;
        navigationDirection = 1;
        remember(snapshot(currentPageIdx));
        returning = true;
        sectionId = id;
        showingSection = true;
        subPageIdxStack = [];
        searchTarget = searchTargetText = "";
        returning = false;
    }
    function goBack(): void {
        navigationDirection = -1;
        if (!showingSection && subPageIdxStack.length) { closeSubPage(); return; }
        if (!pageHistory.length) { openSection(sectionId); return; }
        const destination = pageHistory[pageHistory.length - 1];
        pageHistory = pageHistory.slice(0, -1);
        returning = true;
        currentPageIdx = destination.page;
        sectionId = destination.section;
        showingSection = destination.hub;
        subPageIdxStack = destination.subpages;
        returning = false;
        searchRequested();
    }
    property int currentPageIdx
    property list<int> subPageIdxStack
    property string searchQuery
    readonly property bool searchOpen: searchQuery.trim().length > 0
    property int searchResultIdx
    property string searchTarget
    property string searchTargetText

    property string selectedWallpaperCategory
    property BluetoothDevice selectedBtDevice
    property var selectedApp
    property int editingVpnIndex: -1
    property string selectedNetworkSsid
    property string selectedEthernetInterface
    property bool networkDetailsFromSaved

    signal close
    signal subPageOpened(idx: int)
    signal subPageClosed
    signal searchRequested

    function openPage(id: string): void {
        const route = PageRegistry.route(id);
        const index = PageRegistry.indexOf(route.id);
        if (index < 0) {
            if (PageRegistry.sections.some(value => value.id === id)) openSection(id);
            return;
        }
        navigationDirection = 1;
        if (!returning && (showingSection || currentPageIdx !== index)) remember(snapshot(currentPageIdx));
        returning = true;
        currentPageIdx = index;
        sectionId = PageRegistry.sectionFor(route.id).id;
        showingSection = false;
        subPageIdxStack = [];
        searchTarget = searchTargetText = "";
        returning = false;
        if (route.subPage !== undefined) subPageIdxStack = [route.subPage];
        // Re-entering the same page must also discard a previous detail route.
        searchRequested();
    }

    function openSubPage(idx: int): void {
        searchTarget = searchTargetText = "";
        subPageIdxStack.push(idx);
        subPageOpened(idx);
    }

    function closeSubPage(): void {
        searchTarget = searchTargetText = "";
        subPageClosed();
        subPageIdxStack.pop();
    }

    onCurrentPageIdxChanged: {
        if (!returning) {
            remember(snapshot(previousPageIdx));
            showingSection = false;
            sectionId = PageRegistry.sectionFor(PageRegistry.pages[currentPageIdx]?.id ?? "").id;
        }
        previousPageIdx = currentPageIdx;
        subPageIdxStack.length = 0;
        searchTarget = searchTargetText = "";
    }
}
