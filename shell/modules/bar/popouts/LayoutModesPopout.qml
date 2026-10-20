pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus
import qs.modules.nexus.common
ColumnLayout {
    id: root
    required property PopoutState popouts
    spacing: Tokens.spacing.small
    implicitWidth: 300 * Tokens.scale
    StyledText {
        text: Tr.tr("Window layout")
        font: Tokens.font.body.builders.medium.weight(Font.Medium).build()
    }
    Repeater {
        model: LayoutModes.modes
        RowButton {
            required property int index
            required property var modelData
            first: index === 0
            last: index === 3
            text: modelData.label
            icon: modelData.icon
            trailingIcon: LayoutModes.mode === modelData.id ? "check" : ""
            // Commands are queued; a concurrent file refresh must not lose a click.
            onClicked: LayoutModes.select(modelData.id)
        }
    }
    FeatureError { error: LayoutModes.error }
    RowButton {
        first: true
        last: true
        text: Tr.tr("Layout settings")
        icon: "settings"
        onClicked: { root.popouts.hasCurrent = false; WindowFactory.openPage(LayoutModes.mode === "canvas" ? "canvas" : "windows"); }
    }
}
