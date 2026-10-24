pragma Singleton
import Quickshell
import qs.services
Singleton {
    function getPluginSettings(id: string): var { return Plugins.byId(id)?.settings ?? {}; }
    function savePluginSettings(id: string, settings: var): void { Plugins.saveSettings(id, settings); }
    function openPluginSettings(id: string): void { Plugins.open(id); }
}
