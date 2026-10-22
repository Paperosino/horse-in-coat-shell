pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.Services
import Hyprstack.Config
import qs.components

Singleton {
    id: root
    property var defaults: ({})
    property var candidates: ({})
    property var formats: ({})
    readonly property bool busy: backend.busy
    readonly property string error: backend.error
    function lookup(id: string): var {
        if (!id) return null;
        return ApplicationCatalogue.byId(id) ?? ApplicationCatalogue.byId(id.replace(/\.desktop$/, "")) ?? null;
    }
    readonly property var browserApp: lookup(defaults.browser ?? "")
    readonly property var fileManagerApp: lookup(defaults.fileManager ?? "")
    readonly property var textEditorApp: lookup(defaults.textEditor ?? "")
    readonly property var imageViewerApp: lookup(defaults.imageViewer ?? "")
    readonly property var videoPlayerApp: lookup(defaults.videoPlayer ?? "")
    readonly property var audioPlayerApp: lookup(defaults.audioPlayer ?? "")
    readonly property var pdfViewerApp: lookup(defaults.pdfViewer ?? "")
    readonly property var terminalApp: ApplicationCatalogue.heuristicLookup(GlobalConfig.general.apps.terminal[0] ?? "")
    function accept(data: var): void { if (!data.error) { defaults = data.defaults; candidates = data.candidates; formats = data.formats; } }
    function reload(): void { backend.call([], null, accept); }
    function setDefault(category: string, app: var): void {
        if (!app) return;
        if (category === "terminal") { GlobalConfig.general.apps.terminal = app.command; return; }
        backend.call(["set", category, app.id], null, data => {
            if (data.error) return;
            accept(data);
            if (category === "fileManager") GlobalConfig.general.apps.explorer = app.command;
            if (category === "videoPlayer") GlobalConfig.general.apps.playback = app.command;
            // GlobalConfig.general.apps.audio opens the audio settings tool,
            // independently of the music player used for audio files.
        });
    }
    Component.onCompleted: reload()
    FeatureBackend { id: backend; helper: "default_apps_helper.py" }
}
