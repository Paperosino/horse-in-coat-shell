pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
ColumnLayout {
    id: root
    Layout.fillWidth: true
    spacing: Tokens.spacing.extraSmall / 2
    NativeSystemBackend { id: system; section: "power"; watching: root.visible }
    SectionHeader { first: true; text: Tr.tr("Power profile") }
    FeatureError { error: system.error }
    GenericSettingRow {
        visible: !!system.state.available
        spec: ({label: "Power profile", type: "choice", choices: (system.state.profiles ?? []).map(p => ({value: p, label: p === "power-saver" ? Tr.tr("Power saver") : p === "balanced" ? Tr.tr("Balanced") : Tr.tr("Performance")}))})
        value: system.state.active
        enabled: !system.busy
        onEdited: v => system.apply("profile", {profile: v})
    }
    InfoRow { visible: !!system.state.degraded; first: true; last: true; label: Tr.tr("Performance limitation"); value: system.state.degraded ?? "" }
}
