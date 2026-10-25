pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.Services
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus.common
PageBase {
    id:root
    title:Tr.tr("Focus & breaks");pageIcon:"timer"
    readonly property var prefs:GlobalConfig.utilities.comfort
    property DesktopBackend backend:DesktopBackend {}
    property int awakeMinutes:60
    function set(key,value):void {
        prefs[key]=value;
        if((key==="focusQuiet"||key==="focusKeepAwake") && (Comfort.running||Comfort.focus.paused))
            backend.call("comfort.focus-options",{quiet:prefs.focusQuiet,keepAwake:prefs.focusKeepAwake});
    }
    ColumnLayout {
        width:root.cappedWidth;anchors.horizontalCenter:parent.horizontalCenter;spacing:Tokens.spacing.large
        SettingsCard {
            title:Tr.tr("A little time to concentrate");icon:"timer"
            description:Tr.tr("Work and break timers survive shell reloads. A new work interval starts only when you choose; your normal notification and sleep settings are preserved.")
            InfoRow {label:Tr.tr("Current interval");value:Comfort.focus.phase==="work"?Tr.tr("Focus time"):Comfort.focus.phase==="break"?Tr.tr("Break time"):Tr.tr("Ready to start")}
            StyledText {Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter;text:Math.floor(Comfort.secondsLeft/60)+":"+String(Comfort.secondsLeft%60).padStart(2,"0");font:Tokens.font.headline.large;color:Colours.palette.m3primary}
            RowButton {text:Tr.tr("Start focus time");icon:"play_arrow";disabled:Comfort.running||!!Comfort.focus.paused||root.backend.busy;onClicked:root.backend.call("comfort.focus-start",{minutes:root.prefs.focusMinutes,breakMinutes:root.prefs.breakMinutes,longBreakMinutes:root.prefs.longBreakMinutes,rounds:root.prefs.focusRounds,quiet:root.prefs.focusQuiet,keepAwake:root.prefs.focusKeepAwake})}
            RowButton {visible:Comfort.running||!!Comfort.focus.paused;text:Comfort.focus.paused?Tr.tr("Resume timer"):Tr.tr("Pause timer");icon:Comfort.focus.paused?"play_arrow":"pause";onClicked:root.backend.call(Comfort.focus.paused?"comfort.focus-resume":"comfort.focus-pause",{})}
            RowButton {visible:Comfort.running||!!Comfort.focus.paused;text:Tr.tr("Stop timer");icon:"stop";onClicked:root.backend.call("comfort.focus-stop",{})}
            StepperRow {label:Tr.tr("Focus duration (minutes)");from:1;to:240;value:root.prefs.focusMinutes;onMoved:value=>root.set("focusMinutes",value)}
            StepperRow {label:Tr.tr("Break duration (minutes)");from:1;to:60;value:root.prefs.breakMinutes;onMoved:value=>root.set("breakMinutes",value)}
            ToggleRow {text:Tr.tr("Silence notifications during focus");checked:root.prefs.focusQuiet;onToggled:root.set("focusQuiet",checked)}
            ToggleRow {text:Tr.tr("Keep awake during focus");checked:root.prefs.focusKeepAwake;onToggled:root.set("focusKeepAwake",checked)}
        }
        SettingsCard {
            title:Tr.tr("Long breaks");icon:"self_improvement";collapsible:true;expanded:false
            StepperRow {label:Tr.tr("Work intervals before a long break");from:1;to:12;value:root.prefs.focusRounds;onMoved:value=>root.set("focusRounds",value)}
            StepperRow {label:Tr.tr("Long break duration (minutes)");from:1;to:120;value:root.prefs.longBreakMinutes;onMoved:value=>root.set("longBreakMinutes",value)}
        }
        SettingsCard {
            title:Tr.tr("Stay awake for a while");icon:"coffee"
            description:Tr.tr("Temporarily prevent idle sleep without changing your regular power settings. This does not override lid handling or a manual suspend request.")
            Repeater {model:[15,30,60,120];RowButton {required property int modelData;text:Tr.tr("Stay awake for %1 minutes").arg(modelData);icon:"schedule";onClicked:root.backend.call("comfort.awake",{minutes:modelData})}}
            StepperRow {label:Tr.tr("Custom wake lock (minutes)");from:1;to:1440;stepSize:5;value:root.awakeMinutes;onMoved:value=>root.awakeMinutes=value}
            RowButton {text:Tr.tr("Start temporary wake lock");icon:"coffee";onClicked:root.backend.call("comfort.awake",{minutes:root.awakeMinutes})}
            InfoRow {visible:Comfort.awake;label:Tr.tr("Until");value:Qt.formatTime(new Date(Comfort.state.awakeDeadline??0),"hh:mm")}
            RowButton {visible:Comfort.awake;text:Tr.tr("End temporary wake lock");icon:"close";onClicked:root.backend.call("comfort.awake",{minutes:0})}
        }
        FeatureError {error:root.backend.error}
    }
}
