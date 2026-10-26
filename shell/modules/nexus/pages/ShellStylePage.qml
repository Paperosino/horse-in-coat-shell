pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Components
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.components.images
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "style"

    title: Tr.tr("Shell appearance")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        SettingsCard {
            title: Tr.tr("Font rendering")
            icon: "text_fields"
            description: Tr.tr("One preference for the shell, GTK, Qt, X11 and Flatpak applications")
            ToggleRow {
                objectName: "fontAntialias"
                text: Tr.tr("Smooth font edges")
                subtext: Tr.tr("Grayscale antialiasing works with rotated screens and fractional scaling")
                checked: GlobalConfig.appearance.font.antialias
                onToggled: GlobalConfig.appearance.font.antialias = checked
            }
            SelectRow {
                objectName: "fontHinting"
                label: Tr.tr("Hinting")
                subtext: Tr.tr("Align glyphs to pixels. No hinting keeps transformed text smooth; stronger hinting makes small text sharper.")
                active: menuItems.find(item => item.value === GlobalConfig.appearance.font.hinting) ?? menuItems[1]
                onSelected: item => GlobalConfig.appearance.font.hinting = item.value
                menuItems: [
                    MenuItem { text: Tr.tr("None"); value: "none" },
                    MenuItem { text: Tr.tr("Slight"); value: "slight" },
                    MenuItem { text: Tr.tr("Medium"); value: "medium" },
                    MenuItem { text: Tr.tr("Full"); value: "full" }
                ]
            }
            StyledText {
                Layout.fillWidth: true
                text: "Aa · Абв · 0123456789"
                font: Tokens.font.title.builders.large.size(24).build()
                horizontalAlignment: Text.AlignHCenter
            }
            FeatureError { error: FontRendering.error }
            StyledText {
                Layout.fillWidth: true
                visible: FontRendering.notice.length > 0
                text: FontRendering.notice
                wrapMode: Text.WordWrap
                color: Colours.palette.m3onSurfaceVariant
            }
        }

        ToggleRow {
            first: true
            text: Tr.tr("Display wallpaper")
            checked: Config.background.wallpaperEnabled
            onToggled: GlobalConfig.background.wallpaperEnabled = checked
        }

        ToggleRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing

            text: Tr.tr("Transparency")
            objectName: "appearanceTransparency"
            // TRANSLATORS: %1/%2 = opacity values from 0 to 1 for the base surface and layered surfaces
            subtext: Tr.tr("Base %1, layers %2").arg(Colours.transparency.base).arg(Colours.transparency.layers)
            checked: Colours.transparency.enabled
            onToggled: GlobalConfig.appearance.transparency.enabled = checked
        }

        SliderRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            icon: "opacity"
            objectName: "appearanceOpacity"
            label: Tr.tr("Opacity")
            valueLabel: `${Math.round(value * 100)}%`
            value: GlobalConfig.appearance.transparency.base
            enabled: Colours.transparency.enabled
            onMoved: value => GlobalConfig.appearance.transparency.base = value
        }

        ToggleRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            text: Tr.tr("Blur")
            objectName: "appearanceBlur"
            checked: Effects.blurEnabled
            onToggled: Effects.setBlurEnabled(checked)
        }

        ToggleRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            objectName: "appearanceDesktopFrame"
            text: Tr.tr("Desktop frame in tiling mode")
            checked: Tiling.desktopFrame
            onToggled: Tiling.set("desktopFrame", checked)
        }

        ToggleRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            objectName: "appearanceTilingGaps"
            text: Tr.tr("Gaps in tiling mode")
            subtext: Tr.tr("Toggle with Win+G")
            checked: Tiling.gaps
            onToggled: Tiling.set("gaps", checked)
        }

        StepperRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            objectName: "appearanceFocusBorderWidth"
            label: Tr.tr("Window border width")
            subtext: Tr.tr("Scrolling mode only; 0 hides the window border")
            value: Tiling.focusBorderWidth
            from: 0
            to: 10
            onMoved: v => Tiling.set("focusBorderWidth", v)
        }

        PaletteRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            objectName: "appearanceFocusBorderColor"
            label: Tr.tr("Window border colour")
            subtext: Tr.tr("Scrolling mode; choose a colour from the current scheme independently of the theme accent")
            value: Tiling.focusBorderColor
            palette: Colours.current
            choices: Tiling.borderColorChoices.map(choice => ({
                        role: choice.role,
                        label: Tr.tr(choice.label)
                    }))
            onSelected: role => Tiling.set("focusBorderColor", role)
        }

        StepperRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            objectName: "appearanceWindowRounding"
            label: Tr.tr("Window corner rounding")
            subtext: Tr.tr("Radius in pixels; 0 makes window corners square")
            value: Tiling.windowRounding
            from: 0
            to: 60
            onMoved: v => Tiling.set("windowRounding", v)
        }

        ToggleRow {
            Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
            last: true
            objectName: "appearanceDarkTheme"
            text: Tr.tr("Dark theme")
            checked: !Colours.light
            onToggled: Colours.setMode(checked ? "dark" : "light")
        }

        SettingsCard {
            title: Tr.tr("Window gaps")
            icon: "style"

            StepperRow {
                first: true
                objectName: "appearanceGapsIn"
                label: Tr.tr("Inner gaps")
                subtext: Tr.tr("Padding on each side of a tiled window, in pixels")
                value: Tiling.gapsIn
                from: 0
                to: 100
                onMoved: v => Tiling.set("gapsIn", v)
            }

            StepperRow {
                Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
                last: true
                objectName: "appearanceGapsOut"
                label: Tr.tr("Outer gaps")
                subtext: Tr.tr("Padding at the workspace edges, in pixels; identical for every window count")
                value: Tiling.gapsOut
                from: 0
                to: 100
                onMoved: v => Tiling.set("gapsOut", v)
            }
        }
        SettingsCard {
            title: Tr.tr("Shadows")
            icon: "style"

            ToggleRow {
                first: true
                objectName: "appearanceWindowShadows"
                text: Tr.tr("Window shadows")
                subtext: Tr.tr("The same shadow for active and inactive windows")
                checked: Effects.windowShadows
                onToggled: Effects.set("windowShadows", checked)
            }

            ToggleRow {
                Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
                objectName: "appearanceUiShadows"
                text: Tr.tr("Interface shadows")
                subtext: Tr.tr("Panels, menus and desktop widgets")
                checked: Effects.uiShadows
                onToggled: Effects.set("uiShadows", checked)
            }

            StepperRow {
                Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
                objectName: "appearanceShadowSize"
                label: Tr.tr("Shadow size")
                subtext: Tr.tr("Pixels; 0 disables shadows")
                value: Effects.shadowSize
                from: 0
                to: 60
                onMoved: v => Effects.set("shadowSize", v)
            }

            SliderRow {
                Layout.topMargin: Tokens.spacing.extraSmall / 2 - parent.spacing
                last: true
                objectName: "appearanceShadowOpacity"
                icon: "shadow"
                label: Tr.tr("Shadow intensity")
                valueLabel: `${Math.round(value * 100)}%`
                value: Effects.shadowOpacity
                onMoved: v => Effects.set("shadowOpacity", v)
            }
        }
        SettingsCard {
            title: Tr.tr("Interface scale")
            icon: "style"

            StepperRow {
                first: true
                last: true
                objectName: "appearanceShellScale"
                label: Tr.tr("Shell scale")
                subtext: Tr.tr("Panel, menus, text and desktop widgets, in percent")
                value: Math.round(GlobalConfig.appearance.scale * 100)
                from: 50
                to: 200
                stepSize: 5
                onMoved: v => GlobalConfig.appearance.scale = v / 100
            }
        }
    }
}
