// Register the settings page directory only when shortcut help is opened.
import QtQuick
import Quickshell
import "." as NexusModule
import "pages" as SettingsPages
SettingsPages.KeybindsPage {
    id: root
    property ShellScreen targetScreen
    nState: NexusModule.NexusState { screen: root.targetScreen; isWindow: false }
}
