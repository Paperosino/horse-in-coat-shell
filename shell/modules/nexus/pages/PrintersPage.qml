pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.modules.nexus.common

PageBase {
    id: root
    pageIcon: "print"
    title: Tr.tr("Printers")
    property bool adding: false
    property string printerName
    property string printerDescription
    property string printerUri
    property string removing
    ColumnLayout {
        width: root.cappedWidth
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Tokens.spacing.large
        NativeSystemBackend {
            id: system
            section: "printers"
            watching: root.visible
        }
        FeatureError {
            error: system.error
        }
        RowButton {
            first: true
            last: true
            text: Tr.tr("Refresh")
            icon: "refresh"
            disabled: system.busy
            onClicked: system.reload()
        }
        SettingsCard {
            title: Tr.tr("Printer queues")
            icon: "tune"

            InfoRow {
                visible: !!system.state.available && !(system.state.printers ?? []).length
                first: true
                last: true
                label: Tr.tr("No printers configured")
                value: Tr.tr("Add a network printer by its IPP address")
            }
            Repeater {
                model: system.state.printers ?? []
                ColumnLayout {
                    id: printer
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Tokens.spacing.extraSmall / 2
                    InfoRow {
                        first: true
                        label: printer.modelData.description || printer.modelData.name
                        value: printer.modelData.isDefault ? Tr.tr("System default printer") : printer.modelData.name
                    }
                    InfoRow {
                        label: Tr.tr("Status")
                        value: (printer.modelData.state === 5 ? Tr.tr("Paused") : printer.modelData.state === 4 ? Tr.tr("Printing") : Tr.tr("Ready")) + (printer.modelData.message ? ": " + printer.modelData.message : "")
                    }
                    InfoRow {
                        visible: !!printer.modelData.model
                        label: Tr.tr("Model")
                        value: printer.modelData.model
                    }
                    RowButton {
                        visible: !printer.modelData.isDefault
                        text: Tr.tr("Use as system default")
                        icon: "check_circle"
                        disabled: system.busy
                        onClicked: system.apply("default", {
                            name: printer.modelData.name
                        })
                    }
                    RowButton {
                        text: printer.modelData.state === 5 ? Tr.tr("Resume printing") : Tr.tr("Pause printing")
                        icon: printer.modelData.state === 5 ? "play_arrow" : "pause"
                        disabled: system.busy
                        onClicked: system.apply(printer.modelData.state === 5 ? "resume" : "pause", {
                            name: printer.modelData.name
                        })
                    }
                    RowButton {
                        last: true
                        text: root.removing === printer.modelData.name ? Tr.tr("Confirm printer removal") : Tr.tr("Remove printer")
                        icon: "delete"
                        disabled: system.busy
                        onClicked: {
                            if (root.removing === printer.modelData.name) {
                                system.apply("remove", {
                                    name: printer.modelData.name
                                });
                                root.removing = "";
                            } else
                                root.removing = printer.modelData.name;
                        }
                    }
                }
            }
            RowButton {
                first: true
                last: true
                text: root.adding ? Tr.tr("Cancel") : Tr.tr("Add IPP printer")
                icon: root.adding ? "close" : "add"
                disabled: system.busy || !system.state.available
                onClicked: root.adding = !root.adding
            }
            ColumnLayout {
                visible: root.adding
                Layout.fillWidth: true
                spacing: Tokens.spacing.extraSmall / 2
                RowButton {
                    first: true
                    last: true
                    text: Tr.tr("Find network printers")
                    icon: "search"
                    disabled: system.busy
                    onClicked: system.discoverPrinters()
                }
                InfoRow {
                    visible: system.discovered && !system.discoveredPrinters.length
                    first: true
                    last: true
                    label: Tr.tr("No network printers found")
                    value: Tr.tr("You can enter the IPP address manually")
                }
                Repeater {
                    model: system.discoveredPrinters
                    RowButton {
                        required property var modelData
                        text: modelData.name
                        subtext: modelData.uri
                        icon: "print"
                        onClicked: {
                            root.printerName = modelData.name.replace(/[^A-Za-z0-9_.-]/g, "_");
                            root.printerDescription = modelData.name;
                            root.printerUri = modelData.uri;
                        }
                    }
                }
                TextFieldRow {
                    first: true
                    label: Tr.tr("Queue name")
                    value: root.printerName
                    placeholderText: "Office_Printer"
                    maximumLength: 127
                    onValueEdited: v => root.printerName = v
                }
                TextFieldRow {
                    label: Tr.tr("Description")
                    value: root.printerDescription
                    maximumLength: 256
                    onValueEdited: v => root.printerDescription = v
                }
                TextFieldRow {
                    label: Tr.tr("Printer address")
                    value: root.printerUri
                    placeholderText: "ipp://printer.local/ipp/print"
                    maximumLength: 2048
                    onValueEdited: v => root.printerUri = v
                }
                RowButton {
                    last: true
                    text: Tr.tr("Add printer")
                    subtext: Tr.tr("Uses IPP Everywhere for driverless network printing")
                    icon: "print_add"
                    disabled: system.busy || !root.printerName || !root.printerUri
                    onClicked: system.apply("add", {
                        name: root.printerName,
                        uri: root.printerUri,
                        description: root.printerDescription || root.printerName
                    })
                }
            }
        }
        SettingsCard {
            title: Tr.tr("Your print jobs")
            icon: "tune"

            InfoRow {
                visible: !(system.state.jobs ?? []).length
                first: true
                last: true
                label: Tr.tr("Print queue is empty")
                value: ""
            }
            Repeater {
                model: system.state.jobs ?? []
                RowButton {
                    required property var modelData
                    first: true
                    last: true
                    text: modelData.title
                    subtext: modelData.printer + " · #" + modelData.id
                    trailingIcon: "cancel"
                    disabled: system.busy
                    onClicked: system.apply("cancel-job", {
                        id: modelData.id
                    })
                }
            }
        }
    }
}
