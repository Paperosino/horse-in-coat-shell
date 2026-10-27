import Quickshell
import Quickshell.Wayland
import Hyprstack.Config
import Hyprstack.Components

// qmllint disable uncreatable-type
PanelWindow {
    id: root
    // qmllint enable uncreatable-type
    required property string name

    WlrLayershell.namespace: `hyprstack-${name}`
    color: "transparent"

    GraphicsCache { cacheKey: root.name }

    Config.screen: screen?.name??""
    Tokens.screen: screen?.name??""

    contentItem.Config.screen: screen?.name??""
    contentItem.Tokens.screen: screen?.name??""
}
