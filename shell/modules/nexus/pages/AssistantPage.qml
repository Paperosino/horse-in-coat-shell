pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import QtQuick.Layouts
import QtQuick.Controls as QQC
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    title: Tr.tr("AI assistant")
    objectName: "assistantPage"
    property bool showSettings: !Assistant.config.model
    function follow(): void { Qt.callLater(() => flickable.contentY = Math.max(0, flickable.contentHeight - flickable.height)); }
    readonly property Connections responseConnection: Connections { target: Assistant; function onResponseChanged() { if (!root.showSettings) root.follow(); } }
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.medium
        RowLayout {
            Layout.fillWidth: true
            TextButton { text: Tr.tr("Assistant settings"); isToggle: true; checked: root.showSettings; onClicked: root.showSettings = !root.showSettings }
            Item { Layout.fillWidth: true }
            TextButton { text: Tr.tr("Clear conversation"); enabled: !Assistant.busy; onClicked: Assistant.clear() }
        }
        FeatureError { error: Assistant.error }
        ColumnLayout {
            visible: root.showSettings
            Layout.fillWidth: true
            spacing: Tokens.spacing.extraSmall
            GenericSettingRow {
                spec: ({label: "Provider", type: "choice", choices: ["ollama", "compatible"]})
                value: Assistant.config.provider
                onEdited: v => Assistant.configure({provider: v})
            }
            TextFieldRow { label: Tr.tr("Server URL"); value: Assistant.config.endpoint ?? ""; onEditingFinished: value => Assistant.configure({endpoint: value}) }
            TextFieldRow { label: Tr.tr("Model"); value: Assistant.config.model ?? ""; onEditingFinished: value => Assistant.configure({model: value}) }
            RowButton { text: Tr.tr("Load available models"); icon: "refresh"; disabled: Assistant.settingsBusy; onClicked: Assistant.reloadModels() }
            Repeater {
                model: Assistant.models
                delegate: RowButton { required property string modelData; text: modelData; icon: "smart_toy"; onClicked: Assistant.configure({model: modelData}) }
            }
            TextFieldRow {
                label: Tr.tr("API key")
                value: ""
                placeholderText: Assistant.config.hasKey ? Tr.tr("Saved") : ""
                field.echoMode: TextInput.Password
                onEditingFinished: value => { if (value) { Assistant.configure({apiKey: value}); clear(); } }
            }
            RowButton { text: Tr.tr("Forget API key"); icon: "key_off"; onClicked: Assistant.forgetKey() }
            GenericSettingRow { spec: ({label: "Temperature", type: "number", min: 0, max: 2}); value: Assistant.config.temperature; onEdited: v => Assistant.configure({temperature: v}) }
            GenericSettingRow { spec: ({label: "Maximum response tokens", type: "int", min: 128, max: 65536, step: 128}); value: Assistant.config.maxTokens; onEdited: v => Assistant.configure({maxTokens: v}) }
            TextFieldRow { label: Tr.tr("System prompt"); value: Assistant.config.systemPrompt ?? ""; onEditingFinished: value => Assistant.configure({systemPrompt: value}) }
            ToggleRow { text: Tr.tr("Share display and shell settings with the assistant"); checked: !!Assistant.config.includeSystemContext; onToggled: Assistant.configure({includeSystemContext: checked}) }
            ToggleRow { text: Tr.tr("Save conversation history"); checked: !!Assistant.config.rememberHistory; onToggled: Assistant.configure({rememberHistory: checked}) }
        }
        Repeater {
            model: Assistant.messages
            delegate: StyledRect {
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: Math.max(32 * Tokens.scale, message.implicitHeight) + Tokens.padding.large * 2
                radius: Tokens.rounding.large
                color: modelData.role === "user" ? Colours.palette.m3surfaceContainerHigh : Colours.palette.m3surfaceContainerLow
                StyledText {
                    id: message
                    anchors.fill: parent
                    anchors.margins: Tokens.padding.large
                    anchors.rightMargin: Tokens.padding.large + 32 * Tokens.scale
                    text: modelData.content
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    font: Tokens.font.body.medium
                }
                IconButton { anchors.top: parent.top; anchors.right: parent.right; anchors.margins: Tokens.padding.small; icon: "content_copy"; onClicked: Quickshell.clipboardText = modelData.content }
            }
        }
        StyledText { Layout.fillWidth: true; visible: Assistant.busy; text: Assistant.response || Tr.tr("Thinking…"); wrapMode: Text.Wrap; textFormat: Text.PlainText }
        StyledRect {
            Layout.fillWidth: true
            implicitHeight: 130 * Tokens.scale
            radius: Tokens.rounding.large
            color: Colours.palette.m3surfaceContainer
            QQC.TextArea {
                id: prompt
                anchors.fill: parent
                padding: Tokens.padding.large
                color: Colours.palette.m3onSurface
                selectionColor: Colours.palette.m3primary
                font: Tokens.font.body.medium
                placeholderText: Tr.tr("Ask a question… (Ctrl+Enter to send)")
                wrapMode: TextEdit.Wrap
                background: Item {}
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Return && (event.modifiers & Qt.ControlModifier)) { send.clicked(); event.accepted = true; }
                }
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            TextButton { visible: Assistant.busy; text: Tr.tr("Stop"); onClicked: Assistant.stop() }
            TextButton {
                id: send
                text: Tr.tr("Send")
                enabled: !Assistant.busy && !Assistant.settingsBusy && !!Assistant.config.model && !!prompt.text.trim()
                onClicked: if (enabled) { Assistant.send(prompt.text); prompt.clear(); root.showSettings = false; root.follow(); }
            }
        }
    }
}
