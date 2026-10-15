import QtQuick
import Quickshell
import Quickshell.Bluetooth

QtObject {
    property ShellScreen screen
    property bool isWindow
    property bool animatingContainer
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
        subPageIdxStack.length = 0;
        searchTarget = searchTargetText = "";
    }
}
