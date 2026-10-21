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
    readonly property bool canGoBack: subPageIdxStack.length > 0 || pageHistory.length > 0
    function goBack(): void {
        if (subPageIdxStack.length) { closeSubPage(); return; }
        if (!pageHistory.length) return;
        const destination = pageHistory[pageHistory.length - 1];
        pageHistory = pageHistory.slice(0, -1);
        returning = true; currentPageIdx = destination; returning = false;
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
    property DesktopEntry selectedApp
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
        if (index < 0) return;
        currentPageIdx = index;
        if (route.subPage !== undefined) openSubPage(route.subPage);
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
        if (!returning && previousPageIdx !== currentPageIdx) pageHistory = [...pageHistory.slice(-31), previousPageIdx];
        previousPageIdx = currentPageIdx;
        subPageIdxStack.length = 0;
        searchTarget = searchTargetText = "";
    }
}
