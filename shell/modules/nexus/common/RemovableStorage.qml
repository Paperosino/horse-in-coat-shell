pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import Hyprstack.Services
import qs.modules.nexus.common
ColumnLayout {
    id: root
    Layout.fillWidth: true
    spacing: Tokens.spacing.extraSmall / 2
    SectionHeader { text: Tr.tr("Encrypted volumes") }
    Repeater {
        model: DesktopIntegration.encryptedVolumes
        ColumnLayout {
            id: encrypted
            required property var modelData
            Layout.fillWidth: true
            spacing: Tokens.spacing.extraSmall / 2
            InfoRow { first: true; label: encrypted.modelData.label || encrypted.modelData.device; value: encrypted.modelData.unlocked ? Tr.tr("Unlocked") : Tr.tr("Locked") }
            TextFieldRow { id: passphrase; visible: !encrypted.modelData.unlocked; label: Tr.tr("Passphrase"); field.echoMode: TextInput.Password }
            RowButton {
                last: true; disabled: DesktopIntegration.busy || (!encrypted.modelData.unlocked && !passphrase.field.text)
                text: encrypted.modelData.unlocked ? Tr.tr("Lock volume") : Tr.tr("Unlock volume")
                subtext: Tr.tr("Unmount the filesystem before locking")
                icon: encrypted.modelData.unlocked ? "lock" : "lock_open"
                onClicked: {
                    if (encrypted.modelData.unlocked) DesktopIntegration.lockVolume(encrypted.modelData.path);
                    else DesktopIntegration.unlockVolume(encrypted.modelData.path, passphrase.field.text);
                    passphrase.clear();
                }
            }
        }
    }
    SectionHeader { text: Tr.tr("Safely remove drives") }
    Repeater {
        model: DesktopIntegration.removableDrives.filter(d => d.powerOff || d.ejectable)
        RowButton {
            required property var modelData
            first: true; last: true
            text: modelData.model || Tr.tr("Removable drive")
            subtext: Tr.tr("Unmount all volumes on this drive first. Busy drives will not be removed.")
            icon: "eject"; disabled: DesktopIntegration.busy
            onClicked: DesktopIntegration.ejectDrive(modelData.path, modelData.powerOff)
        }
    }
    ToggleRow {
        first: true; last: true
        text: Tr.tr("Open newly connected volumes")
        subtext: Tr.tr("Mount removable filesystems and open them in the file manager. Encrypted volumes require unlocking.")
        checked: GlobalConfig.services.openRemovableVolumes
        onToggled: GlobalConfig.services.openRemovableVolumes = checked
    }
    FeatureError { error: DesktopIntegration.error }
}
