import QtQuick
import Quickshell
import Hyprstack.Config
import qs.services

Scope {
    Component.onCompleted: {
        // Force certain singletons to load on shell init instead of lazily

        LayoutModes;
        Plugins;
        LiveWallpapers;
        ThemeAutomation;
        IdleInhibitor;
        GameMode;
        Notifs;
        DesktopIntegrationMonitor;
        Players;
        WindowSwitcher;
        Brightness;
        DefaultApps;
        Weather.reload();

        if (GlobalConfig.utilities.vpn.enabled)
            VPN;
    }
}
