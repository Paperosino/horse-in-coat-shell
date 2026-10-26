pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Services
import qs.components.controls
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "wallpaper"
    title: Tr.tr("Customisation")
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.small
        SettingsGuide {
            icon: "palette"
            title: Tr.tr("Make this desktop yours")
            description: Tr.tr("Start with the background and colours, then match your applications and pointer.")
            badges: [Tr.tr("Background"), Tr.tr("Colours"), Tr.tr("Icons"), Tr.tr("Cursors")]
        }
        SettingsCard {
            title: Tr.tr("Desktop background")
            icon: "palette"

            NavRow {
                first: true
                text: Tr.tr("Wallpapers")
                subtext: Tr.tr("Choose a picture for your desktop")
                icon: "wallpaper"
                onClicked: root.nState.openSubPage(1)
            }
            NavRow {
                last: true
                text: Tr.tr("Live wallpapers")
                subtext: Tr.tr("Videos and Wallpaper Engine per monitor")
                icon: "movie"
                onClicked: root.nState.openSubPage(5)
            }
        }
        SettingsCard {
            title:Tr.tr("Desktop icons")
            icon:"desktop_windows"
            description:Tr.tr("Files from your desktop folder, shared with Nautilus, Dolphin and other file managers. File associations remain system-wide.")
            ToggleRow {text:Tr.tr("Show desktop icons");checked:GlobalConfig.background.desktopIcons.enabled;onToggled:GlobalConfig.background.desktopIcons.enabled=checked}
            ToggleRow {visible:GlobalConfig.background.desktopIcons.enabled;text:Tr.tr("Open desktop items with a single click");checked:GlobalConfig.background.desktopIcons.singleClick;onToggled:GlobalConfig.background.desktopIcons.singleClick=checked}
            ToggleRow {visible:GlobalConfig.background.desktopIcons.enabled;text:Tr.tr("Show hidden desktop files");checked:GlobalConfig.background.desktopIcons.showHidden;onToggled:GlobalConfig.background.desktopIcons.showHidden=checked}
            StepperRow {visible:GlobalConfig.background.desktopIcons.enabled;label:Tr.tr("Desktop icon size");from:32;to:96;stepSize:8;value:GlobalConfig.background.desktopIcons.iconSize;onMoved:value=>GlobalConfig.background.desktopIcons.iconSize=value}
            SelectRow {
                visible:GlobalConfig.background.desktopIcons.enabled
                label:Tr.tr("Sort desktop icons")
                active:menuItems.find(item=>item.value===GlobalConfig.background.desktopIcons.sortBy)??menuItems[0]
                menuItems:[MenuItem {text:Tr.tr("Name");value:"name"},MenuItem {text:Tr.tr("Type");value:"type"},MenuItem {text:Tr.tr("Recently modified");value:"modified"}]
                onSelected:item=>{GlobalConfig.background.desktopIcons.sortBy=item.value;DesktopFiles.tidy();}
            }
            GenericSettingRow {
                visible:GlobalConfig.background.desktopIcons.enabled
                spec:({label:"Desktop icons display",type:"choice",choices:[{label:"First connected display",value:""}].concat(Quickshell.screens.map(screen=>({label:screen.name,value:screen.name})))})
                value:GlobalConfig.background.desktopIcons.output
                onEdited:value=>GlobalConfig.background.desktopIcons.output=value
            }
            RowButton {visible:GlobalConfig.background.desktopIcons.enabled;text:Tr.tr("Open desktop folder");subtext:DesktopFiles.directory;icon:"folder_open";onClicked:DesktopIcons.openFolder()}
            RowButton {visible:GlobalConfig.background.desktopIcons.enabled;text:Tr.tr("Arrange desktop icons");icon:"grid_view";onClicked:DesktopFiles.tidy()}
        }
        SettingsCard {
            title: Tr.tr("Colours & themes")
            icon: "palette"

            NavRow {
                first: true
                text: Tr.tr("Colours")
                subtext: Tr.tr("Accent, light and dark palettes")
                icon: "colors"
                onClicked: root.nState.openSubPage(3)
            }
            NavRow {
                last: true
                text: Tr.tr("Themes & automation")
                subtext: Tr.tr("Import themes, day and night schedule")
                icon: "schedule"
                onClicked: root.nState.openSubPage(4)
            }
            ToggleRow {
                first: true
                last: true
                text: Tr.tr("Smart colour scheme")
                subtext: Tr.tr("Derive theme mode and variant from the wallpaper")
                checked: GlobalConfig.services.smartScheme
                onToggled: GlobalConfig.services.smartScheme = checked
            }
        }
        SettingsCard {
            title: Tr.tr("Application appearance")
            icon: "apps"

            NavRow {
                first: true
                text: Tr.tr("Application icons")
                subtext: Tr.tr("Theme previews for GTK, Qt 5, Qt 6 and Flatpak")
                icon: "interests"
                onClicked: root.nState.openSubPage(6)
            }
            NavRow {
                last: true
                text: Tr.tr("Cursor appearance")
                subtext: Tr.tr("Preview shapes, choose a theme and adjust its size")
                icon: "arrow_selector_tool"
                onClicked: root.nState.openSubPage(7)
            }
        }
        SettingsCard {
            title: Tr.tr("Shell & windows")
            icon: "window"

            NavRow {
                first: true
                last: true
                text: Tr.tr("Shell appearance")
                subtext: Tr.tr("Transparency, blur, window edges, shadows and scale")
                icon: "blur_on"
                onClicked: root.nState.openSubPage(8)
            }
        }
    }
}
