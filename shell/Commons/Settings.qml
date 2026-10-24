pragma Singleton
import QtQuick
import Quickshell
import Hyprstack.Config
import qs.services
Singleton {
    readonly property var data: ({general: {avatarImage: "", radiusRatio: 1}, ui: {fontDefault: Tokens.font.body.medium.family, fontFixed: "monospace"}, colorSchemes: {darkMode: !Colours.currentLight}, plugins: {states: Plugins.plugins.reduce((a,p) => {a[p.id] = p.enabled; return a;}, {})}})
}
