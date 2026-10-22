pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.I18n
import qs.modules.nexus.common
// Compatibility for the old saved page index. Public VPN links route to Network.
PageBase {
    id:root
    title:Tr.tr("VPN")
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter
        VpnSection {nState:root.nState;editorPage:1;pluginsPage:2}
    }
}
