import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.modules
import qs.modules.dashboard.performance
import qs.services

ShellRoot {
    id: root
    GSFLoader {}
    property int phase: 0
    // Read the real registered backend property; sensor values below are
    // deterministic presentation inputs, not simulated physical measurements.
    property bool backendAvailability: Cpu.temperatureAvailable
    FloatingWindow {
        id: win
        visible: true
        implicitWidth: 800
        implicitHeight: 500
        color: Colours.palette.m3surface
        Config.screen: screen?.name ?? ""
        Tokens.screen: screen?.name ?? ""
        contentItem.Config.screen: screen?.name ?? ""
        contentItem.Tokens.screen: screen?.name ?? ""
        HeroCard {
            id: card
            anchors.fill: parent
            icon: "memory"
            label: "CPU fixture"
            subLabel: "Sensor unavailable / zero / valid"
            accent: Colours.palette.m3primary
            usage: 0.2
            temperature: 0
            temperatureAvailable: false
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
        interval: 300; running: true; repeat: true
        onTriggered: {
            const label = root.named(card, "sensorTemperature");
            const progress = root.named(card, "sensorTemperatureProgress");
            if (!label || !progress) throw new Error("Missing temperature controls");
            const expected = card.temperatureAvailable ? Units.formatSensorTemp(card.temperature) : "—";
            if (label.text !== expected || progress.indeterminate)
                throw new Error("Wrong unavailable/zero/valid sensor presentation: " + label.text);
            if (root.phase === 0) card.temperatureAvailable = true;
            else if (root.phase === 1) card.temperature = 43;
            else if (root.phase === 2) card.temperatureAvailable = false;
            else {
                console.log("SETTINGS_DESIGN_OK CPU_SENSOR_UI_OK");
                Qt.quit();
            }
            root.phase++;
        }
    }
}
