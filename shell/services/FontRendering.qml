pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Config
import Hyprstack.I18n
import qs.utils

Singleton {
    id: root
    readonly property bool antialias: GlobalConfig.appearance.font.antialias
    readonly property string hinting: GlobalConfig.appearance.font.hinting
    // Distance fields ignore hinting. Use the native font engine when the
    // user explicitly requests grid fitting or disables glyph antialiasing.
    readonly property bool nativeRendering: !antialias || hinting !== "none"
    property string error: ""
    property string notice: ""
    property bool pending: false
    readonly property bool busy: applyProcess.running || debounce.running
    property list<string> backendCommand: ["python3", Paths.toLocalFile(Qt.resolvedUrl("../assets/gtk_theme.py"))]
    Connections {
        target: GlobalConfig.appearance.font
        function onAntialiasChanged(): void { debounce.restart(); }
        function onHintingChanged(): void { debounce.restart(); }
    }
    Timer {
        id: debounce
        interval: 300
        onTriggered: {
            if (applyProcess.running) { root.pending = true; return; }
            root.pending = false;
            root.error = root.notice = "";
            applyProcess.command = [...root.backendCommand, "fonts", String(root.antialias), root.hinting];
            applyProcess.running = true;
        }
    }
    Process {
        id: applyProcess
        stderr: StdioCollector { id: diagnostics }
        onExited: (code, status) => {
            if (code || status) root.error = Tr.tr("Unable to apply font rendering") + "\n" + diagnostics.text;
            else if (diagnostics.text.trim()) root.notice = Tr.tr("Saved. Some applications could not be updated immediately.") + "\n" + diagnostics.text;
            else root.notice = Tr.tr("Applied. Reopen applications that cache font settings. Applications with their own text renderer may ignore system preferences.");
            if (root.pending) debounce.restart();
        }
    }
}
