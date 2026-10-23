pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
ColumnLayout {
    id: root
    property bool watching: false
    property var draft: ({})
    property bool dirty: false
    readonly property string mode: draft.mode ?? "system"
    readonly property var live: backend.state
    readonly property bool usesZram: ["zram", "both", "smart"].includes(mode)
    readonly property bool usesZswap: ["zswap", "both", "smart"].includes(mode)
    Layout.fillWidth: true
    spacing: Tokens.spacing.medium
    function edit(key: string, value: var): void {
        const next = Object.assign({}, draft); next[key] = value; draft = next; dirty = true;
    }
    function amount(bytes: real): string { return (bytes / 1073741824).toFixed(1) + " GiB"; }
    NativeSystemBackend { id: backend; section: "memory"; watching: root.watching }
    Timer {
        interval: 2000
        repeat: true
        running: root.watching && !root.dirty && JSON.stringify(root.live.config) !== JSON.stringify(root.live.controller?.config)
        onTriggered: { if (!backend.busy) backend.reload(); }
    }
    Connections {
        target: backend
        function onStateChanged(): void { if (!root.dirty && backend.state.config) root.draft = Object.assign({}, backend.state.config); }
        function onApplied(): void { root.dirty = false; if (backend.state.config) root.draft = Object.assign({}, backend.state.config); }
    }
    SettingsGuide {
        icon: "memory"
        title: Tr.tr("Memory and compression")
        description: Tr.tr("Choose when compressed RAM and disk-backed memory become available. Settings apply system-wide and persist after logout.")
        badges: [Tr.tr("RAM") + " · " + root.amount(root.live.total ?? 0), Tr.tr("Available") + " · " + root.amount(root.live.available ?? 0), Math.round(root.live.ramPercent ?? 0) + "%"]
    }
    FeatureError { error: backend.error || root.live.controller?.error || "" }
    SettingsCard {
        title: Tr.tr("Memory strategy")
        description: Tr.tr("The system strategy keeps your existing swap configuration. Select another strategy to let hics manage memory.")
        icon: "tune"
        Flow {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small
            Repeater {
                model: [{value:"system",label:"System settings"},{value:"off",label:"No swap"},{value:"zram",label:"ZRAM only"},{value:"zswap",label:"ZSwap only"},{value:"both",label:"ZRAM + ZSwap"},{value:"smart",label:"Smart mode"}]
                delegate: IconTextButton {
                    required property var modelData
                    isToggle: true
                    checked: root.mode === modelData.value
                    text: Tr.tr(modelData.label)
                    icon: root.mode === modelData.value ? "check_circle" : "radio_button_unchecked"
                    onClicked: root.edit("mode", modelData.value)
                }
            }
        }
        StyledText {
            Layout.fillWidth: true
            text: Tr.tr("Current stage") + ": " + Tr.tr(({system:"System settings",ram:"RAM only",zram:"ZRAM",zswap:"ZSwap + disk reserve"})[root.live.controller?.phase ?? "system"])
            font: Tokens.font.body.medium
            wrapMode: Text.WordWrap
        }
        Repeater {
            model: root.live.swaps ?? []
            delegate: StyledText {
                required property var modelData
                Layout.fillWidth: true
                text: modelData.path + " · " + root.amount(modelData.used) + " / " + root.amount(modelData.size)
                font: Tokens.font.body.small
                color: Colours.palette.m3onSurfaceVariant
                wrapMode: Text.WrapAnywhere
            }
        }
    }
    SettingsCard {
        visible: root.mode === "smart"
        title: Tr.tr("Adaptive stages")
        description: Tr.tr("RAM only → ZRAM → ZSwap with disk reserve. RAM pressure uses available memory, excluding reclaimable cache. The second threshold measures logical ZRAM usage.")
        icon: "auto_awesome"
        GenericSettingRow { spec: ({type:"int",label:"Enable ZRAM at RAM usage (%)",min:20,max:95,value:root.draft.ramThreshold ?? 75}); onEdited: value => root.edit("ramThreshold",value) }
        GenericSettingRow { spec: ({type:"int",label:"Enable ZSwap at ZRAM usage (%)",min:20,max:95,value:root.draft.zramThreshold ?? 80}); onEdited: value => root.edit("zramThreshold",value) }
        GenericSettingRow { spec: ({type:"bool",label:"Return to RAM only when pressure falls",value:root.draft.releaseIdle ?? true}); onEdited: value => root.edit("releaseIdle",value) }
        GenericSettingRow { visible: root.draft.releaseIdle ?? true; spec: ({type:"int",label:"Recovery margin (percentage points)",min:3,max:30,value:root.draft.hysteresis ?? 10}); onEdited: value => root.edit("hysteresis",value) }
        GenericSettingRow { visible: root.draft.releaseIdle ?? true; spec: ({type:"int",label:"Low-pressure delay (seconds)",min:15,max:3600,step:15,value:root.draft.releaseSeconds ?? 120}); onEdited: value => root.edit("releaseSeconds",value) }
    }
    SettingsCard {
        visible: root.usesZram
        title: "ZRAM"
        description: Tr.tr("A compressed swap device in RAM. The logical capacity is a limit; physical memory is allocated as pages arrive.")
        icon: "memory"
        GenericSettingRow { spec: ({type:"int",label:"ZRAM logical capacity (MiB)",min:64,max:Math.max(64,Math.floor((root.live.total ?? 2147483648)/524288)),step:256,value:root.draft.zramMiB ?? 4096}); onEdited: value => root.edit("zramMiB",value) }
    }
    SettingsCard {
        visible: root.usesZswap
        title: Tr.tr("ZSwap and disk reserve")
        description: Tr.tr("ZSwap grows its compressed cache automatically up to the RAM limit. Backing swap files are added in chunks; active files are never resized. Reaching a limit stops growth.")
        icon: "storage"
        GenericSettingRow { spec: ({type:"int",label:"ZSwap RAM limit (%)",min:1,max:50,value:root.draft.poolPercent ?? 20}); onEdited: value => root.edit("poolPercent",value) }
        GenericSettingRow { spec: ({type:"int",label:"Disk growth step (MiB)",min:64,max:16384,step:256,value:root.draft.chunkMiB ?? 1024}); onEdited: value => root.edit("chunkMiB",value) }
        GenericSettingRow { spec: ({type:"int",label:"Maximum disk swap (MiB)",min:64,max:1048576,step:1024,value:root.draft.diskMaxMiB ?? 8192}); onEdited: value => root.edit("diskMaxMiB",value) }
        GenericSettingRow { spec: ({type:"int",label:"Grow disk reserve at usage (%)",min:20,max:95,value:root.draft.diskThreshold ?? 75}); onEdited: value => root.edit("diskThreshold",value) }
        GenericSettingRow { spec: ({type:"int",label:"Keep free disk space (MiB)",min:512,max:1048576,step:1024,value:root.draft.reserveMiB ?? 4096}); onEdited: value => root.edit("reserveMiB",value) }
        StyledText { Layout.fillWidth:true; visible:root.mode === "both" || root.mode === "smart"; text:Tr.tr("ZSwap is a global kernel cache and can also cache pages sent to ZRAM. Combining them can add compression overhead."); wrapMode:Text.WordWrap; color:Colours.palette.m3onSurfaceVariant; font:Tokens.font.body.small }
    }
    SettingsCard {
        visible: root.mode !== "system" && root.mode !== "off"
        title: Tr.tr("Compression")
        icon: "compress"
        GenericSettingRow { spec: ({type:"choice",label:"Compression algorithm",choices:["zstd","lz4","lzo-rle"],value:root.draft.compressor ?? "zstd"}); onEdited: value => root.edit("compressor",value) }
    }
    SettingsCard {
        visible: root.mode !== "system"
        title: Tr.tr("Switching from the system strategy")
        description: Tr.tr("Existing systemd ZRAM0 can be transferred to hics. Other external swap must be disabled first. Turning swap off waits for sufficient free RAM; no forced page eviction is used.")
        icon: "swap_horiz"
        GenericSettingRow { spec: ({type:"bool",label:"Take over systemd ZRAM0",value:root.draft.takeOver ?? false}); onEdited: value => root.edit("takeOver",value) }
    }
    RowLayout {
        Layout.fillWidth: true
        IconTextButton { text:Tr.tr("Apply memory settings"); icon:"check"; disabled:backend.busy || !root.dirty; onClicked:backend.apply("configure",root.draft) }
        IconTextButton { text:Tr.tr("Reset changes"); icon:"undo"; disabled:backend.busy || !root.dirty; onClicked:{root.dirty=false;root.draft=Object.assign({},backend.state.config ?? {});} }
    }
}
