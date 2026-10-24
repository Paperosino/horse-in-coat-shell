import Quickshell
import Quickshell.Wayland
import Hyprstack.Config

// qmllint disable uncreatable-type
PanelWindow {
    // qmllint enable uncreatable-type
    required property string name

    WlrLayershell.namespace: `hyprstack-${name}`
    color: "transparent"

    contentItem.Config.screen: screen?.name??""
    contentItem.Tokens.screen: screen?.name??""
}
