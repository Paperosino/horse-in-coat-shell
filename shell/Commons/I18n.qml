pragma Singleton
import QtQuick
import Quickshell
Singleton {
    function tr(key: string, values = {}): string { let s = key; for (const [k,v] of Object.entries(values)) s = s.replace("{" + k + "}", String(v)); return s; }
    readonly property string currentLanguage: Quickshell.env("LANG").split("_")[0]
}
