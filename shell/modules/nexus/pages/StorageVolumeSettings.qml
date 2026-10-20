pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.modules.nexus.common

ColumnLayout {
    id: root
    required property var volume
    required property var backend
    property var draft: ({})
    property bool dirty: false
    property string draftPath
    readonly property var health: volume.smart ?? ({})
    readonly property var job: volume.maintenance ?? ({})
    spacing: Tokens.spacing.extraSmall / 2
    function resetDraft(): void {
        const options = (volume.mountOptions ?? "").split(",");
        draft = { path: volume.path, directory: volume.mountDirectory, automatic: !!volume.automatic,
            readOnly: options.includes("ro"), noexec: options.includes("noexec"), nosuid: options.includes("nosuid"),
            nodev: options.includes("nodev"), nofail: !volume.configured || options.includes("nofail"), noatime: options.includes("noatime") };
        draftPath = volume.path;
        dirty = false;
    }
    function edit(key: string, value: var): void { draft = Object.assign({}, draft, {[key]: value}); dirty = true; }
    function action(operation: string): void { backend.apply(operation, {path: volume.path}); }
    function testStatus(): string {
        switch (health.test) {
        case "success": return Tr.tr("No self-test errors reported");
        case "interrupted": case "ctrl_reset": case "ns_removed": return Tr.tr("Interrupted");
        case "fatal": case "fatal_error": case "error_unknown": case "error_electrical": case "error_servo": case "error_read": case "error_handling": case "unknown_seg_fail": case "known_seg_fail": return Tr.tr("Self-test failed");
        case "inprogress": case "in_progress": return Tr.tr("In progress") + (health.remaining >= 0 ? " · " + (100 - health.remaining) + "%" : "");
        case "aborted": case "aborted_host": case "aborted_by_host": case "aborted_format": case "aborted_unknown": case "aborted_sanitize": return Tr.tr("Stopped");
        case "never": case "never_tested": return Tr.tr("Not tested yet");
        default: return health.test || Tr.tr("Not available");
        }
    }
    Component.onCompleted: resetDraft()
    onVolumeChanged: { if (!dirty || draftPath !== volume.path) resetDraft(); }
    Connections { target: root.backend; function onApplied(operation: string): void { if (operation === "configure") root.resetDraft(); } }
    SectionHeader { first: true; text: Tr.tr("Drive information") }
    InfoRow { first: true; label: Tr.tr("Model"); value: root.volume.model }
    InfoRow { label: Tr.tr("Serial number"); value: root.volume.serial || Tr.tr("Not available") }
    InfoRow { last: true; label: "UUID"; value: root.volume.uuid }

    SectionHeader { text: Tr.tr("Mount settings") }
    InfoRow {
        first: true; last: true; visible: !root.volume.mountEditable
        label: Tr.tr("System mount configuration is protected")
        value: Tr.tr("System volumes and volumes with multiple mount entries are managed outside this page")
    }
    ColumnLayout {
        visible: root.volume.mountEditable
        enabled: !root.backend.busy
        Layout.fillWidth: true
        spacing: Tokens.spacing.extraSmall / 2
        ToggleRow { first: true; text: Tr.tr("Mount at startup"); subtext: Tr.tr("Connect this volume automatically when the system starts"); checked: !!root.draft.automatic; disabled: root.backend.busy; onToggled: root.edit("automatic", checked) }
        TextFieldRow { label: Tr.tr("Mount point"); subtext: Tr.tr("A directory inside /mnt or /media"); value: root.draft.directory ?? ""; maximumLength: 240; onValueEdited: value => root.edit("directory", value) }
        ToggleRow { text: Tr.tr("Read-only mount"); checked: !!root.draft.readOnly; onToggled: root.edit("readOnly", checked) }
        ToggleRow { text: Tr.tr("Block program execution"); subtext: "noexec"; checked: !!root.draft.noexec; onToggled: root.edit("noexec", checked) }
        ToggleRow { text: Tr.tr("Ignore privileged executable bits"); subtext: "nosuid"; checked: !!root.draft.nosuid; onToggled: root.edit("nosuid", checked) }
        ToggleRow { text: Tr.tr("Ignore device files"); subtext: "nodev"; checked: !!root.draft.nodev; onToggled: root.edit("nodev", checked) }
        ToggleRow { text: Tr.tr("Continue boot if the drive is missing"); subtext: "nofail"; checked: !!root.draft.nofail; onToggled: root.edit("nofail", checked) }
        ToggleRow { text: Tr.tr("Do not update file access times"); subtext: "noatime"; checked: !!root.draft.noatime; onToggled: root.edit("noatime", checked) }
        RowButton { last: true; text: Tr.tr("Save mount settings"); subtext: Tr.tr("Applied at the next mount; the current connection is preserved"); icon: "save"; disabled: root.backend.busy || !root.dirty; onClicked: root.backend.apply("configure", root.draft) }
    }

    SectionHeader { text: Tr.tr("S.M.A.R.T. health") }
    InfoRow { first: true; last: true; visible: !root.health.supported; label: Tr.tr("Not available"); value: Tr.tr("This device does not expose S.M.A.R.T. through UDisks") }
    ColumnLayout {
        visible: !!root.health.supported
        Layout.fillWidth: true
        spacing: Tokens.spacing.extraSmall / 2
        InfoRow { first: true; label: Tr.tr("Overall health"); value: !root.health.enabled ? Tr.tr("Disabled") : !root.health.updated ? Tr.tr("No health data yet") : root.health.failing ? Tr.tr("Drive reports a problem") : Tr.tr("No problems reported") }
        InfoRow { visible: root.health.temperature !== undefined; label: Tr.tr("Temperature"); value: (root.health.temperature ?? 0).toFixed(0) + " °C" }
        InfoRow { visible: root.health.hours !== undefined; label: Tr.tr("Power-on time"); value: Math.floor(root.health.hours ?? 0) + " " + Tr.tr("hours") }
        InfoRow { visible: root.health.badSectors !== undefined && root.health.badSectors >= 0; label: Tr.tr("Bad sectors"); value: String(root.health.badSectors ?? 0) }
        InfoRow { visible: root.health.failingAttributes !== undefined && root.health.failingAttributes >= 0; label: Tr.tr("Failing attributes"); value: String(root.health.failingAttributes ?? 0) }
        InfoRow { visible: root.health.percent_used !== undefined; label: Tr.tr("Estimated endurance used"); value: (root.health.percent_used ?? 0) + "%" }
        InfoRow { visible: root.health.media_errors !== undefined; label: Tr.tr("Media errors"); value: String(root.health.media_errors ?? 0) }
        InfoRow { visible: root.health.total_data_written !== undefined; label: Tr.tr("Data written"); value: ((root.health.total_data_written ?? 0) / 1e12).toFixed(2) + " TB" }
        InfoRow { visible: root.health.updated > 0; label: Tr.tr("Last updated"); value: new Date((root.health.updated ?? 0) * 1000).toLocaleString(Qt.locale(), Locale.ShortFormat) }
        InfoRow { label: Tr.tr("Self-test"); value: root.testStatus() }
        RowButton { text: Tr.tr("Refresh health data"); subtext: Tr.tr("May wake a sleeping drive"); icon: "refresh"; disabled: root.backend.busy || !root.health.enabled; onClicked: root.action("smart-refresh") }
        RowButton { text: Tr.tr("Run short self-test"); icon: "diagnosis"; disabled: root.backend.busy || !root.health.enabled || root.health.test === "inprogress" || root.health.test === "in_progress"; onClicked: root.action("smart-short") }
        RowButton { text: Tr.tr("Run extended self-test"); subtext: Tr.tr("May take several hours; files remain accessible"); icon: "fact_check"; disabled: root.backend.busy || !root.health.enabled || root.health.test === "inprogress" || root.health.test === "in_progress"; onClicked: root.action("smart-extended") }
        RowButton { last: true; text: Tr.tr("Stop self-test"); icon: "stop"; disabled: root.backend.busy || !(root.health.test === "inprogress" || root.health.test === "in_progress"); onClicked: root.action("smart-abort") }
    }

    SectionHeader { text: Tr.tr("Filesystem maintenance") }
    InfoRow { first: true; label: Tr.tr("Maintenance task"); value: root.job.active ? Tr.tr("In progress") : root.job.result === "success" ? Tr.tr("Completed successfully") : root.job.result ? Tr.tr("Task failed; see the system journal") : Tr.tr("Not running") }
    RowButton { visible: !!root.volume.canTrim; text: Tr.tr("Optimize SSD (TRIM)"); subtext: Tr.tr("Return unused filesystem blocks to the SSD"); icon: "cleaning_services"; disabled: root.backend.busy || root.job.active || root.volume.readOnly; onClicked: root.action("trim") }
    RowButton { visible: !!root.volume.canDefragment; text: Tr.tr("Defragment ext4 volume"); subtext: Tr.tr("Runs in the background with low priority; files remain accessible"); icon: "grid_view"; disabled: root.backend.busy || root.job.active || root.volume.readOnly; onClicked: root.action("defragment") }
    InfoRow { visible: !root.volume.canTrim && !root.volume.canDefragment; label: Tr.tr("Available maintenance"); value: !root.volume.mountPoint ? Tr.tr("Mount the volume to see available maintenance actions") : Tr.tr("No supported optimization for this filesystem and drive type") }
    RowButton { last: true; visible: !!root.job.active; text: Tr.tr("Stop maintenance"); icon: "stop"; disabled: root.backend.busy; onClicked: root.action("stop-maintenance") }
}
