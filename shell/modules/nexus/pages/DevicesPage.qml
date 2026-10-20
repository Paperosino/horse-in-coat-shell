import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.modules.nexus.common
PageBase {
    id: root
    title: Tr.tr("Printers & storage")
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.extraSmall / 2
        NavRow { first: true; text: Tr.tr("Printers"); subtext: Tr.tr("Printer queues, default printer and print jobs"); icon: "print"; onClicked: root.nState.openSubPage(1) }
        NavRow { last: true; text: Tr.tr("Storage"); subtext: Tr.tr("Disk space, filesystems and removable volumes"); icon: "storage"; onClicked: root.nState.openSubPage(2) }
    }
}
