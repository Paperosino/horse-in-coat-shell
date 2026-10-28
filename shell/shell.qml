//@ pragma AppId org.hics.Shell
//@ pragma DefaultEnv QS_NO_RELOAD_POPUP=1
//@ pragma DefaultEnv QS_DROP_EXPENSIVE_FONTS=1
//@ pragma DefaultEnv QSG_RENDER_LOOP=threaded
//@ pragma DefaultEnv QT_QUICK_FLICKABLE_WHEEL_DECELERATION=10000
//@ pragma IconTheme Adwaita

import "modules/configuration" as Configuration
import "modules/displays" as Displays
import "modules/extensions"
import "modules"
import "modules/drawers"
import "modules/background"
import "modules/areapicker"
import "modules/lock"
import "modules/session" as SessionModule
import "modules/overview" as OverviewModule
import "modules/switcher" as SwitcherModule
import "modules/polkit" as PolkitModule
import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack
import Hyprstack.Services
import qs.services

ShellRoot {
    id: root

    settings.watchFiles: false
    IpcHandler { target: "sessionHealth"; function ready(): bool { return StartupPerformance.firstFrame; } }
    IpcHandler {
        target: "sessionControl"
        function transition(mode: string): bool {
            if (lock.transitioning || lock.lock.locked || !["on", "resume"].includes(mode)) return false;
            lock.transitioning = true;
            Qt.exit(mode === "on" ? 75 : 76);
            return true;
        }
    }

    Component.onCompleted: AnimationClock.activate()

    Binding {
        target: ShellState
        property: "shellRoot"
        value: root
    }

    GSFLoader {}
    ServiceLoader {}
    PluginHost {}
    Displays.Confirmation {}
    Configuration.Confirmation {}
    Loader {
        active: Onboarding.running
        source: active ? Qt.resolvedUrl("modules/TourContent.qml") : ""
    }
    PolkitModule.Polkit { id: authentication }

    Background {}
    Drawers {}
    AreaPicker {}
    Lock {
        id: lock
    }

    WorkspaceServices {locked:lock.lock.locked}
    SessionModule.LogoutFlow { locked: lock.lock.locked }
    Shortcuts {}
    ShortcutHelp { authenticationActive: authentication.active }
    OverviewModule.OverviewWindows {}
    SwitcherModule.WindowSwitcher {}
    BatteryMonitor {}
    IdleMonitors {
        lock: lock
    }
}
