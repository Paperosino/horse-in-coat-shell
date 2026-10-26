pragma ComponentBehavior: Bound
import QtQuick
import Hyprstack.I18n
import qs.components

SettingsContextMenu {
    id: root
    objectName: "panelContextMenu"
    property string widgetId: ""
    readonly property var routes: ({
        logo:"panel-launcher", workspaces:"panel-workspaces", activeWindow:"panel-active-window",
        tray:"panel-tray", clock:"panel-clock", statusIcons:"panel-status-icons",
        layoutSwitcher:"windows", notifications:"notifications", power:"power", plugins:"plugins",
        network:"network", audio:"audio", microphone:"audio", bluetooth:"bluetooth",
        battery:"power", kbLayout:"keyboard", lockStatus:"keyboard", operations:"operations"
    })
    actions: {
        const result = [];
        if (routes[widgetId]) result.push({label:"Widget settings",icon:"tune",page:routes[widgetId]});
        result.push({label:"Panel height and widgets",icon:"widgets",page:"statusbar-layout"});
        result.push({label:"Panel settings",icon:"view_week",page:"panel-options"});
        return result;
    }
    function show(x: real, above: bool, widget: string): void {
        widgetId = widget;
        openAt(anchor.item, x, above ? 0 : anchor.item.height, above);
    }
}
