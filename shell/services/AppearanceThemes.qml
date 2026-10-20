pragma Singleton
pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.I18n
import qs.utils
Singleton {
    id: root
    property var icons: []
    property var cursors: []
    property var current: ({icons:"",cursors:"",size:24})
    property bool flatpak: false
    property string error: ""
    property string notice: ""
    readonly property bool loading: catalogue.running
    readonly property bool busy: mutation.running
    readonly property string helper: Paths.toLocalFile(Qt.resolvedUrl("../assets/appearance_themes.py"))
    function reload(): void { if (!loading && !busy) catalogue.running = true; }
    function apply(kind: string, theme: string, size: int): void {
        if (busy || !theme) return;
        error = notice = "";
        mutation.command = ["python3",helper,"apply",kind,theme,"--size",String(size)];
        mutation.running = true;
    }
    Component.onCompleted: reload()
    Process {
        id: catalogue
        command: ["python3",root.helper,"list"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const data = JSON.parse(text);
                    if (data.error) { root.error = data.error; return; }
                    root.icons = data.icons; root.cursors = data.cursors;
                    root.current = data.current; root.flatpak = data.flatpak;
                } catch (e) { root.error = Tr.tr("Unable to read appearance themes"); }
            }
        }
    }
    Process {
        id: mutation
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const data = JSON.parse(text);
                    if (data.error) { root.error = data.error; return; }
                    root.current = data.current;
                    root.notice = data.warnings?.length ? Tr.tr("Saved. Some applications could not be updated immediately.") + "\n" + data.warnings.join("\n") : Tr.tr("Applied. Reopen applications that still use the previous theme.");
                } catch (e) { root.error = Tr.tr("Unable to apply appearance theme"); }
            }
        }
        onExited: (code, status) => { if ((code || status) && !root.error) root.error = Tr.tr("Unable to apply appearance theme"); }
    }
}
