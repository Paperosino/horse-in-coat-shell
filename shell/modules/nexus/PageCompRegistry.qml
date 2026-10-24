pragma Singleton

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus.common
import qs.modules.nexus.pages
import qs.modules.nexus.pages.apps
import qs.modules.nexus.pages.audio
import qs.modules.nexus.pages.bluetooth
import qs.modules.nexus.pages.keyboard
import qs.modules.nexus.pages.network
import qs.modules.nexus.pages.panels
import qs.modules.nexus.pages.services
import qs.modules.nexus.pages.wallandstyle
import qs.modules.nexus.pages.panels.taskbar

QtObject {
    id: root

    readonly property list<Component> pageComps: [
        // Appearance
        Component {
            // Wallpaper & style
            StackPage {
                Component {
                    WallpaperAndStyle {}
                }
                Component {
                    WallpaperSelect {}
                }
                Component {
                    WallpaperCategory {}
                }
                Component { ColourSelect {} }
                Component { ThemeCenterPage {} }
                Component { LiveWallpapersPage {} }
                Component { AppearanceThemesPage {} }
                Component { AppearanceThemesPage { cursorThemes:true } }
                Component { ShellStylePage {} }
            }
        },

        // Connectivity
        Component {
            // Display
            StackPage {
                Component {
                    DisplayPage {}
                }
            }
        },
        Component { StackPage { Component { SystemControlsPage {} } Component { CanvasPage {} } } },
        Component {
            // Network
            StackPage {
                Component {
                    NetworkPage {}
                }
                Component {
                    EthernetDetailPage {}
                }
                Component {
                    AddNetworkPage {}
                }
                Component {
                    NetworkDetailPage {}
                }
                Component {
                    AddVpnPage {}
                }
                Component {
                    AllNetworksPage {}
                }
                Component {
                    SavedNetworksPage {}
                }
                Component { VpnEditorPage {} }
                Component { VpnPluginsPage {} }
            }
        },
        Component {
            // Bluetooth
            StackPage {
                Component {
                    BluetoothPage {}
                }
                Component {
                    BtDeviceInfo {}
                }
                Component {
                    BluetoothPairing {}
                }
            }
        },
        Component {
            // Audio
            StackPage {
                Component {
                    AudioPage {}
                }
                Component {
                    AppVolumes {}
                }
                Component { MediaPage {} }
            }
        },

        Component {
            // Keyboard
            StackPage {
                Component {
                    KeyboardPage {}
                }
                Component { LayoutPicker {} }
                Component { InputDevicePage { title: Tr.tr("Mouse"); groups: ["Mouse"] } }
                Component { InputDevicePage { title: Tr.tr("Touchpad"); groups: ["Touchpad"] } }
                Component { InputDevicePage { title: Tr.tr("Cursor"); groups: ["Cursor"] } }
                Component { InputDevicePage { title: Tr.tr("Gestures"); groups: ["Gestures"] } }
                Component { ShortcutEditorPage {} }
            }
        },

        // Shell
        Component {
            // Panels
            StackPage {
                Component {
                    PanelsPage {}
                }
                Component {
                    DashboardPanel {}
                }
                Component {
                    TaskbarPanel {}
                }
                Component {
                    LauncherPanel {}
                }
                Component {
                    SidebarPanel {}
                }
                Component {
                    UtilitiesPanel {}
                }

                // Taskbar component sub-pages
                Component {
                    BarWorkspaces {}
                }
                Component {
                    BarActiveWindow {}
                }
                Component {
                    BarTray {}
                }
                Component {
                    BarStatusIcons {}
                }
                Component {
                    BarClock {}
                }
                Component { DockPage {} }
                Component { StatusbarLayoutPage {} }
            }
        },
        Component {
            // Dock
            StackPage {
                Component {
                    DockPage {}
                }
            }
        },
        Component {
            // Apps
            StackPage {
                Component {
                    AppsPage {}
                }
                Component {
                    AllApps {}
                }
                Component { AppInfo {} }
                Component { SessionServicesPage { autostartOnly: true } }
                Component { PluginsPage {} }
                Component { AssistantPage {} }
                Component { DefaultAppsPage {} }
            }
        },
        Component {
            // Services
            StackPage {
                Component {
                    ServicesPage {}
                }
                Component { NotificationsPage {} }
                Component { SessionServicesPage {} }
            }
        },
        Component {
            // Power & lock
            StackPage {
                Component {
                    PowerPage {}
                }
            }
        },
        Component {
            // Language & region
            StackPage {
                Component {
                    LanguageAndRegion {}
                }
                Component { DateTimePage {} }
            }
        },

        Component {
            StackPage {
                Component {
                    ShortcutEditorPage {}
                }
            }
        },

        Component { StackPage { Component { PluginsPage {} } } },
        Component { StackPage { Component { AssistantPage {} } } },

        // About
        Component {
            StackPage {
                Component {
                    AboutPage {}
                }
            }
        },
        Component { StackPage { Component { DevicesPage {} } Component { PrintersPage {} } Component { StoragePage {} } } },
        Component { StackPage { Component { AccessibilityPage {} } } },
        Component { StackPage { Component { SharingPage {} } } },
        Component { StackPage { Component { NotificationsPage {} } } },
        Component { StackPage { Component { InputDevicePage { title:Tr.tr("Mouse"); groups:["Mouse"] } } } },
        Component { StackPage { Component { InputDevicePage { title:Tr.tr("Touchpad"); groups:["Touchpad"] } } } },
        Component { StackPage { Component { PrintersPage {} } } },
        Component { StackPage { Component { StoragePage {} } } },
        Component { StackPage { Component { DateTimePage {} } } },
        Component { StackPage { Component { SessionServicesPage { autostartOnly:true } } } },
        Component { StackPage { Component { DefaultAppsPage {} } } },
        Component { StackPage { Component { VpnProfilesPage {} } Component { VpnEditorPage {} } Component { VpnPluginsPage {} } } },
        Component { StackPage { Component { ClipboardPage {} } } },
        Component { StackPage { Component { WorkspaceSessionPage {} } } },
        Component { StackPage { Component { WorkspaceSessionPage { projectsOnly:true } } } },
        Component { StackPage { Component { ConfigurationPage { profilesOnly:true } } } },
        Component { StackPage { Component { ConfigurationPage {} } } },
        Component { StackPage { Component { DesktopRulesPage {} } } },
        Component { StackPage { Component { DesktopRulesPage { devicesOnly:true } } } },
        Component { StackPage { Component { SettingsWorkbenchPage {} } } },
        Component { StackPage { Component { DiagnosticsPage {} } } },
        Component { StackPage { Component { OnboardingPage {} } } },
        Component { StackPage { Component { PerformancePage {} } } }
    ]

    readonly property Component placeholderComp: Component {
        PlaceholderComp {}
    }

    component PlaceholderComp: Item {
        property NexusState nState // To avoid the warning from non-existent property

        ColumnLayout {
            anchors.centerIn: parent
            spacing: Tokens.padding.extraSmall

            MaterialIcon {
                Layout.alignment: Qt.AlignHCenter
                text: "handyman"
                color: Colours.palette.m3outlineVariant
                fontStyle: Tokens.font.icon.extraLarge
            }

            StyledText {
                Layout.alignment: Qt.AlignHCenter
                text: Tr.tr("Page under construction")
                color: Colours.palette.m3outlineVariant
                font: Tokens.font.title.large
            }

            StyledText {
                Layout.alignment: Qt.AlignHCenter
                text: Tr.tr("This page will be available in a future update.")
                color: Colours.palette.m3outlineVariant
                font: Tokens.font.body.large
            }
        }
    }
}
