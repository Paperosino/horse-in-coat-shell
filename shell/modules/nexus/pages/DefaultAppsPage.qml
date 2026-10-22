pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Services
import Quickshell.Widgets
import Hyprstack
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
import qs.utils
import qs.modules.nexus.common
import qs.modules.launcher.items
import qs.modules.launcher.services

PageBase {
    id: root

    title: Tr.tr("Default applications")

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2

        FeatureError { error: DefaultApps.error }

        // Default applications
        SectionHeader {
            first: true
            text: Tr.tr("Default applications")
        }

        DefaultRow {
            first: true
            icon: "language"
            category: "browser"
            label: Tr.trCtx("Web browser", "default app category")
            currentApp: DefaultApps.browserApp
            categoryMatch: app => (app.categories || []).includes("WebBrowser") || (app.categories || []).includes("Network") || /browser|chrome|firefox|vivaldi|opera|edge|brave|zen/i.test(app.id + " " + app.name)
            onSelected: app => DefaultApps.setDefault("browser", app)
        }

        DefaultRow {
            icon: "folder"
            category: "fileManager"
            label: Tr.trCtx("File manager", "default app category")
            currentApp: DefaultApps.fileManagerApp
            categoryMatch: app => (app.categories || []).includes("FileManager") || /file|nautilus|thunar|dolphin|pcmanfm|nemo/i.test(app.id + " " + app.name)
            onSelected: app => DefaultApps.setDefault("fileManager", app)
        }

        DefaultRow {
            icon: "edit_note"
            category: "textEditor"
            label: Tr.trCtx("Text editor", "default app category")
            currentApp: DefaultApps.textEditorApp
            categoryMatch: app => (app.categories || []).includes("TextEditor") || (app.categories || []).includes("Development") || (app.categories || []).includes("IDE") || /editor|kate|code|gedit|sublime|text|nvim|vim/i.test(app.id + " " + app.name)
            onSelected: app => DefaultApps.setDefault("textEditor", app)
        }

        DefaultRow {
            icon: "image"
            category: "imageViewer"
            label: Tr.trCtx("Image viewer", "default app category")
            currentApp: DefaultApps.imageViewerApp
            categoryMatch: app => (app.categories || []).includes("Graphics") || (app.categories || []).includes("Viewer") || /image|photo|view|gwenview|eog|gimp|inkscape/i.test(app.id + " " + app.name)
            onSelected: app => DefaultApps.setDefault("imageViewer", app)
        }

        DefaultRow {
            icon: "movie"
            category: "videoPlayer"
            label: Tr.trCtx("Video player", "default app category")
            currentApp: DefaultApps.videoPlayerApp
            categoryMatch: app => ((app.categories || []).includes("Video") || (app.categories || []).includes("Player") || (app.categories || []).includes("AudioVideo")) && !/recorder|burn/i.test(app.name) || /mpv|vlc|totem|celluloid|player/i.test(app.id + " " + app.name)
            onSelected: app => DefaultApps.setDefault("videoPlayer", app)
        }

        DefaultRow {
            icon: "music_note"
            category: "audioPlayer"
            label: Tr.trCtx("Music player", "default app category")
            currentApp: DefaultApps.audioPlayerApp
            categoryMatch: app => ((app.categories || []).includes("Audio") || (app.categories || []).includes("Music") || (app.categories || []).includes("AudioVideo")) || /music|audio|clementine|rhythmbox|spotify|mpv/i.test(app.id + " " + app.name)
            onSelected: app => DefaultApps.setDefault("audioPlayer", app)
        }

        DefaultRow {
            icon: "picture_as_pdf"
            category: "pdfViewer"
            label: Tr.trCtx("PDF documents", "default app category")
            currentApp: DefaultApps.pdfViewerApp
            categoryMatch: app => (app.categories || []).includes("Office") || (app.categories || []).includes("Viewer") || /pdf|reader|document|evince|okular|onlyoffice|libreoffice/i.test(app.id + " " + app.name)
            onSelected: app => DefaultApps.setDefault("pdfViewer", app)
        }

        DefaultRow {
            icon: "book_2"
            category: "ebookReader"
            label: Tr.trCtx("E-books", "default app category")
            currentApp: DefaultApps.lookup(DefaultApps.defaults.ebookReader ?? "")
        }

        DefaultRow {
            icon: "folder_zip"
            category: "archiveManager"
            label: Tr.trCtx("Archives", "default app category")
            currentApp: DefaultApps.lookup(DefaultApps.defaults.archiveManager ?? "")
        }

        DefaultRow {
            icon: "description"
            category: "wordProcessor"
            label: Tr.trCtx("Text documents", "default app category")
            currentApp: DefaultApps.lookup(DefaultApps.defaults.wordProcessor ?? "")
        }

        DefaultRow {
            icon: "table_chart"
            category: "spreadsheet"
            label: Tr.trCtx("Spreadsheets", "default app category")
            currentApp: DefaultApps.lookup(DefaultApps.defaults.spreadsheet ?? "")
        }

        DefaultRow {
            icon: "slideshow"
            category: "presentation"
            label: Tr.trCtx("Presentations", "default app category")
            currentApp: DefaultApps.lookup(DefaultApps.defaults.presentation ?? "")
        }

        DefaultRow {
            icon: "mail"
            category: "mailClient"
            label: Tr.trCtx("Email", "default app category")
            currentApp: DefaultApps.lookup(DefaultApps.defaults.mailClient ?? "")
        }

        DefaultRow {
            icon: "download"
            category: "torrentClient"
            label: Tr.trCtx("Torrents and magnet links", "default app category")
            currentApp: DefaultApps.lookup(DefaultApps.defaults.torrentClient ?? "")
        }

        DefaultRow {
            icon: "terminal"
            category: "terminal"
            label: Tr.trCtx("Terminal", "default app category")
            currentApp: DefaultApps.terminalApp
            status: currentApp?.name ?? GlobalConfig.general.apps.terminal.join(" ")
            categoryMatch: app => (app.categories || []).includes("TerminalEmulator") || /terminal|term|kitty|alacritty|wezterm|foot|konsole/i.test(app.id + " " + app.name)
            onSelected: app => DefaultApps.setDefault("terminal", app)
        }

        DefaultRow {
            last: true
            icon: "volume_up"
            category: "audioSettings"
            label: Tr.trCtx("Audio settings", "default app category")
            status: GlobalConfig.general.apps.audio.join(" ")
            onSelected: app => GlobalConfig.general.apps.audio = app.command
        }


    }

    component DefaultRow: PopupRow {
        id: row

        property string category: ""
        property var currentApp: null
        property var categoryMatch: null

        readonly property int popupHeight: root.flickable.height - y + root.flickable.contentY - Tokens.padding.large - Tokens.padding.extraExtraLarge

        enabled: !DefaultApps.busy
        signal selected(app: var)
        onSelected: app => { if (!["browser", "fileManager", "textEditor", "imageViewer", "videoPlayer", "audioPlayer", "pdfViewer", "terminal", "audioSettings"].includes(category)) DefaultApps.setDefault(category, app); }

        status: currentApp?.name ?? Tr.tr("Not set")

        keepPopupAsChild: {
            if (root.nState.animatingContainer || root.opacity < 1)
                return true;

            let p = root.parent;
            while (p && p.objectName !== "PageContainer")
                p = p.parent;
            return p?.opacity < 1;
        }
        popup.topMovement: Math.max(Tokens.sizes.nexus.minPopupHeight - popupHeight, Tokens.padding.large)

        Loader {
            anchors.centerIn: parent
            active: row.popup.animDriver > 0

            sourceComponent: Item {
                implicitWidth: Math.max(320 * Tokens.scale, Tokens.sizes.nexus.popupWidth)
                implicitHeight: CUtils.clamp(row.popupHeight, Tokens.sizes.nexus.minPopupHeight, Tokens.sizes.nexus.maxPopupHeight)
                ColumnLayout {
                anchors.fill: parent
                spacing: Tokens.spacing.small

                SearchBar {
                    id: searchField

                    Layout.fillWidth: true
                    Layout.margins: Tokens.padding.small
                    Layout.bottomMargin: 0
                    topPadding: Tokens.padding.medium
                    bottomPadding: Tokens.padding.medium

                    placeholderText: Tr.tr("Search applications...")

                    Component.onCompleted: forceActiveFocus()
                }

                VerticalFadeListView {
                    id: list

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    model: {
                        const q = searchField.text.trim().toLowerCase();
                        let apps = [...ApplicationCatalogue.applications.values];
                        if (q) {
                            apps = apps.filter(a => {
                                const name = (a.name || "").toLowerCase();
                                const gen = (a.genericName || "").toLowerCase();
                                const comment = (a.comment || "").toLowerCase();
                                const id = (a.id || "").toLowerCase();
                                return name.includes(q) || gen.includes(q) || comment.includes(q) || id.includes(q);
                            });
                        }
                        const favourited = new Set(apps.filter(a => Strings.testRegexList(GlobalConfig.launcher.favouriteApps, a.id)));
                        return apps.sort((a, b) => {
                            if (!q) {
                                const matchA = (DefaultApps.candidates[row.category] ?? []).includes(a.id.replace(/\.desktop$/, "")) ? 2 : row.categoryMatch?.(a) ? 1 : 0;
                                const matchB = (DefaultApps.candidates[row.category] ?? []).includes(b.id.replace(/\.desktop$/, "")) ? 2 : row.categoryMatch?.(b) ? 1 : 0;
                                if (matchA !== matchB) return matchB - matchA;
                            }
                            return (favourited.has(b) - favourited.has(a)) || a.name.localeCompare(b.name);
                        });
                    }

                    delegate: AppItem {
                        required property int index
                        screenState: ShellState.forScreen(root.nState.screen)
                        selectionOnly: true
                        onChosen: entry => { row.popup.open = false; row.selected(entry); }
                    }
                }
                }
            }
        }
    }
}
