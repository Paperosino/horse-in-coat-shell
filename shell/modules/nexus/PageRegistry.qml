pragma Singleton

import QtQuick
import Hyprstack.I18n

QtObject {
    id: root

    function route(id: string): var {
        return ({vpn:{id:"network"},canvas: {id:"windows",subPage:1}, themes: {id:"appearance",subPage:4},
            "live-wallpapers": {id:"appearance",subPage:5}, "system-controls": {id:"windows"},
            "session-services": {id:"services",subPage:2}, cursor: {id:"keyboard",subPage:4},
            gestures: {id:"keyboard",subPage:5}, "statusbar-layout": {id:"panels",subPage:12},
            icons: {id:"appearance",subPage:6}, "cursor-theme": {id:"appearance",subPage:7},
            "shell-style": {id:"appearance",subPage:8}, media: {id:"audio",subPage:2}})[id] ?? {id:id};
    }
    function indexOf(id: string): int { return pages.findIndex(p => p.id === route(id).id); }


    readonly property var navigationPages: ([
        ...navigationGroup("personalisation", ["appearance", "panels", "dock", "windows"]),
        ...navigationGroup("devices", ["display", "audio", "printers", "storage"]),
        ...navigationGroup("input", ["keyboard", "mouse", "touchpad", "shortcuts", "clipboard", "accessibility"]),
        ...navigationGroup("connections", ["network", "bluetooth", "sharing"]),
        ...navigationGroup("applications", ["apps", "default-apps", "autostart", "session-recovery", "notifications", "plugins", "assistant"]),
        ...navigationGroup("system", ["power", "region", "datetime", "services", "about"])
    ])
    function navigationGroup(category: string, ids: list<string>): var {
        return ids.map(id => {
            const index = pages.findIndex(p => p.id === id);
            return Object.assign({}, pages[index], {pageIndex:index, category:category});
        });
    }
    function categoryLabel(category: string): string {
        return ({personalisation:Tr.tr("Personalisation"),devices:Tr.tr("Devices"),
            input:Tr.tr("Input & interaction"),connections:Tr.tr("Connections"),applications:Tr.tr("Applications"),system:Tr.tr("System")})[category] ?? "";
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
            label: Tr.tr("Bluetooth"),
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
            label: Tr.tr("Keyboard"),
            icon: "keyboard",
            description: Tr.tr("Layouts, typing, cursor and gestures"),
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
            description: Tr.tr("User services, timers and system monitoring"),
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
        {id: "accessibility", label: Tr.tr("Accessibility"), icon: "accessibility_new", description: Tr.tr("Contrast, motion, scale and keyboard navigation"), category: "shell"},
        {id: "sharing", label: Tr.tr("Screen capture & sharing"), icon: "screen_share", description: Tr.tr("Recording sources and video capture activity"), category: "connectivity"},
        {id:"notifications", label:Tr.tr("Notifications"), icon:"notifications", description:Tr.tr("Application rules, quiet mode and popups"), category:"shell"},
        {id:"mouse", label:Tr.tr("Mouse"), icon:"mouse", description:Tr.tr("Sensitivity, buttons and scrolling"), category:"connectivity"},
        {id:"touchpad", label:Tr.tr("Touchpad"), icon:"touchpad_mouse", description:Tr.tr("Taps, clicks and scrolling"), category:"connectivity"},
        {id:"printers", label:Tr.tr("Printers"), icon:"print", description:Tr.tr("Printer queues, default printer and print jobs"), category:"connectivity"},
        {id:"storage", label:Tr.tr("Storage"), icon:"storage", description:Tr.tr("Disk space, filesystems and removable volumes"), category:"connectivity"},
        {id:"datetime", label:Tr.tr("Date & time"), icon:"schedule", description:Tr.tr("Clock, time zone and automatic time"), category:"shell"},
        {id:"autostart", label:Tr.tr("Autostart"), icon:"rocket_launch", description:Tr.tr("Applications started when signing in"), category:"shell"},
        {id:"default-apps", label:Tr.tr("Default applications"), icon:"open_in_new", description:Tr.tr("Browser, documents, media and file formats"), category:"shell"},
        {id:"vpn", label:Tr.tr("VPN"), icon:"vpn_key", description:Tr.tr("NetworkManager profiles, protocols, DNS and routing"), category:"connectivity"},
        {id:"clipboard",label:Tr.tr("Clipboard history"),icon:"content_paste",description:Tr.tr("History, pins, privacy and retention"),category:"shell"},
        {id:"session-recovery",label:Tr.tr("Session recovery"),icon:"restore",description:Tr.tr("Snapshots, application recovery and desktop compatibility"),category:"shell"}
    ]
}
