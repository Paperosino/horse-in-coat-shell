pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import qs.utils

Singleton {
    id: root
    property bool enabled: false
    property int lightHour: 8
    property int darkHour: 20
    property string dayTheme: ""
    property string nightTheme: ""
    property string lastSelection: ""
    property bool loaded: false
    function save(value: var): void {
        enabled = value.enabled ?? enabled;
        lightHour = Math.max(0, Math.min(23, value.lightHour ?? lightHour));
        darkHour = Math.max(0, Math.min(23, value.darkHour ?? darkHour));
        dayTheme = value.dayTheme ?? dayTheme;
        nightTheme = value.nightTheme ?? nightTheme;
        storage.setText(JSON.stringify({enabled, lightHour, darkHour, dayTheme, nightTheme}));
        lastSelection = "";
        apply();
    }
    function apply(): void {
        if (!enabled || !loaded) return;
        const hour = new Date().getHours();
        const light = lightHour < darkHour ? hour >= lightHour && hour < darkHour : hour >= lightHour || hour < darkHour;
        const mode = light ? "light" : "dark";
        const theme = light ? dayTheme : nightTheme;
        const selection = theme + ":" + mode;
        if (selection === lastSelection || ThemeSchemes.busy) return;
        lastSelection = selection;
        if (theme) ThemeSchemes.apply(theme, mode); else ThemeSchemes.setMode(mode);
    }
    FileView {
        id: storage
        path: `${Paths.config}/theme-schedule.json`
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const d = JSON.parse(text()); root.enabled = !!d.enabled; root.lightHour = d.lightHour ?? 8; root.darkHour = d.darkHour ?? 20;
                root.dayTheme = d.dayTheme ?? ""; root.nightTheme = d.nightTheme ?? "";
            } catch (e) { console.warn("Theme schedule:", e); }
            root.loaded = true; root.apply();
        }
        onLoadFailed: root.loaded = true
    }
    Timer { interval: 60000; repeat: true; running: root.enabled; onTriggered: root.apply() }
}
