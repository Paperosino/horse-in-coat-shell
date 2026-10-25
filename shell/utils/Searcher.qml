import QtQuick
import Quickshell

Singleton {
    id:root
    required property list<QtObject> list
    property string key: "name"
    property bool useFuzzy: false
    property var extraOpts: ({})

    // Extra stuff for fuzzy
    property list<string> keys: [key]
    property list<real> weights: [1]

    Loader {
        id: engine
        source: root.list.length ? Qt.resolvedUrl(root.useFuzzy ? "FuzzySearchBackend.qml" : "FzfSearchBackend.qml") : ""
        onLoaded: item.owner = root
    }

    function transformSearch(search: string): string {
        return search;
    }

    function selector(item: var): string {
        // Only for fzf
        return item[key];
    }

    function query(search: string): var {
        search = transformSearch(search.trim().replace(/\s+/g, " "));
        if (!search)
            return [...list];

        return engine.item ? engine.item.query(search) : [];
    }
}
