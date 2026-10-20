pragma Singleton

import QtQuick
import Hyprstack.I18n

QtObject {
    id: root

    function route(id: string): var {
        return ({printers: {id:"devices",subPage:1}, storage: {id:"devices",subPage:2}, datetime: {id:"region",subPage:1}, canvas: {id:"windows",subPage:1}, themes: {id: "appearance", subPage: 4}, "live-wallpapers": {id: "appearance", subPage: 5},
            "system-controls": {id: "windows"}, "session-services": {id: "services", subPage: 2},
            autostart: {id: "apps", subPage: 3}, mouse: {id: "keyboard", subPage: 2},
            touchpad: {id: "keyboard", subPage: 3}, cursor: {id: "keyboard", subPage: 4},
            gestures: {id: "keyboard", subPage: 5},
            "default-apps": {id:"apps",subPage:6}, "statusbar-layout": {id:"panels",subPage:12}, icons: {id:"appearance",subPage:6}, "cursor-theme": {id:"appearance",subPage:7},
            "shell-style": {id:"appearance",subPage:8}, dock: {id:"panels",subPage:11},
            shortcuts: {id:"keyboard",subPage:6}, plugins: {id:"apps",subPage:4}, assistant: {id:"apps",subPage:5}})[id] ?? {id: id};
    }
    function indexOf(id: string): int { return pages.findIndex(p => p.id === route(id).id); }


    readonly property var navigationPages: ([
        ...navigationGroup("personalisation", ["appearance", "panels", "windows"]),
        ...navigationGroup("devices", ["display", "keyboard", "audio", "bluetooth", "devices"]),
        ...navigationGroup("connections", ["network"]),
        ...navigationGroup("applications", ["apps"]),
        ...navigationGroup("system", ["power", "region", "services", "about"])
    ])
    function navigationGroup(category: string, ids: list<string>): var {
        return ids.map(id => {
            const index = pages.findIndex(p => p.id === id);
            return Object.assign({}, pages[index], {pageIndex:index, category:category});
        });
    }
    function categoryLabel(category: string): string {
        return ({personalisation:Tr.tr("Personalisation"),devices:Tr.tr("Devices"),
            connections:Tr.tr("Connections"),applications:Tr.tr("Applications"),system:Tr.tr("System")})[category] ?? "";
    }

    readonly property list<var> pages: [
        // Appearance
        {
            id: "appearance",
            label: Tr.tr("Customisation"),
            icon: "palette",
            description: Tr.tr("Background, colours, icons and cursors"),
            category: "appearance"
        },

        // Connectivity
        {
            id: "display",
            label: Tr.tr("Display"),
            icon: "monitor",
            description: Tr.tr("Resolution, refresh rate, arrangement"),
            category: "connectivity"
        },
        {
            id: "windows",
            label: Tr.tr("Windows & workspaces"),
            icon: "tune",
            description: Tr.tr("Focus, resizing and workspace navigation"),
            category: "connectivity"
        },
        {
            id: "network",
            label: Tr.tr("Network"),
            icon: "wifi",
            description: Tr.tr("Wi-Fi, ethernet, VPN"),
            category: "connectivity"
        },
        {
            id: "bluetooth",
            label: Tr.tr("Connected devices"),
            icon: "devices_other",
            description: Tr.tr("Bluetooth, pairing"),
            category: "connectivity",
            noFill: true
        },
        {
            id: "audio",
            label: Tr.tr("Audio"),
            icon: "volume_up",
            description: Tr.tr("App volumes, sound devices"),
            category: "connectivity"
        },

        {
            id: "keyboard",
            label: Tr.tr("Keyboard & mouse"),
            icon: "keyboard",
            description: Tr.tr("Keyboard, mouse, touchpad and gestures"),
            category: "connectivity"
        },

        // Shell
        {
            id: "panels",
            label: Tr.tr("Panels"),
            icon: "dock_to_bottom",
            description: Tr.tr("Dashboard, taskbar, launcher, sidebar"),
            category: "shell"
        },
        {
            id: "dock",
            label: Tr.tr("Dock"),
            icon: "web_asset",
            description: Tr.tr("Pinned apps, app list"),
            category: "shell"
        },
        {
            id: "apps",
            label: Tr.tr("Apps"),
            icon: "apps",
            description: Tr.tr("Default apps, favourites, hidden apps"),
            category: "shell"
        },
        {
            id: "services",
            label: Tr.tr("Services"),
            icon: "build",
            description: Tr.tr("Poll intervals, lyrics backend"),
            category: "shell"
        },
        {
            id: "power",
            label: Tr.tr("Power & lock"),
            icon: "power_settings_new",
            description: Tr.tr("Screen timeout, locking, sleep"),
            category: "shell"
        },
        {
            id: "region",
            label: Tr.tr("Language & region"),
            icon: "globe",
            description: Tr.tr("UI language, weather location, display units"),
            category: "shell"
        },

        {
            id: "shortcuts",
            label: Tr.tr("Keyboard shortcuts"),
            icon: "keyboard",
            description: Tr.tr("Current key bindings and mouse gestures"),
            category: "shell"
        },

        {
            id: "plugins",
            label: Tr.tr("Plugins"),
            icon: "extension",
            description: Tr.tr("Extensions, compatibility and settings"),
            category: "shell"
        },
        {
            id: "assistant",
            label: Tr.tr("AI assistant"),
            icon: "smart_toy",
            description: Tr.tr("Local models and configurable chat servers"),
            category: "shell"
        },

        // About
        {
            id: "about",
            label: Tr.tr("About"),
            icon: "info",
            description: Tr.tr("System information, credits"),
            category: "about"
        },
        {
            id: "devices",
            label: Tr.tr("Printers & storage"),
            icon: "print",
            description: Tr.tr("Print queues, disks and removable volumes"),
            category: "connectivity"
        },
    ]
}
