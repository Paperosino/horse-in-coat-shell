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
        name:"display-confirmation"
        visible:!!DisplayProfiles.pending
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
                Keys.onEscapePressed:DisplayProfiles.revert()
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
                        StyledText {Layout.fillWidth:true;text:Tr.tr("Keep these display settings?");wrapMode:Text.WordWrap;font:Tokens.font.title.large;Accessible.role:Accessible.AlertMessage}
                    }
                    StyledText {
                        Layout.fillWidth:true
                        text:DisplayProfiles.pending?.label?Tr.tr("Display profile")+": "+DisplayProfiles.pending.label:Tr.tr("Check that all screens are visible and arranged correctly.")
                        textFormat:Text.PlainText;wrapMode:Text.WordWrap;color:Colours.palette.m3onSurfaceVariant
                    }
                    StyledText {
                        Layout.fillWidth:true
                        text:Tr.tr("Previous settings return automatically in %1 seconds.").arg(DisplayProfiles.secondsLeft)
                        wrapMode:Text.WordWrap
                    }
                    Rectangle {
                        Layout.fillWidth:true;implicitHeight:4*Tokens.scale;radius:height/2;color:Colours.palette.m3surfaceContainerHighest;clip:true
                        Rectangle {width:parent.width*Math.min(1,DisplayProfiles.secondsLeft/(DisplayProfiles.settings.timeout??15));height:parent.height;radius:height/2;color:Colours.palette.m3primary;Behavior on width {Anim {type:Anim.FastEffects}}}
                    }
                    StyledText {Layout.fillWidth:true;visible:!!DisplayProfiles.error;text:Tr.tr(DisplayProfiles.error);textFormat:Text.PlainText;wrapMode:Text.WordWrap;color:Colours.palette.m3error}
                    GridLayout {
                        Layout.fillWidth:true
                        columns:width>320*Tokens.scale?2:1
                        TextButton {Layout.fillWidth:true;text:Tr.tr("Restore previous settings");type:TextButton.Tonal;disabled:DisplayProfiles.busy;onClicked:DisplayProfiles.revert()}
                        TextButton {Layout.fillWidth:true;text:Tr.tr("Keep settings");type:TextButton.Filled;disabled:DisplayProfiles.busy||DisplayProfiles.secondsLeft===0;onClicked:DisplayProfiles.confirm()}
                    }
                    }
                }
            }
        }
    }
}
