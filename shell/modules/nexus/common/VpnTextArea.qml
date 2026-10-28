import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
ColumnLayout {
    id: root
    property string label
    property string value
    property string hint
    property bool password: false
    signal edited(string value)
    Layout.fillWidth: true
    StyledText { text:Tr.tr(root.label); font:Tokens.font.label.large }
    StyledText { visible:root.hint.length>0; text:Tr.tr(root.hint); color:Colours.palette.m3onSurfaceVariant; wrapMode:Text.WordWrap; Layout.fillWidth:true }
    ScrollView {
        Layout.fillWidth:true
        implicitHeight:Math.max(100,Math.min(220,area.contentHeight+24))
        TextArea {
            font: Tokens.font.body.medium
            renderType: FontRendering.nativeRendering ? TextEdit.NativeRendering : TextEdit.CurveRendering
            id:area
            Component.onCompleted:text=root.value
            Connections { target:root; function onValueChanged():void { if(!area.activeFocus)area.text=root.value } }
            wrapMode:TextEdit.Wrap
            color:Colours.palette.m3onSurface
            selectByMouse:true
            onTextChanged:if (activeFocus) root.edited(text)
            background:Rectangle { color:Colours.palette.m3surfaceContainer; radius:Tokens.rounding.medium; border.color:Colours.palette.m3outlineVariant }
        }
    }
}
