import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import Hyprstack.Components
import qs.modules
import qs.modules.dashboard.performance
import qs.services

ShellRoot {
    id: root
    GSFLoader {}
    property int phase: 0
    property int attempts: 0
    Component.onCompleted: GlobalConfig.services.gpuType = GpuType.Generic
    ServiceRef { service: Gpu }
    FloatingWindow {
        visible: true; implicitWidth: 800; implicitHeight: 500
        color: Colours.palette.m3surface
        Config.screen: screen?.name ?? ""
        Tokens.screen: screen?.name ?? ""
        contentItem.Config.screen: screen?.name ?? ""
        contentItem.Tokens.screen: screen?.name ?? ""
        HeroCard {
            id: card
            anchors.fill: parent
            icon: "desktop_windows"; label: "GPU fixture"; subLabel: "Synthetic helper samples"
            accent: Colours.palette.m3secondary
            usage: Gpu.percentage
            temperature: Gpu.temperature
            temperatureAvailable: Gpu.temperatureAvailable
        }
    }
    function named(item, name) {
        if (item.objectName === name) return item;
        for (const child of item.children ?? []) {
            const match = named(child, name);
            if (match) return match;
        }
        return null;
    }
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            if (++root.attempts > 150) throw new Error("GPU sampler did not deliver the expected sequence");
            const sample = Math.round(Gpu.percentage * 100) - 25;
            if (sample < root.phase) return;
            if (sample !== root.phase) throw new Error("Skipped GPU sample: " + sample);
            const available = root.phase !== 2;
            const temperature = [43, 0, 0, 37][root.phase];
            const label = root.named(card, "sensorTemperature");
            const progress = root.named(card, "sensorTemperatureProgress");
            if (Gpu.temperatureAvailable !== available || Gpu.temperature !== temperature
                || label.text !== (available ? Units.formatSensorTemp(temperature) : "—")
                || progress.indeterminate)
                throw new Error("GPU sensor availability or presentation is stale at phase " + root.phase);
            if (++root.phase === 4) {
                console.log("SETTINGS_DESIGN_OK GPU_SENSOR_UI_OK");
                Qt.quit();
            }
        }
    }
}
