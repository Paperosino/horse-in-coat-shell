pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Bluetooth
import Hyprstack
import Hyprstack.Config
import Hyprstack.Services
import Hyprstack.I18n
import qs.modules.nexus
import qs.components.misc
Singleton {
    id: root
    readonly property var preferences: GlobalConfig.utilities.comfort
    readonly property var state: DesktopJobs.available ? DesktopJobs.comfort : ({})
    readonly property var focus: state.focus ?? ({})
    readonly property bool focusing: focus.phase === "work" && !focus.paused && focus.deadline > clock
    readonly property bool running: (focus.deadline ?? 0) > clock
    readonly property bool awake: (state.awakeDeadline ?? 0) > clock
    property var recordingStreams: Audio.microphoneStreams
    readonly property bool callActive: preferences.quietDuringCalls && recordingStreams.length > 0
    readonly property bool quiet: (focusing && !!focus.quiet) || callActive
    readonly property bool inhibit: awake || (focusing && !!focus.keepAwake)
    readonly property int secondsLeft: focus.paused ? focus.remainingSeconds ?? 0 : Math.max(0, Math.ceil(((focus.deadline ?? 0) - clock) / 1000))
    property double clock: Date.now()
    property var warnedBatteries: ({})
    function refreshClock(): void { clock = Date.now(); }
    function beginFocus(): void {
        DesktopJobs.request("comfort.focus-start", {minutes:preferences.focusMinutes, breakMinutes:preferences.breakMinutes,
            longBreakMinutes:preferences.longBreakMinutes, rounds:preferences.focusRounds,
            quiet:preferences.focusQuiet, keepAwake:preferences.focusKeepAwake});
    }
    function plainText(): void {
        DesktopJobs.request("comfort.plain-text", {}, result => Toaster.toast(result.error ? Tr.tr("Clipboard unavailable") : Tr.tr("Plain text is ready"),
            result.error ? result.error : Tr.tr("Press Ctrl+V to paste without formatting"), "content_paste"), root);
    }
    function checkBattery(device): void {
        const key = device.address;
        if (!device.connected || !device.batteryAvailable) return;
        const threshold = Math.max(5, Math.min(50, preferences.bluetoothBatteryThreshold)) / 100;
        if (device.battery > threshold + 0.1) {
            if (warnedBatteries[key]) { const copy = Object.assign({},warnedBatteries); delete copy[key]; warnedBatteries=copy; }
            return;
        }
        if (preferences.bluetoothBatteryAlerts && !quiet && !Presentation.active && device.battery <= threshold && !warnedBatteries[key]) {
            const warnings=Object.assign({}, warnedBatteries, {[key]:true});
            if(Object.keys(warnings).length>128)delete warnings[Object.keys(warnings)[0]];
            warnedBatteries=warnings;
            Toaster.toast(Tr.tr("Bluetooth device needs charging"), `${device.name || device.address}: ${Math.round(device.battery*100)}%`, "battery_alert");
        }
    }
    Timer { interval:1000; running:root.running || root.awake; repeat:true; onTriggered:root.refreshClock() }
    Connections {target:DesktopJobs;function onChanged():void {root.refreshClock();}}
    Instantiator {
        model: Bluetooth.defaultAdapter?.devices.values ?? []
        delegate: QtObject {
            required property var modelData
            property Connections observer: Connections {
                target:modelData
                function onBatteryChanged():void {root.checkBattery(modelData);}
                function onBatteryAvailableChanged():void {root.checkBattery(modelData);}
                function onConnectedChanged():void {root.checkBattery(modelData);}
            }
            Component.onCompleted:root.checkBattery(modelData)
        }
    }
    CustomShortcut {name:"findCursor";description:"Find the pointer";onPressed:CursorLocator.show()}
    CustomShortcut {name:"clipboardPlain";description:"Remove clipboard formatting";onPressed:root.plainText()}
    IpcHandler {
        target:"comfort"
        function focus():void {root.beginFocus();}
        function stopFocus():void {DesktopJobs.request("comfort.focus-stop",{});}
        function keepAwake(minutes:int):void {DesktopJobs.request("comfort.awake",{minutes});}
        function clipboardPlain():void {root.plainText();}
        function findCursor():void {CursorLocator.show();}
        function settings():void {WindowFactory.openPage("comfort");}
    }
}
