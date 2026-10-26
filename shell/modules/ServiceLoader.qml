import QtQuick
import Quickshell
import Hyprstack.Services
import Hyprstack.Config
import qs.services

Scope {
    VpnAuthentication {}
    property bool backgroundStarted: false
    function startBackgroundServices(): void {
        if (backgroundStarted) return;
        backgroundStarted = true;
        Comfort; HungApplications; CaptivePortal; DesktopIntegrationMonitor;
        DefaultApps; Weather.reload();
    }
    Connections {
        target: StartupPerformance
        function onFirstFrameChanged(): void { if (StartupPerformance.firstFrame) Qt.callLater(startBackgroundServices); }
    }
    Timer {interval:60000;running:StartupPerformance.firstFrame && GlobalConfig.general.maintenance.automaticThumbnailCleanup;triggeredOnStart:true;repeat:true;onTriggered:DesktopConveniences.automaticCleanup(GlobalConfig.general.maintenance.thumbnailRetentionDays)}

    Component.onCompleted: {
        // Force certain singletons to load on shell init instead of lazily

        StartupPerformance;
        if (StartupPerformance.firstFrame) Qt.callLater(startBackgroundServices);
        DesktopJobs;
        ApplicationLayouts;
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
        Players;
        WindowSwitcher;
        Brightness;

        if (GlobalConfig.utilities.vpn.enabled)
            VPN;
    }
}
