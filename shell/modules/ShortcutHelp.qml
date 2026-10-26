pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.components
import qs.components.containers
import qs.components.controls
import qs.components.misc
import qs.services
import Hyprstack.Config
import Hyprstack.I18n

Scope {
    id: root
    property bool opened: false
    property bool authenticationActive: false
    onAuthenticationActiveChanged: if (authenticationActive) opened = false
    property ShellScreen requestScreen
    function toggle(): void {
        if (authenticationActive) return;
        if (!opened) {
            requestScreen = Quickshell.screens.find(s => s.name === Hypr.focusedMonitor?.name) ?? Quickshell.screens[0];
            Keybinds.reload();
        }
        opened = !opened;
    }
    CustomShortcut {
        name: "shortcutHelp"
        description: "Keyboard shortcuts"
        onPressed: root.toggle()
    }
    Connections {
        target: Hyprland
        function onRawEvent(event: HyprlandEvent): void {
            if (event.name === "activewindow" && /gcr-prompter|gcr-system-prompter|keyring[.]SystemPrompter|polkit-.*authentication/i.test(event.data))
                root.opened = false;
        }
    }
    LazyLoader {
        active: root.opened
        StyledWindow {
            id: panel
            name: "shortcut-help"
            Config.screen: screen?.name ?? ""
            Tokens.screen: screen?.name ?? ""
            screen: Quickshell.screens.includes(root.requestScreen) ? root.requestScreen : Quickshell.screens[0]
            implicitWidth: Math.min(920 * Tokens.scale, (screen?.width ?? 1000) - 48)
            implicitHeight: Math.min(760 * Tokens.scale, (screen?.height ?? 900) - 48)
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.exclusionMode: ExclusionMode.Ignore
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
            onBackingWindowVisibleChanged: if (backingWindowVisible) Qt.callLater(() => contents.forceActiveFocus())
            StyledRect {
                id: contents
                anchors.fill: parent
                radius: Tokens.rounding.large
                color: Colours.palette.m3surface
                focus: true
                Keys.onEscapePressed: root.opened = false
                Loader {
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.large
                    property ShellScreen targetScreen: panel.screen
                    source: Qt.resolvedUrl("nexus/ShortcutHelpPage.qml")
                    onLoaded: item.targetScreen = targetScreen
                    onTargetScreenChanged: if (item) item.targetScreen = targetScreen
                }
                IconButton {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: Tokens.padding.medium
                    icon: "close"
                    onClicked: root.opened = false
                    Accessible.name: Tr.tr("Close")
                }
            }
        }
    }
}
