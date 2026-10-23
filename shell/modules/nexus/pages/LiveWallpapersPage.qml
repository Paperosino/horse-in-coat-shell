pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.components.filedialog
import qs.services
import qs.utils
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "wallpaper"
    title: Tr.tr("Live wallpapers")
    objectName: "liveWallpapersPage"
    property string outputName: nState.screen?.name ?? Screens.screens[0]?.name ?? ""
    property var draft: LiveWallpapers.forScreen(outputName)
    readonly property var entry: LiveWallpapers.entries.find(e => e.path === draft.source) ?? null
    function set(key: string, value: var): void {
        draft = Object.assign({}, draft, {
            [key]: value
        });
    }
    Component.onCompleted: LiveWallpapers.reloadLibrary()
    readonly property FileDialog videoDialog: FileDialog {
        title: Tr.tr("Choose a video wallpaper")
        filterLabel: Tr.tr("Videos")
        filters: ["mp4", "webm", "mkv", "mov", "m4v", "ogv"]
        onAccepted: path => root.set("source", Paths.toLocalFile(path))
    }
    property int currentPage: 0
    property int pageSize: 25
    readonly property var filteredWallpapers: (LiveWallpapers.entries ?? []).filter(e => !query.text || (e.title ?? "").toLowerCase().includes(query.text.toLowerCase()))
    readonly property int totalPages: Math.max(1, Math.ceil(filteredWallpapers.length / pageSize))
    readonly property var pageItems: filteredWallpapers.slice(currentPage * pageSize, (currentPage + 1) * pageSize)

    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.extraSmall
        FeatureError {
            error: LiveWallpapers.error
        }
        GenericSettingRow {
            spec: ({
                    label: "Output",
                    type: "choice",
                    choices: Screens.screens.map(s => s.name)
                })
            value: root.outputName
            onEdited: v => {
                root.outputName = v;
                root.draft = LiveWallpapers.forScreen(v);
            }
        }
        GenericSettingRow {
            spec: ({
                    label: "Wallpaper type",
                    type: "choice",
                    choices: ["static", "video", "engine"]
                })
            value: root.draft.kind
            onEdited: v => root.set("kind", v)
        }
        TextFieldRow {
            label: Tr.tr("Wallpaper source")
            value: root.draft.source
            onEditingFinished: v => root.set("source", v)
        }
        RowButton {
            visible: root.draft.kind === "video"
            text: Tr.tr("Choose a video wallpaper")
            icon: "video_file"
            onClicked: root.videoDialog.open()
        }
        GenericSettingRow {
            spec: ({
                    label: "Scaling",
                    type: "choice",
                    choices: ["fill", "fit", "stretch", "default"]
                })
            value: root.draft.scaling
            onEdited: v => root.set("scaling", v)
        }
        ToggleRow {
            text: Tr.tr("Mute wallpaper")
            checked: root.draft.muted
            onToggled: root.set("muted", checked)
        }
        GenericSettingRow {
            spec: ({
                    label: "Volume",
                    type: "int",
                    min: 0,
                    max: 100
                })
            value: root.draft.volume
            onEdited: v => root.set("volume", v)
        }
        GenericSettingRow {
            visible: root.draft.kind === "engine"
            spec: ({
                    label: "FPS limit",
                    type: "int",
                    min: 5,
                    max: 120
                })
            value: root.draft.fps
            onEdited: v => root.set("fps", v)
        }
        ToggleRow {
            text: Tr.tr("Pause behind fullscreen windows")
            checked: root.draft.pauseFullscreen
            onToggled: root.set("pauseFullscreen", checked)
        }
        ToggleRow {
            text: Tr.tr("Pause on battery")
            checked: root.draft.pauseBattery
            onToggled: root.set("pauseBattery", checked)
        }
        ColumnLayout {
            Layout.fillWidth: true
            visible: root.draft.kind === "engine"
            spacing: Tokens.spacing.extraSmall
            ToggleRow {
                text: Tr.tr("Synchronize shell colors")
                checked: root.draft.syncColors
                onToggled: root.set("syncColors", checked)
            }
            ToggleRow {
                text: Tr.tr("Disable wallpaper mouse interaction")
                checked: root.draft.disableMouse
                onToggled: root.set("disableMouse", checked)
            }
            ToggleRow {
                text: Tr.tr("Disable particles")
                checked: root.draft.disableParticles
                onToggled: root.set("disableParticles", checked)
            }
            ToggleRow {
                text: Tr.tr("Disable parallax")
                checked: root.draft.disableParallax
                onToggled: root.set("disableParallax", checked)
            }
        }
        RowButton {
            text: Tr.tr("Apply wallpaper")
            icon: "check"
            disabled: LiveWallpapers.busy
            onClicked: LiveWallpapers.save(root.outputName, root.draft)
        }
        RowButton {
            text: Tr.tr("Restart wallpaper")
            icon: "restart_alt"
            onClicked: LiveWallpapers.restart(root.outputName)
        }
        RowButton {
            text: Tr.tr("Restore static wallpaper")
            icon: "stop"
            onClicked: {
                root.set("kind", "static");
                root.set("source", "");
                LiveWallpapers.save(root.outputName, root.draft);
            }
        }
        SectionHeader {
            text: "Wallpaper Engine · Steam Workshop"
        }
        InfoRow {
            label: "linux-wallpaperengine"
            value: LiveWallpapers.capabilities.engineAvailable ? Tr.tr("Available") : Tr.tr("Not installed")
        }
        TextFieldRow {
            label: Tr.tr("Additional Workshop paths")
            subtext: Tr.tr("One path or several paths separated by a semicolon")
            value: (LiveWallpapers.config.workshopPaths ?? []).join(";")
            onEditingFinished: v => LiveWallpapers.setPaths(v.split(";").map(s => s.trim()).filter(Boolean))
        }
        RowButton {
            text: Tr.tr("Refresh library")
            icon: "refresh"
            disabled: LiveWallpapers.busy
            onClicked: LiveWallpapers.reloadLibrary()
        }
        SearchBar {
            id: query
            Layout.fillWidth: true
            placeholderText: Tr.tr("Search Workshop wallpapers")
            onTextChanged: root.currentPage = 0
        }

        // Pagination Bar (Top)
        RowLayout {
            Layout.fillWidth: true
            visible: root.filteredWallpapers.length > root.pageSize
            spacing: Tokens.spacing.small

            IconButton {
                icon: "first_page"
                disabled: root.currentPage <= 0
                onClicked: root.currentPage = 0
            }
            IconButton {
                icon: "chevron_left"
                disabled: root.currentPage <= 0
                onClicked: root.currentPage = Math.max(0, root.currentPage - 1)
            }
            StyledText {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                font: Tokens.font.body.small
                color: Colours.palette.m3onSurfaceVariant
                text: Tr.tr("Page %1 of %2 (%3 wallpapers)").arg(root.currentPage + 1).arg(root.totalPages).arg(root.filteredWallpapers.length)
            }
            IconButton {
                icon: "chevron_right"
                disabled: root.currentPage >= root.totalPages - 1
                onClicked: root.currentPage = Math.min(root.totalPages - 1, root.currentPage + 1)
            }
            IconButton {
                icon: "last_page"
                disabled: root.currentPage >= root.totalPages - 1
                onClicked: root.currentPage = root.totalPages - 1
            }
        }

        // Empty state
        StyledText {
            visible: root.filteredWallpapers.length === 0
            Layout.fillWidth: true
            Layout.topMargin: Tokens.spacing.medium
            Layout.bottomMargin: Tokens.spacing.medium
            horizontalAlignment: Text.AlignHCenter
            text: Tr.tr("No wallpapers found")
            font: Tokens.font.body.medium
            color: Colours.palette.m3outline
        }

        // 5-Column Preview Grid
        GridLayout {
            Layout.fillWidth: true
            columns: 5
            columnSpacing: Tokens.spacing.small
            rowSpacing: Tokens.spacing.small

            Repeater {
                model: root.pageItems
                delegate: StyledRect {
                    id: wallpaper
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    implicitHeight: 140 * Tokens.scale
                    radius: Tokens.rounding.medium
                    clip: true
                    color: root.draft.source === wallpaper.modelData.path ? Colours.palette.m3primaryContainer : Colours.palette.m3surfaceContainer
                    border.color: root.draft.source === wallpaper.modelData.path ? Colours.palette.m3primary : "transparent"
                    border.width: root.draft.source === wallpaper.modelData.path ? 2 : 0

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 0

                        // Preview thumbnail container
                        Item {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 88 * Tokens.scale
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: wallpaper.modelData.preview ? Paths.fileUrl(wallpaper.modelData.preview) : ""
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                            }

                            // Selection badge or playlist toggle button
                            IconButton {
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 2
                                icon: root.draft.playlist.includes(wallpaper.modelData.path) ? "playlist_add_check" : "playlist_add"
                                color: root.draft.playlist.includes(wallpaper.modelData.path) ? Colours.palette.m3primary : Colours.palette.m3surface
                                onClicked: root.set("playlist", root.draft.playlist.includes(wallpaper.modelData.path) ? root.draft.playlist.filter(p => p !== wallpaper.modelData.path) : [...root.draft.playlist, wallpaper.modelData.path])
                            }
                        }

                        // Title on the card
                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            StyledText {
                                anchors.fill: parent
                                anchors.margins: Tokens.padding.extraSmall
                                text: wallpaper.modelData.title ?? ""
                                font: Tokens.font.label.small
                                color: root.draft.source === wallpaper.modelData.path ? Colours.palette.m3onPrimaryContainer : Colours.palette.m3onSurface
                                wrapMode: Text.Wrap
                                maximumLineCount: 2
                                elide: Text.ElideRight
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.draft = Object.assign({}, root.draft, {
                                kind: "engine",
                                source: wallpaper.modelData.path,
                                properties: {}
                            });
                        }
                    }
                }
            }
        }

        // Pagination Bar (Bottom)
        RowLayout {
            Layout.fillWidth: true
            visible: root.filteredWallpapers.length > root.pageSize
            spacing: Tokens.spacing.small

            IconButton {
                icon: "first_page"
                disabled: root.currentPage <= 0
                onClicked: root.currentPage = 0
            }
            IconButton {
                icon: "chevron_left"
                disabled: root.currentPage <= 0
                onClicked: root.currentPage = Math.max(0, root.currentPage - 1)
            }
            StyledText {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                font: Tokens.font.body.small
                color: Colours.palette.m3onSurfaceVariant
                text: Tr.tr("Page %1 of %2").arg(root.currentPage + 1).arg(root.totalPages)
            }
            IconButton {
                icon: "chevron_right"
                disabled: root.currentPage >= root.totalPages - 1
                onClicked: root.currentPage = Math.min(root.totalPages - 1, root.currentPage + 1)
            }
            IconButton {
                icon: "last_page"
                disabled: root.currentPage >= root.totalPages - 1
                onClicked: root.currentPage = root.totalPages - 1
            }
        }
        SettingsCard {
            title: Tr.tr("Wallpaper properties")
            icon: "tune"
            visible: !!root.entry

            Repeater {
                model: Object.entries(root.entry?.properties ?? {}).filter(([k, p]) => ["bool", "slider", "combo", "color", "textinput"].includes(p.type)).map(([k, p]) => ({
                            key: k,
                            label: String(p.text ?? k).replace(/<[^>]*>/g, " "),
                            type: p.type === "bool" ? "bool" : p.type === "slider" ? "number" : p.type === "combo" ? "choice" : "string",
                            min: p.min,
                            max: p.max,
                            default: p.value,
                            choices: p.options?.map(o => ({
                                        label: o.label ?? String(o.value),
                                        value: o.value
                                    })) ?? []
                        }))
                delegate: GenericSettingRow {
                    required property var modelData
                    spec: modelData
                    value: root.draft.properties[modelData.key] ?? modelData.default
                    onEdited: v => root.set("properties", Object.assign({}, root.draft.properties, {
                            [modelData.key]: v
                        }))
                }
            }
        }
        SettingsCard {
            title: Tr.tr("Wallpaper rotation")
            icon: "tune"

            InfoRow {
                label: Tr.tr("Selected wallpapers")
                value: String(root.draft.playlist.length)
            }
            GenericSettingRow {
                spec: ({
                        label: "Rotation interval (minutes)",
                        type: "int",
                        min: 1,
                        max: 1440
                    })
                value: root.draft.cycleMinutes
                onEdited: v => root.set("cycleMinutes", v)
            }
            ToggleRow {
                text: Tr.tr("Shuffle wallpapers")
                checked: root.draft.shuffle
                onToggled: root.set("shuffle", checked)
            }
            RowButton {
                text: Tr.tr("Save rotation")
                icon: "save"
                onClicked: LiveWallpapers.save(root.outputName, root.draft)
            }
        }
    }
}
