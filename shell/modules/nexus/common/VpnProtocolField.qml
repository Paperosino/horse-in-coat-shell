pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.I18n
import Hyprstack.Config
import qs.components.controls
ColumnLayout {
    id:root
    required property var spec
    property var settings:({})
    property var credentials:({})
    property bool showSection:false
    signal edited(string key,var value)
    signal credentialEdited(string key,string value)
    signal fileRequested(string key)
    Layout.fillWidth:true;spacing:Tokens.spacing.extraSmall/2
    SectionHeader {visible:root.showSection&&!!root.spec.section;text:Tr.tr(root.spec.section??"")}
    Loader {
        Layout.fillWidth:true
        sourceComponent:root.spec.type==="secret"?secret:root.spec.type==="file"?file:normal
    }
    Component {
        id:normal
        GenericSettingRow {
            spec:root.spec
            value:root.spec.type==="bool"?root.settings[root.spec.key]==="yes":(root.settings[root.spec.key]??"")
            onEdited:v=>root.edited(root.spec.key,root.spec.type==="bool"?(v?"yes":"no"):String(v))
        }
    }
    Component {
        id:secret
        TextFieldRow {
            label:Tr.tr(root.spec.label)
            subtext:Tr.tr("Leave empty to keep the stored credential")
            value:root.credentials[root.spec.key]??""
            field.echoMode:TextInput.Password
            onValueEdited:v=>root.credentialEdited(root.spec.key,v)
        }
    }
    Component {
        id:file
        RowLayout {
            Layout.fillWidth:true
            TextFieldRow {label:Tr.tr(root.spec.label);value:root.settings[root.spec.key]??"";onValueEdited:v=>root.edited(root.spec.key,v)}
            IconButton {icon:"folder_open";type:IconButton.Text;Accessible.name:Tr.tr("Choose file");onClicked:root.fileRequested(root.spec.key)}
        }
    }
}
