import Hyprstack.Config
import Hyprstack.I18n
import QtQuick
import QtQuick.Layouts
import qs.modules.nexus.common
import qs.components
import qs.components.controls
import qs.services

PageBase {
    id: root

    pageIcon: "accessibility_new"
    title: Tr.tr("Accessibility")

    readonly property FeatureBackend reader: FeatureBackend {helper:"accessibility_manager.py"}
    property var readerState:({settings:{},values:{},supported:[]})
    function refreshReader():void {reader.call(["status"],null,value=>{if(!value.error)readerState=value;});}
    function configureReader(values:var):void {reader.call(["configure"],values,value=>{if(!value.error)readerState=value;});}
    Component.onCompleted:refreshReader()
    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.cappedWidth
        spacing: Tokens.spacing.large

        SettingsCard {
            title:Tr.tr("Find the pointer");icon:"my_location"
            description:Tr.tr("Show a high-contrast ring at the pointer's current position. Reduced motion uses a still ring, and clicks pass through it.")
            ToggleRow {text:Tr.tr("Enable pointer locator");checked:GlobalConfig.utilities.comfort.cursorLocator;onToggled:GlobalConfig.utilities.comfort.cursorLocator=checked}
            StepperRow {label:Tr.tr("Pointer highlight duration (seconds)");from:1;to:5;value:GlobalConfig.utilities.comfort.cursorLocatorSeconds;onMoved:value=>GlobalConfig.utilities.comfort.cursorLocatorSeconds=value}
            RowButton {text:Tr.tr("Find my pointer now");icon:"my_location";onClicked:CursorLocator.show()}
            InfoRow {label:Tr.tr("Custom shortcut");value:"hics-shell ipc call comfort findCursor"}
        }
        SettingsCard {
            title: Tr.tr("Interface")
            icon: "contrast"

            ToggleRow {
                first: true
                text: Tr.tr("High contrast")
                subtext: Tr.tr("Use an opaque, high-contrast palette in the shell")
                checked: GlobalConfig.appearance.highContrast
                onToggled: GlobalConfig.appearance.highContrast = checked
            }

            ToggleRow {
                text: Tr.tr("Reduce motion")
                subtext: Tr.tr("Disable shell transitions and animated interaction effects")
                checked: GlobalConfig.appearance.reducedMotion
                onToggled: GlobalConfig.appearance.reducedMotion = checked
            }

            StepperRow {
                last: true
                label: Tr.tr("Interface scale")
                value: GlobalConfig.appearance.scale
                from: 0.75
                to: 2
                stepSize: 0.05
                onMoved: value => {
                    return GlobalConfig.appearance.scale = value;
                }
            }
        }

        SettingsCard {
            title:Tr.tr("Screen reader")
            description:Tr.tr("Orca reads focused controls through AT-SPI. Speech preferences are applied through Orca’s supported settings; its native dialog exposes additional voices and profiles.")
            icon:"record_voice_over"
            FeatureError {error:root.reader.error}
            InfoRow {label:Tr.tr("Status");value:root.readerState.running?Tr.tr("Running"):root.readerState.available?Tr.tr("Stopped"):Tr.tr("Not installed")}
            ToggleRow {text:Tr.tr("Enable screen reader");checked:root.readerState.settings?.enabled??false;enabled:!root.reader.busy;onToggled:root.configureReader({enabled:checked})}
            ToggleRow {text:Tr.tr("Start screen reader after login");checked:root.readerState.settings?.autostart??false;enabled:!root.reader.busy;onToggled:root.configureReader({autostart:checked})}
            Repeater {
                model:[{key:"rate",label:"Speech rate",type:"int",min:0,max:100},{key:"speech",label:"Speech output",type:"bool"},{key:"characterEcho",label:"Read typed characters",type:"bool"},{key:"wordEcho",label:"Read typed words",type:"bool"},{key:"mouseReview",label:"Read items under the pointer",type:"bool"},{key:"braille",label:"Braille output",type:"bool"}].filter(f=>(root.readerState.supported??[]).includes(f.key))
                GenericSettingRow {required property var modelData;spec:Object.assign({},modelData,{value:root.readerState.values?.[modelData.key]});onEdited:value=>root.configureReader({[modelData.key]:value})}
            }
            StepperRow {visible:(root.readerState.supported??[]).includes("pitch");label:Tr.tr("Speech pitch");from:0;to:10;stepSize:0.1;value:root.readerState.values?.pitch??5;onMoved:value=>root.configureReader({pitch:value})}
            StepperRow {visible:(root.readerState.supported??[]).includes("volume");label:Tr.tr("Speech volume");from:0;to:10;stepSize:0.1;value:root.readerState.values?.volume??10;onMoved:value=>root.configureReader({volume:value})}
            RowButton {text:Tr.tr("Advanced Orca preferences");icon:"settings_voice";disabled:!root.readerState.available;onClicked:root.reader.call(["preferences"])}
        }
        SettingsCard {
            title: Tr.tr("Keyboard navigation")
            icon: "keyboard"

            InfoRow {
                first: true
                label: Tr.tr("Keyboard navigation")
                value: Tr.tr("Tab / Shift+Tab to move, Enter / Space to activate")
            }

            InfoRow {
                last: true
                label: Tr.tr("Screen reader support")
                value: Tr.tr("Controls expose names, states and actions through AT-SPI. Use Tab or Shift+Tab to move between controls and Enter or Space to activate them.")
            }
        }
    }
}
