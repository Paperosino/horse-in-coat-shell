pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.containers
import qs.components.controls
import qs.services
Variants {
    model:Quickshell.screens
    StyledWindow {
        id:window
        required property ShellScreen modelData
        screen:modelData
        name:"configuration-confirmation"
        visible:!!DesktopConfiguration.pending
        exclusionMode:ExclusionMode.Ignore
        implicitWidth:Math.min(480*Tokens.scale,screen.width-32)
        implicitHeight:Math.min(contents.implicitHeight+Tokens.padding.large*2,screen.height-24)
        WlrLayershell.layer:WlrLayer.Overlay
        WlrLayershell.keyboardFocus:visible&&screen.name===(Hypr.focusedMonitor?.name??Quickshell.screens[0]?.name)?WlrKeyboardFocus.Exclusive:WlrKeyboardFocus.None
        StyledRect {
            anchors.fill:parent;radius:Tokens.rounding.extraLarge
            color:Colours.palette.m3surfaceContainerHigh
            border.width:1*Tokens.scale;border.color:Colours.palette.m3outlineVariant
            FocusScope {
                anchors.fill:parent;focus:window.visible
                Keys.onEscapePressed:DesktopConfiguration.revert()
                Flickable {
                    id:scroll
                    anchors.fill:parent;anchors.margins:Tokens.padding.large
                    contentHeight:contents.implicitHeight;clip:true;boundsBehavior:Flickable.StopAtBounds
                    ColumnLayout {
                    id:contents
                    width:scroll.width
                    spacing:Tokens.spacing.medium
                    RowLayout {
                        Layout.fillWidth:true;spacing:Tokens.spacing.medium
                        MaterialIcon {text:"desktop_windows";fontStyle:Tokens.font.icon.large;color:Colours.palette.m3primary}
                        StyledText {Layout.fillWidth:true;text:Tr.tr("Keep this desktop profile?");wrapMode:Text.WordWrap;font:Tokens.font.title.large;Accessible.role:Accessible.AlertMessage}
                    }
                    StyledText {
                        Layout.fillWidth:true
                        text:DesktopConfiguration.pending?.name?Tr.tr("Desktop profile")+": "+DesktopConfiguration.pending.name:Tr.tr("Explore the desktop before keeping this appearance. Your previous configuration is ready to return.")
                        textFormat:Text.PlainText;wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant
                    }
                    StyledText {
                        Layout.fillWidth:true
                        text:Tr.tr("The previous desktop returns in %1 seconds.").arg(DesktopConfiguration.secondsLeft)
                        wrapMode:Text.WordWrap
                    }
                    Rectangle {
                        Layout.fillWidth:true;implicitHeight:4*Tokens.scale;radius:height/2;color:Colours.palette.m3surfaceContainerHighest;clip:true
                        Rectangle {width:parent.width*Math.min(1,DesktopConfiguration.secondsLeft/30);height:parent.height;radius:height/2;color:Colours.palette.m3primary;Behavior on width {NumberAnimation {duration:200}}}
                    }
                    StyledText {Layout.fillWidth:true;visible:!!DesktopConfiguration.error;text:Tr.tr(DesktopConfiguration.error);textFormat:Text.PlainText;wrapMode:Text.WordWrap;color:Colours.palette.m3error}
                    GridLayout {
                        Layout.fillWidth:true
                        columns:width>320*Tokens.scale?2:1
                        TextButton {Layout.fillWidth:true;text:Tr.tr("Restore previous settings");type:TextButton.Tonal;disabled:DesktopConfiguration.busy;onClicked:DesktopConfiguration.revert()}
                        TextButton {Layout.fillWidth:true;text:Tr.tr("Keep settings");type:TextButton.Filled;disabled:DesktopConfiguration.busy||DesktopConfiguration.secondsLeft===0;onClicked:DesktopConfiguration.confirm()}
                    }
                    }
                }
            }
        }
    }
}
