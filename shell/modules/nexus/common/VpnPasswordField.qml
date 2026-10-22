pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.I18n
import qs.components.controls
RowLayout {
    id:root
    property alias label:editor.label
    property alias subtext:editor.subtext
    property alias value:editor.value
    readonly property alias field:editor.field
    property bool secret:true
    property bool revealed:false
    signal valueEdited(string value)
    signal editingFinished(string value)
    function toggleVisibility():void {revealed=!revealed}
    Layout.fillWidth:true
    TextFieldRow {
        id:editor
        Layout.fillWidth:true
        field.echoMode:root.secret&&!root.revealed?TextInput.Password:TextInput.Normal
        onValueEdited:v=>root.valueEdited(v)
        onEditingFinished:v=>root.editingFinished(v)
    }
    IconButton {
        objectName:"vpnPasswordVisibility"
        visible:root.secret
        icon:root.revealed?"visibility_off":"visibility"
        type:IconButton.Text
        Accessible.name:root.revealed?Tr.tr("Hide password"):Tr.tr("Show password")
        onClicked:root.toggleVisibility()
    }
}
