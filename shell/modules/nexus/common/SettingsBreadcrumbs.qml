pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.services
import qs.modules.nexus
Flow {
    id: root
    required property NexusState nState
    required property string title
    property bool detail: false
    readonly property var section: PageRegistry.section(nState.sectionId)
    readonly property var page: PageRegistry.pages[nState.currentPageIdx]
    readonly property var path: {
        const items = [{label:Tr.tr("Settings home"), section:"home", current:nState.showingSection && section.id === "home"}];
        if (section.id !== "home") items.push({label:section.label, section:section.id, current:nState.showingSection});
        if (!nState.showingSection) {
            if (detail && page?.label !== title) items.push({label:page.label, page:page.id});
            // The current title is already the heading below the breadcrumb.
        }
        return items;
    }
    spacing: Tokens.spacing.extraSmall
    Repeater {
        model: root.path
        RowLayout {
            id: crumb
            required property var modelData
            required property int index
            spacing: Tokens.spacing.extraSmall
            MaterialIcon { visible: crumb.index > 0; text:"chevron_right"; color:Colours.palette.m3outline; fontStyle:Tokens.font.icon.small }
            StyledRect {
                implicitWidth: label.implicitWidth + Tokens.padding.small * 2
                implicitHeight: label.implicitHeight + Tokens.padding.small * 2
                radius: Tokens.rounding.medium
                color: "transparent"
                StateLayer {
                    radius: parent.radius
                    enabled: !crumb.modelData.current
                    keyboardFocusable: true
                    Accessible.name: crumb.modelData.label
                    Accessible.role: Accessible.Button
                    onClicked: {
                        if (crumb.modelData.page) root.nState.openPage(crumb.modelData.page);
                        else root.nState.openSection(crumb.modelData.section);
                    }
                }
                StyledText {
                    id: label
                    anchors.centerIn: parent
                    text: crumb.modelData.label
                    font: Tokens.font.label.medium
                    color: crumb.modelData.current ? Colours.palette.m3onSurfaceVariant : Colours.palette.m3primary
                }
            }
        }
    }
}
