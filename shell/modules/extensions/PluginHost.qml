pragma ComponentBehavior: Bound
import QtQuick
import QtQml.Models
import Quickshell
import qs.services

Scope {
    Instantiator {
        model: ScriptModel { values: Plugins.enabled.map(p => p.id) }
        delegate: Scope {
            id: context
            required property string modelData
            readonly property var pluginApi: api
            PluginApi {
                id: api
                pluginId: context.modelData
                mainInstance: main.item
                Component.onCompleted: Plugins.registerApi(pluginId, api)
                Component.onDestruction: Plugins.unregisterApi(pluginId)
            }
            IsolatedPluginWorker { pluginId:context.modelData; enabled:Plugins.byId(pluginId)?.isolated??false }
            PluginSlot { id: main; pluginId: context.modelData; slot: "main"; api: context.pluginApi }
        }
    }
}
