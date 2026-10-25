import QtQuick
import Quickshell
import Hyprstack.Services
import Hyprstack.Config
import qs.services

Scope {
    VpnAuthentication {}
    Timer {interval:60000;running:GlobalConfig.general.maintenance.automaticThumbnailCleanup;triggeredOnStart:true;repeat:true;onTriggered:DesktopConveniences.automaticCleanup(GlobalConfig.general.maintenance.thumbnailRetentionDays)}

    Component.onCompleted: {
        // Force certain singletons to load on shell init instead of lazily

        CaptivePortal;
        DesktopConfiguration;
        DisplayProfiles;
        LayoutModes;
        Plugins;
        LiveWallpapers;
        ThemeAutomation;
        IdleInhibitor;
        PerformancePolicy;
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
