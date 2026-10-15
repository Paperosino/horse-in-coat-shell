pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import qs.services
import qs.utils

Singleton {
    id: root

    // Tint each application's own texture; never flatten the whole workspace.
    property string mode: "tinted"
    property string activeColour: ""
    property string inactiveColour: ""
    property string activeColourRole: "onPrimary"
    property string inactiveColourRole: "primary"
    readonly property string activeSelection: activeColourRole || activeColour
    readonly property string inactiveSelection: inactiveColourRole || inactiveColour
    readonly property var colourChoices: [
        {role: "onPrimary", label: "On accent"}, ...Tiling.borderColorChoices
    ]
    property int size: 20
    property bool loaded: false

    function validColour(value: string): bool { return !value || /^#[0-9a-fA-F]{6}$/.test(value); }
    function validRole(value: var): bool { return value === "onPrimary" || Tiling.validBorderRole(value); }

    function colour(active: bool): color {
        const role = active ? activeColourRole : inactiveColourRole;
        const legacy = active ? activeColour : inactiveColour;
        return role ? Colours.colourForRole(role, Colours.palette)
            : legacy || Colours.colourForRole(active ? "onPrimary" : "primary", Colours.palette);
    }

    function set(option: string, value: var): void {
        if (!loaded) return;
        if (option === "mode" && ["original", "tinted", "symbols"].includes(value)) mode = value;
        else if ((option === "activeColourRole" || option === "inactiveColourRole") && validRole(value)) {
            root[option] = value;
            root[option.replace("Role", "")] = "";
        } else if ((option === "activeColour" || option === "inactiveColour") && validColour(value)) {
            root[option] = value;
            root[option + "Role"] = value ? "" : (option === "activeColour" ? "onPrimary" : "primary");
        }
        else if (option === "size") size = Math.max(12, Math.min(32, Math.round(value)));
        else return;
        storage.setText(JSON.stringify({mode: mode, activeColour: activeColour, inactiveColour: inactiveColour,
            activeColourRole: activeColourRole, inactiveColourRole: inactiveColourRole, size: size}));
    }

    FileView {
        id: storage
        path: `${Paths.config}/workspace-icons.json`
        printErrors: false
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                const data = JSON.parse(text());
                root.mode = ["original", "tinted", "symbols"].includes(data.mode) ? data.mode : "tinted";
                root.activeColour = root.validColour(data.activeColour ?? "") ? data.activeColour ?? "" : "";
                root.inactiveColour = root.validColour(data.inactiveColour ?? "") ? data.inactiveColour ?? "" : "";
                root.activeColourRole = root.validRole(data.activeColourRole) ? data.activeColourRole
                    : root.activeColour ? "" : "onPrimary";
                root.inactiveColourRole = root.validRole(data.inactiveColourRole) ? data.inactiveColourRole
                    : root.inactiveColour ? "" : "primary";
                root.size = Math.max(12, Math.min(32, Math.round(data.size ?? 20)));
            } catch (error) {
                console.warn(`Unable to load workspace icon appearance: ${error}`);
            }
            root.loaded = true;
        }
        onLoadFailed: root.loaded = true
    }
}
