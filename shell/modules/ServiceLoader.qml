import QtQuick
import Quickshell
import Hyprstack.Config
import qs.services

Scope {
    VpnAuthentication {}

    Component.onCompleted: {
        // Force certain singletons to load on shell init instead of lazily

        DesktopConfiguration;
        DisplayProfiles;
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
