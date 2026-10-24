//@ pragma DefaultEnv QS_NO_RELOAD_POPUP=1
//@ pragma DefaultEnv QS_DROP_EXPENSIVE_FONTS=1
//@ pragma DefaultEnv QSG_RENDER_LOOP=threaded
//@ pragma DefaultEnv QT_QUICK_FLICKABLE_WHEEL_DECELERATION=10000
//@ pragma IconTheme Adwaita

import "modules/onboarding" as OnboardingModule
import "modules/configuration" as Configuration
import "modules/displays" as Displays
import "modules/extensions"
import "modules"
import "modules/drawers"
import "modules/background"
import "modules/areapicker"
import "modules/lock"
import "modules/overview" as OverviewModule
import "modules/switcher" as SwitcherModule
import "modules/polkit" as PolkitModule
import QtQuick
import Quickshell
import Hyprstack
import qs.services

ShellRoot {
    id: root

    settings.watchFiles: false

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
    OnboardingModule.Wizard {}
    PolkitModule.Polkit { id: authentication }

    Background {}
    Drawers {}
    AreaPicker {}
    Lock {
        id: lock
    }

    WorkspaceServices {locked:lock.lock.locked}
    Shortcuts {}
    ShortcutHelp { authenticationActive: authentication.active }
    OverviewModule.OverviewWindows {}
    SwitcherModule.WindowSwitcher {}
    BatteryMonitor {}
    IdleMonitors {
        lock: lock
    }
}
