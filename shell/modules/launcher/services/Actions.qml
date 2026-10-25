pragma Singleton

import Hyprstack
import ".."
import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.services
import qs.utils
import qs.modules.nexus

Searcher {
    id: root

    function transformSearch(search: string): string {
        return search.slice(GlobalConfig.launcher.actionPrefix.length);
    }

    readonly property var integratedActions: GlobalConfig.utilities.comfort.launcherActions ? [
        {name:Tr.tr("Open home folder"),desc:Tr.tr("Use your default file manager"),icon:"home",onClicked:list=>{DesktopJobs.request("integration.open",{target:"home"});list.screenState.launcher=false;}},
        {name:Tr.tr("Open downloads"),desc:Tr.tr("Use your default file manager"),icon:"download",onClicked:list=>{DesktopJobs.request("integration.open",{target:"downloads"});list.screenState.launcher=false;}},
        {name:Tr.tr("Open trash"),desc:Tr.tr("Restore files in your file manager"),icon:"delete",onClicked:list=>{DesktopJobs.request("integration.open",{target:"trash"});list.screenState.launcher=false;}},
        {name:Tr.tr("File manager integration"),desc:Tr.tr("File managers and archive applications"),icon:"folder_open",onClicked:list=>{WindowFactory.openPage("file-integration");list.screenState.launcher=false;}},
        {name:Tr.tr("Focus & breaks"),desc:Tr.tr("Focus sessions and temporary wake locks"),icon:"timer",onClicked:list=>{WindowFactory.openPage("focus");list.screenState.launcher=false;}},
        {name:Tr.tr("Find my pointer now"),desc:Tr.tr("Highlight the pointer without moving it"),icon:"my_location",onClicked:list=>{CursorLocator.show();list.screenState.launcher=false;}},
        {name:Tr.tr("Remove clipboard formatting"),desc:Tr.tr("Prepare the current text for Ctrl+V"),icon:"format_clear",onClicked:list=>{Comfort.plainText();list.screenState.launcher=false;}}
    ] : []
    list: [...variants.instances, ...integratedActions]
    useFuzzy: GlobalConfig.launcher.useFuzzy.actions

    Variants {
        id: variants

        model: {
            const enableDangerous = GlobalConfig.launcher.enableDangerousActions;
            return GlobalConfig.launcher.actions.values.filter(a => a.enabled && (enableDangerous || !a.dangerous));
        }

        Action {}
    }

    component Action: QtObject {
        required property var modelData
        readonly property string name: modelData.name ? Tr.trMarked(modelData.name) : Tr.trCtx("Unnamed", "launcher action with no name")
        readonly property string desc: modelData.description ? Tr.trMarked(modelData.description) : Tr.trCtx("No description", "launcher action with no description")
        readonly property string icon: modelData.icon ?? "help_outline"
        readonly property list<string> command: modelData.command ?? []
        readonly property bool enabled: modelData.enabled ?? true
        readonly property bool dangerous: modelData.dangerous ?? false

        function onClicked(list: AppList): void {
            if (command.length === 0)
                return;

            if (command[0] === "autocomplete" && command.length > 1) {
                list.search.text = `${GlobalConfig.launcher.actionPrefix}${command[1]} `;
            } else if (command[0] === "setMode" && command.length > 1) {
                list.screenState.launcher = false;
                Colours.setMode(command[1]);
            } else {
                list.screenState.launcher = false;
                if (!SessionManager.exec(command))
                    CUtils.execDetached(command);
            }
        }
    }
}
