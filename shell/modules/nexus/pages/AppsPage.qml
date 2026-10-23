pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.modules.nexus.common

PageBase {
    id: root
    title: Tr.tr("Apps")
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.small
        SettingsGuide {
            icon: "apps"
            title: Tr.tr("Choose how your applications work")
            description: Tr.tr("Browse apps, choose what opens your files, and add new features.")
            badges: [Tr.tr("Library"), Tr.tr("Defaults"), Tr.tr("Extensions")]
        }
        SettingsCard {
            title: Tr.tr("Applications & files")
            icon: "tune"

            NavRow {
                first: true
                text: Tr.tr("All apps")
                subtext: Tr.tr("Browse installed apps, set favourites and hidden")
                icon: "apps"
                onClicked: root.nState.openSubPage(1)
            }
            NavRow {
                text: Tr.tr("Default applications")
                subtext: Tr.tr("Browser, documents, media and file formats")
                icon: "open_in_new"
                onClicked: root.nState.openPage("default-apps")
            }
            NavRow {
                last: true
                text: Tr.tr("Autostart")
                subtext: Tr.tr("Applications started when signing in")
                icon: "rocket_launch"
                onClicked: root.nState.openPage("autostart")
            }
        }
        SettingsCard {
            title: Tr.tr("Extensions & tools")
            icon: "tune"

            NavRow {
                first: true
                text: Tr.tr("Plugins")
                subtext: Tr.tr("Add features and manage extensions")
                icon: "extension"
                onClicked: root.nState.openPage("plugins")
            }
            NavRow {
                last: true
                text: Tr.tr("AI assistant")
                subtext: Tr.tr("Models, providers and conversation settings")
                icon: "smart_toy"
                onClicked: root.nState.openPage("assistant")
            }
        }
    }
}
