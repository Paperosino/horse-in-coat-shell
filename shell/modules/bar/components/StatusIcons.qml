pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Hyprstack.Config
import Hyprstack.Services
import Hyprstack.I18n
import qs.modules.nexus
import qs.components
import qs.services
import qs.utils
import qs.modules.bar.components.status

StyledRect {
    id: root

    property color colour: Colours.palette.m3secondary
    readonly property alias items: iconColumn

    readonly property int spacing: Tokens.spacing.medium / 2

    // Index of the first/last entry that isn't collapsed, for edge margin gating
    readonly property int firstPresent: {
        const values = model.values;
        for (let i = 0; i < values.length; i++)
            if (!collapsed(values[i]))
                return i;
        return -1;
    }
    readonly property int lastPresent: {
        const values = model.values;
        for (let i = values.length - 1; i >= 0; i--)
            if (!collapsed(values[i]))
                return i;
        return -1;
    }

    // Entries that can shrink to nothing, spacing included
    function collapsed(entry: var): bool {
        if (entry.id === "lockStatus")
            return !Hypr.capsLock && !Hypr.numLock;
        return false;
    }

    color: "transparent"
    radius: Tokens.rounding.full

    GroupBackground {}

    clip: true
    implicitWidth: iconColumn.implicitWidth + Tokens.padding.medium * 2
    implicitHeight: Tokens.sizes.bar.innerWidth

    RowLayout {
        id: iconColumn

        anchors.centerIn: parent

        spacing: 0

        Item {
            visible: Audio.privacyMuted || Audio.microphoneStreams.length>0 || Recorder.busy || DesktopIntegration.microphoneTesting || DesktopIntegration.captureStreams.length > 0
            implicitWidth: visible ? captureIcon.implicitWidth + Tokens.padding.small : 0
            implicitHeight: captureIcon.implicitHeight
            Accessible.role: Accessible.Button
            Accessible.name: Tr.tr("Recording or video capture is active")
            MaterialIcon {
                id: captureIcon
                anchors.centerIn: parent
                text: Audio.privacyMuted ? "mic_off" : Audio.microphoneStreams.length>0 || DesktopIntegration.microphoneTesting ? "mic" : "screen_record"
                color: Colours.palette.m3error
                fontStyle: Tokens.font.icon.medium
            }
            StateLayer { onClicked: WindowFactory.openPage("sharing") }
        }

        Item {
            id:operationsIndicator
            objectName:"backgroundOperationsIndicator"
            property string name:"operations"
            property real extent:BackgroundOperations.visible?operationsRow.implicitWidth+Tokens.padding.small:0
            Layout.alignment:Qt.AlignVCenter
            implicitWidth:extent
            implicitHeight:Tokens.sizes.bar.innerWidth
            visible:extent>0.5
            clip:true
            Accessible.role:Accessible.Button
            Accessible.name:Tr.tr("Background operations")+": "+BackgroundOperations.count
            Behavior on extent {Anim {}}
            Row {
                id:operationsRow;anchors.centerIn:parent;spacing:Tokens.spacing.extraSmall
                MaterialIcon {text:BackgroundOperations.errors?"error":"pending_actions";color:BackgroundOperations.errors?Colours.palette.m3error:root.colour;fontStyle:Tokens.font.icon.medium}
                StyledText {text:String(BackgroundOperations.count);color:root.colour;font:Tokens.font.mono.small;anchors.verticalCenter:parent.verticalCenter}
            }
            Rectangle {visible:GlobalConfig.utilities.operations.showProgress&&BackgroundOperations.progress>=0;anchors.bottom:parent.bottom;anchors.bottomMargin:Tokens.padding.extraSmall;anchors.left:parent.left;implicitHeight:2*Tokens.scale;width:parent.width*BackgroundOperations.progress;color:Colours.palette.m3primary;radius:height/2}
            StateLayer {onClicked:{BackgroundOperations.acknowledge();WindowFactory.openPage("operations");}}
        }

        Repeater {
            model: ScriptModel {
                id: model

                values: root.Config.bar.statusIcons.values.filter(e => e.enabled)
            }

            DelegateChooser {
                role: "id"

                DelegateChoice {
                    roleValue: "lockStatus"
                    delegate: EntryWrapper {
                        LockStatus {
                            colour: root.colour
                            parentSpacing: root.spacing
                        }
                    }
                }
                DelegateChoice {
                    roleValue: "audio"
                    delegate: EntryWrapper {
                        margin: Tokens.spacing.extraSmall / 2

                        MaterialIcon {
                            animate: true
                            text: Icons.getVolumeIcon(Audio.volume, Audio.muted)
                            color: root.colour
                            fontStyle: Tokens.font.icon.medium
                            fill: 1
                        }
                    }
                }
                DelegateChoice {
                    roleValue: "microphone"
                    delegate: EntryWrapper {
                        margin: Tokens.spacing.extraSmall / 2
                        name: "audio" // Mic opens audio popout

                        MaterialIcon {
                            animate: true
                            text: Icons.getMicVolumeIcon(Audio.sourceVolume, Audio.sourceMuted)
                            color: root.colour
                            fontStyle: Tokens.font.icon.medium
                            fill: 1
                        }
                    }
                }
                DelegateChoice {
                    roleValue: "kbLayout"
                    delegate: EntryWrapper {
                        StyledText {
                            animate: true
                            text: Hypr.kbLayout
                            color: root.colour
                            font: Tokens.font.mono.medium
                        }
                    }
                }
                DelegateChoice {
                    roleValue: "network"
                    delegate: EntryWrapper {
                        MaterialIcon {
                            animate: true
                            text: Nmcli.activeEthernet ? "cable" : Nmcli.active ? Icons.getNetworkIcon(Nmcli.active.strength ?? 0) : "wifi_off"
                            color: root.colour
                        }
                    }
                }
                DelegateChoice {
                    roleValue: "bluetooth"
                    delegate: EntryWrapper {
                        BluetoothStatus {
                            colour: root.colour
                        }
                    }
                }
                DelegateChoice {
                    roleValue: "battery"
                    delegate: EntryWrapper {
                        BatteryStatus {
                            colour: root.colour
                        }
                    }
                }
            }
        }
    }

    component EntryWrapper: Item {
        required property var modelData
        required property int index
        property int margin: root.spacing / 2
        readonly property bool present: !root.collapsed(modelData)
        property real topGap: present && index !== root.firstPresent ? margin : 0
        property real bottomGap: present && index !== root.lastPresent ? margin : 0
        default property Item item
        property string name: modelData.id.toLowerCase()

        Layout.leftMargin: Math.round(topGap)
        Layout.rightMargin: Math.round(bottomGap)
        Layout.alignment: Qt.AlignVCenter

        implicitWidth: item?.implicitWidth ?? 0
        implicitHeight: item?.implicitHeight ?? 0

        children: item

        Behavior on topGap {
            Anim {
                type: Anim.SlowEffects
            }
        }

        Behavior on bottomGap {
            Anim {
                type: Anim.SlowEffects
            }
        }
    }
}
