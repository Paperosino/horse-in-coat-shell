pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common

PageBase {
    id: root
    title: Tr.tr("Performance & games")
    pageIcon: "speed"
    readonly property var prefs: RuntimePerformance.settings
    readonly property var live: RuntimePerformance.status
    function save(key: string, value: var): void { RuntimePerformance.set(key,value); }
    function list(text: string): var { return text.split(",").map(s=>s.trim()).filter(s=>s.length>0); }
    function reading(key: string, unit: string): string {
        const value=Number(live[key] ?? -1);return value>=0 ? value.toFixed(0)+unit : Tr.tr("Unavailable");
    }
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large
        FeatureError { error: root.live.error ?? "" }
        SettingsCard {
            title: Tr.tr("Ready when you play")
            description: Tr.tr("Recognise selected fullscreen games, pause background work and restore your desktop afterwards. Ordinary desktop quality stays unchanged.")
            icon: "sports_esports"
            badge: GameMode.enabled ? Tr.tr("Game mode") : Tr.tr("Desktop")
            ToggleRow { objectName:"performanceAutoGame"; text:Tr.tr("Automatic game mode"); checked:root.prefs.autoGameMode; onToggled:root.save("autoGameMode",checked) }
            ToggleRow { text:Tr.tr("Require fullscreen");subtext:Tr.tr("Maximised windows and game launchers do not count as fullscreen games");checked:root.prefs.fullscreenOnly;onToggled:root.save("fullscreenOnly",checked) }
            SettingsCard {
                title:Tr.tr("Application matching");icon:"rule";collapsible:true;expanded:false
            TextFieldRow { label:Tr.tr("Game application IDs");subtext:Tr.tr("Comma-separated IDs; * matches any characters. Wayland alone never identifies a game.");value:root.prefs.gameRules.join(", ");onEditingFinished:value=>root.save("gameRules",root.list(value)) }
            TextFieldRow { label:Tr.tr("Excluded application IDs");value:root.prefs.excludeRules.join(", ");onEditingFinished:value=>root.save("excludeRules",root.list(value)) }
            }
            RowButton { text:Tr.tr("Add the last application");subtext:root.live.lastApplication??Tr.tr("No focused application");icon:"add";disabled:!root.live.lastApplication;onClicked:{const rules=root.prefs.gameRules.slice();rules.push(root.live.lastApplication);root.save("gameRules",rules);} }
            ToggleRow { text:Tr.tr("Game mode now");checked:GameMode.enabled;onToggled:GameMode.enabled=checked }
            RowButton { visible:GameMode.manualOverrideActive;text:Tr.tr("Follow automatic game mode");icon:"autorenew";onClicked:GameMode.resumeAutomatic() }
        }
        SettingsCard {
            title: Tr.tr("While a game is active")
            icon: "stadia_controller"
            description: Tr.tr("Each option is temporary. Input sensitivity, acceleration, USB polling and CPU quotas are never changed.")
            ToggleRow { text:Tr.tr("Suspend compositor effects");subtext:Tr.tr("Animations, blur, shadows, rounding and gaps");checked:root.prefs.disableEffects;onToggled:root.save("disableEffects",checked) }
            ToggleRow { text:Tr.tr("Pause live wallpapers");checked:root.prefs.pauseWallpapers;onToggled:root.save("pauseWallpapers",checked) }
            ToggleRow { text:Tr.tr("Suspend dock motion");checked:root.prefs.reduceDockMotion;onToggled:root.save("reduceDockMotion",checked) }
            GenericSettingRow { spec:({type:"choice",label:"Direct scanout",choices:[{value:0,label:"Keep compositor setting"},{value:1,label:"Automatic for game content"},{value:2,label:"Allow for fullscreen games"}]});value:root.prefs.directScanout;onEdited:value=>root.save("directScanout",value) }
            ToggleRow { text:Tr.tr("Allow tearing during games");subtext:Tr.tr("Requires a matching immediate window rule and compatible hardware; this does not guarantee direct scanout");checked:root.prefs.allowTearing;onToggled:root.save("allowTearing",checked) }
            RowButton { text:Tr.tr("Adaptive sync per display");subtext:Tr.tr("VRR is opt-in. Use display confirmation to check for flicker and keep a safe way back.");icon:"monitor";onClicked:root.nState.openPage("display") }
        }
        SettingsCard {
            title: Tr.tr("Power and process priority")
            description: Tr.tr("Use system services that own and restore their policies. Optional GameMode provides game process and I/O priority; power-profiles-daemon provides a temporary performance hold.")
            icon: "bolt"
            collapsible: true; expanded: false
            ToggleRow { text:Tr.tr("Request Feral GameMode for the game");subtext:Tr.tr("Requires the optional gamemode package. Choose one power policy provider; enabling one disables the other.");checked:root.prefs.feralGameMode;onToggled:root.save("feralGameMode",checked) }
            ToggleRow { text:Tr.tr("Hold the performance power profile");subtext:Tr.tr("Released when the game ends, focus leaves it or the shell exits. Your manual profile selection takes precedence.");checked:root.prefs.performanceProfile;onToggled:root.save("performanceProfile",checked) }
            ToggleRow { text:Tr.tr("Allow boosts and prefetch on battery");checked:root.prefs.allowOnBattery;onToggled:root.save("allowOnBattery",checked) }
            FeatureError {error:[root.live.leaseError,root.live.gamemodeError,root.live.powerError].filter(Boolean).join("\n")}
        }
        SettingsCard {
            title: Tr.tr("Adaptive effects")
            description: Tr.tr("Optional GPU-load policy with hysteresis. It changes effective shell effects without overwriting your appearance or accessibility preferences. Missing GPU readings never trigger a downgrade.")
            icon: "auto_awesome"
            collapsible: true; expanded: false
            ToggleRow {text:Tr.tr("Adapt shell effects to GPU load");checked:root.prefs.adaptiveQuality;onToggled:root.save("adaptiveQuality",checked)}
            GenericSettingRow {spec:({type:"choice",label:"Minimum effect quality",choices:[{value:2,label:"Full quality"},{value:1,label:"Smaller shadows"},{value:0,label:"No blur or shadows"}]});value:root.prefs.qualityFloor;onEdited:value=>root.save("qualityFloor",value)}
            StepperRow {label:Tr.tr("High GPU load (%)");from:root.prefs.gpuLow+10;to:95;value:root.prefs.gpuHigh;onMoved:value=>root.save("gpuHigh",value)}
            StepperRow {label:Tr.tr("Recovery GPU load (%)");from:10;to:root.prefs.gpuHigh-10;value:root.prefs.gpuLow;onMoved:value=>root.save("gpuLow",value)}
            StepperRow {label:Tr.tr("Minimum time between quality changes (s)");from:5;to:120;value:root.prefs.qualityDwell/1000;onMoved:value=>root.save("qualityDwell",value*1000)}
            StepperRow {label:Tr.tr("Sampling interval (s)");from:2;to:30;value:root.prefs.sampleInterval/1000;onMoved:value=>root.save("sampleInterval",value*1000)}
            InfoRow {label:Tr.tr("GPU load");value:root.reading("gpu"," %")}
            InfoRow {label:Tr.tr("Effective quality");value:RuntimePerformance.quality===2?Tr.tr("Full quality"):RuntimePerformance.quality===1?Tr.tr("Smaller shadows"):Tr.tr("Background effects paused")}
        }
        SettingsCard {
            title: Tr.tr("Temperature guard")
            description: Tr.tr("Reduce the shell's background work when recognised CPU/GPU sensors report heat. This complements kernel thermal protection; it cannot guarantee that games will not throttle.")
            icon: "device_thermostat"
            collapsible: true; expanded: false
            ToggleRow {text:Tr.tr("Reduce background effects when hot");checked:root.prefs.thermalGuard;onToggled:root.save("thermalGuard",checked)}
            StepperRow {label:Tr.tr("Activate at (°C)");from:Math.max(50,root.prefs.temperatureLow+5);to:110;value:root.prefs.temperatureHigh;onMoved:value=>root.save("temperatureHigh",value)}
            StepperRow {label:Tr.tr("Recover below (°C)");from:30;to:Math.min(100,root.prefs.temperatureHigh-5);value:root.prefs.temperatureLow;onMoved:value=>root.save("temperatureLow",value)}
            InfoRow {label:Tr.tr("Highest recognised temperature");value:root.reading("temperature"," °C")}
            InfoRow {label:Tr.tr("Temperature guard");value:RuntimePerformance.thermalLimited?Tr.tr("Background effects paused"):Tr.tr("Normal")}
        }
        SettingsCard {
            title: Tr.tr("Conservative application prefetch")
            description: Tr.tr("Learn application transitions locally and warm only a bounded executable prefix from an explicit allowlist. No hidden application instances are launched. Benefit depends on storage and the page cache.")
            icon: "rocket_launch"
            collapsible: true; expanded: false
            ToggleRow {objectName:"performancePrefetch";text:Tr.tr("Learn transitions and enable prefetch");checked:root.prefs.prefetch;onToggled:root.save("prefetch",checked)}
            TextFieldRow {label:Tr.tr("Allowed desktop application IDs");subtext:Tr.tr("Exact IDs, separated by commas. An empty list disables all prefetch.");value:root.prefs.prefetchAllowlist.join(", ");onEditingFinished:value=>root.save("prefetchAllowlist",root.list(value))}
            StepperRow {label:Tr.tr("Executable prefix limit (MiB)");from:1;to:32;value:root.prefs.prefetchMiB;onMoved:value=>root.save("prefetchMiB",value)}
            StepperRow {label:Tr.tr("Cooldown (s)");from:30;to:3600;stepSize:30;value:root.prefs.prefetchCooldown;onMoved:value=>root.save("prefetchCooldown",value)}
            StepperRow {label:Tr.tr("Required matching transitions");from:3;to:30;value:root.prefs.prefetchTransitions;onMoved:value=>root.save("prefetchTransitions",value)}
            StepperRow {label:Tr.tr("Minimum confidence (%)");from:10;to:95;value:root.prefs.prefetchConfidence;onMoved:value=>root.save("prefetchConfidence",value)}
            StepperRow {label:Tr.tr("Maximum prediction age (s)");from:30;to:600;value:root.prefs.prefetchMaxAge;onMoved:value=>root.save("prefetchMaxAge",value)}
            StepperRow {label:Tr.tr("Maximum CPU use (%)");from:10;to:95;value:root.prefs.prefetchCpu;onMoved:value=>root.save("prefetchCpu",value)}
            StepperRow {label:Tr.tr("Maximum memory use (%)");from:10;to:95;value:root.prefs.prefetchMemory;onMoved:value=>root.save("prefetchMemory",value)}
            InfoRow {label:Tr.tr("Last prediction");value:root.live.prediction??"—"}
            InfoRow {label:Tr.tr("Executable bytes advised to the kernel");value:String(root.live.prefetchedBytes??0)}
            RowButton {text:Tr.tr("Forget learned application transitions");icon:"delete_history";onClicked:RuntimePerformance.forgetHistory()}
        }
        SettingsCard {
            title: Tr.tr("Reliability and diagnostics")
            description: Tr.tr("The broker has a main-loop watchdog. Crashes and timeouts produce bounded, private local reports in /var/lib/hics/crashes; reports are never uploaded. The kernel manages memory compaction and applications own their network socket options.")
            icon: "health_and_safety"
            InfoRow {label:Tr.tr("Background monitoring");value:root.live.monitoring?Tr.tr("Active"):Tr.tr("Sleeping")}
            InfoRow {label:Tr.tr("CPU load");value:root.reading("cpu"," %")}
            InfoRow {label:Tr.tr("Memory use");value:root.reading("memory"," %")}
        }
    }
}
