pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus.common
PageBase {
    id: root
    title: Tr.tr("Customisation")
    ColumnLayout {
        width:root.cappedWidth
        anchors.horizontalCenter:parent.horizontalCenter
        spacing:Tokens.spacing.small
        SettingsGuide {
            icon:"palette"
            title:Tr.tr("Make this desktop yours")
            description:Tr.tr("Start with the background and colours, then match your applications and pointer.")
            badges:[Tr.tr("Background"),Tr.tr("Colours"),Tr.tr("Icons"),Tr.tr("Cursors")]
        }
        SectionHeader { text:Tr.tr("Desktop background") }
        NavRow { first:true;text:Tr.tr("Wallpapers");subtext:Tr.tr("Choose a picture for your desktop");icon:"wallpaper";onClicked:root.nState.openSubPage(1) }
        NavRow { last:true;text:Tr.tr("Live wallpapers");subtext:Tr.tr("Videos and Wallpaper Engine per monitor");icon:"movie";onClicked:root.nState.openSubPage(5) }
        SectionHeader { text:Tr.tr("Colours & themes") }
        NavRow { first:true;text:Tr.tr("Colours");subtext:Tr.tr("Accent, light and dark palettes");icon:"colors";onClicked:root.nState.openSubPage(3) }
        NavRow { last:true;text:Tr.tr("Themes & automation");subtext:Tr.tr("Import themes, day and night schedule");icon:"schedule";onClicked:root.nState.openSubPage(4) }
        ToggleRow {
            first: true
            last: true
            text: Tr.tr("Smart colour scheme")
            subtext: Tr.tr("Derive theme mode and variant from the wallpaper")
            checked: GlobalConfig.services.smartScheme
            onToggled: GlobalConfig.services.smartScheme = checked
        }
        SectionHeader { text:Tr.tr("Application appearance") }
        NavRow { first:true;text:Tr.tr("Application icons");subtext:Tr.tr("Theme previews for GTK, Qt 5, Qt 6 and Flatpak");icon:"interests";onClicked:root.nState.openSubPage(6) }
        NavRow { last:true;text:Tr.tr("Cursor appearance");subtext:Tr.tr("Preview shapes, choose a theme and adjust its size");icon:"arrow_selector_tool";onClicked:root.nState.openSubPage(7) }
        SectionHeader { text:Tr.tr("Shell & windows") }
        NavRow { first:true;last:true;text:Tr.tr("Shell appearance");subtext:Tr.tr("Transparency, blur, window edges, shadows and scale");icon:"blur_on";onClicked:root.nState.openSubPage(8) }


    }
}
