import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.modules.nexus.common
PageBase {
    id: root
    title: Tr.tr("Accessibility")
    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.cappedWidth
        spacing: Tokens.spacing.extraSmall / 2
        ToggleRow {
            first: true
            text: Tr.tr("High contrast")
            subtext: Tr.tr("Use an opaque, high-contrast palette in the shell")
            checked: GlobalConfig.appearance.highContrast
            onToggled: GlobalConfig.appearance.highContrast = checked
        }
        ToggleRow {
            text: Tr.tr("Reduce motion")
            subtext: Tr.tr("Disable shell transitions and animated interaction effects")
            checked: GlobalConfig.appearance.reducedMotion
            onToggled: GlobalConfig.appearance.reducedMotion = checked
        }
        StepperRow {
            last: true
            label: Tr.tr("Interface scale")
            value: GlobalConfig.appearance.scale
            from: 0.75; to: 2; stepSize: 0.05
            onMoved: value => GlobalConfig.appearance.scale = value
        }
        InfoRow {
            first: true
            label: Tr.tr("Keyboard navigation")
            value: Tr.tr("Tab / Shift+Tab to move, Enter / Space to activate")
        }
        InfoRow {
            last: true
            label: Tr.tr("Screen reader support")
            value: Tr.tr("Controls expose accessibility names and actions. Full screen reader compatibility still requires testing with Orca in a live session.")
        }
    }
}
