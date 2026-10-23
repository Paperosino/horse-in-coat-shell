pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.modules.nexus.common
PageBase {
    pageIcon: "palette"
    id: root
    property bool cursorThemes: false
    readonly property string kind: cursorThemes ? "cursors" : "icons"
    readonly property var themes: cursorThemes ? AppearanceThemes.cursors : AppearanceThemes.icons
    property string selected: ""
    property int cursorSize: AppearanceThemes.current.size ?? 24
    property string query: ""
    readonly property string activeTheme: AppearanceThemes.current[kind] ?? ""
    readonly property string choice: selected || (themes.some(t => t.id === activeTheme) ? activeTheme : themes[0]?.id ?? "")
    readonly property var chosen: themes.find(t => t.id === choice)
    readonly property var filtered: themes.filter(t => (t.name+" "+t.id).toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
    title: cursorThemes ? Tr.tr("Cursor appearance") : Tr.tr("Application icons")
    objectName: cursorThemes ? "cursorThemesPage" : "iconThemesPage"
    function previewLabel(name: string): string {
        return ({folder:Tr.tr("Folder"),"user-home":Tr.tr("Home"),"text-x-generic":Tr.tr("Document"),
            "web-browser":Tr.tr("Browser"),"user-trash":Tr.tr("Trash"),"preferences-system":Tr.tr("Settings"),
            left_ptr:Tr.tr("Arrow"),pointer:Tr.tr("Link"),text:Tr.tr("Text"),wait:Tr.tr("Waiting"),
            crosshair:Tr.tr("Crosshair"),grab:Tr.tr("Grab"),grabbing:Tr.tr("Dragging"),"ew-resize":Tr.tr("Resize")})[name] ?? name;
    }
    ColumnLayout {
        width:root.cappedWidth
        anchors.horizontalCenter:parent.horizontalCenter
        spacing:Tokens.spacing.medium
        SettingsGuide {
            icon:root.cursorThemes ? "arrow_selector_tool" : "interests"
            title:root.cursorThemes ? Tr.tr("One pointer, across your desktop") : Tr.tr("A matching set for your applications")
            description:Tr.tr("1. Find a theme   2. Preview it   3. Apply")
            badges:root.cursorThemes ? ["GTK", "Qt 5", "Qt 6", "Flatpak", "X11", "Wayland"] : ["GTK", "Qt 5", "Qt 6", "Flatpak"]
        }
        FeatureError { error:AppearanceThemes.error }
        StyledText { Layout.fillWidth:true;visible:AppearanceThemes.notice.length>0;text:AppearanceThemes.notice;wrapMode:Text.WordWrap;font:Tokens.font.body.small;textFormat:Text.PlainText }
        ConnectedRect {
            Layout.fillWidth:true
            implicitHeight:selection.implicitHeight+Tokens.padding.large*2
            first:true;last:true
            ColumnLayout {
                id:selection
                anchors {left:parent.left;right:parent.right;top:parent.top;margins:Tokens.padding.large}
                spacing:Tokens.spacing.medium
                RowLayout {
                    Layout.fillWidth:true
                    ColumnLayout {
                        Layout.fillWidth:true
                        StyledText { Layout.fillWidth:true;text:root.chosen?.name ?? root.choice;font:Tokens.font.title.medium;wrapMode:Text.WordWrap;textFormat:Text.PlainText }
                        StyledText { Layout.fillWidth:true;text:root.choice===root.activeTheme ? Tr.tr("Current theme") : Tr.tr("Preview — not applied yet");font:Tokens.font.body.small;color:Colours.palette.m3onSurfaceVariant }
                    }
                    TextButton {
                        text:AppearanceThemes.busy ? Tr.tr("Applying…") : Tr.tr("Apply theme")
                        disabled:AppearanceThemes.busy || !root.chosen
                        onClicked:AppearanceThemes.apply(root.kind,root.choice,root.cursorSize)
                    }
                }
                GridLayout {
                    Layout.fillWidth:true
                    columns: root.cursorThemes ? (width > 460*Tokens.scale ? 8 : 4) : (width > 380*Tokens.scale ? 6 : 3)
                    columnSpacing:Tokens.spacing.small
                    rowSpacing:Tokens.spacing.small
                    Repeater {
                        model:root.chosen?.previews ?? []
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth:true
                            Layout.minimumWidth:0
                            Image { Layout.alignment:Qt.AlignHCenter;Layout.preferredWidth:40*Tokens.scale;Layout.preferredHeight:40*Tokens.scale;source:parent.modelData.source;fillMode:Image.PreserveAspectFit;sourceSize:Qt.size(64,64);asynchronous:true }
                            StyledText { Layout.fillWidth:true;text:root.previewLabel(parent.modelData.name);font:Tokens.font.label.small;elide:Text.ElideRight;horizontalAlignment:Text.AlignHCenter }
                        }
                    }
                }
            }
        }
        StepperRow {
            visible:root.cursorThemes
            label:Tr.tr("Cursor size")
            subtext:Tr.tr("Pixels. Applied to GTK, Qt, X11, Wayland and Flatpak.")
            from:16;to:96;stepSize:4
            value:root.cursorSize
            onMoved:v=>root.cursorSize=v
        }
        SearchBar { Layout.fillWidth:true;placeholderText:root.cursorThemes ? Tr.tr("Search cursor themes") : Tr.tr("Search icon themes");onTextChanged:root.query=text }
        RowLayout {
            Layout.fillWidth:true
            StyledText { Layout.fillWidth:true;text:AppearanceThemes.loading ? Tr.tr("Loading themes…") : Tr.tr("Installed themes");font:Tokens.font.title.small }
            IconButton { icon:"refresh";disabled:AppearanceThemes.loading || AppearanceThemes.busy;Accessible.name:Tr.tr("Refresh themes");onClicked:AppearanceThemes.reload() }
        }
        GridLayout {
            Layout.fillWidth:true
            columns:width>=540*Tokens.scale ? 2 : 1
            columnSpacing:Tokens.spacing.small
            rowSpacing:Tokens.spacing.small
            Repeater {
                model:root.filtered
                delegate: StyledRect {
                    id:card
                    required property var modelData
                    Layout.fillWidth:true
                    Layout.minimumWidth:0
                    implicitHeight:cardContent.implicitHeight+Tokens.padding.large*2
                    radius:Tokens.rounding.large
                    color:root.choice===modelData.id ? Colours.palette.m3secondaryContainer : Colours.tPalette.m3surfaceContainer
                    border.width:root.choice===modelData.id ? 2*Tokens.scale : 0
                    border.color:Colours.palette.m3primary
                    StateLayer { onClicked:root.selected=card.modelData.id }
                    Accessible.role:Accessible.RadioButton
                    Accessible.name:modelData.name
                    Accessible.checked:root.choice===modelData.id
                    activeFocusOnTab:true
                    Keys.onSpacePressed:root.selected=modelData.id
                    Keys.onReturnPressed:root.selected=modelData.id
                    ColumnLayout {
                        id:cardContent
                        anchors {left:parent.left;right:parent.right;top:parent.top;margins:Tokens.padding.large}
                        spacing:Tokens.spacing.medium
                        RowLayout {
                            Layout.fillWidth:true
                            StyledText { Layout.fillWidth:true;Layout.minimumWidth:0;text:card.modelData.name;font:Tokens.font.body.medium;elide:Text.ElideRight;textFormat:Text.PlainText }
                            MaterialIcon { text:root.choice===card.modelData.id ? "check_circle" : "radio_button_unchecked";color:Colours.palette.m3primary;fontStyle:Tokens.font.icon.small }
                        }
                        RowLayout {
                            Layout.fillWidth:true
                            Repeater {
                                model:card.modelData.previews.slice(0,4)
                                delegate: Image { required property var modelData;Layout.fillWidth:true;Layout.preferredHeight:32*Tokens.scale;source:modelData.source;fillMode:Image.PreserveAspectFit;sourceSize:Qt.size(48,48);asynchronous:true }
                            }
                        }
                        StyledText { Layout.fillWidth:true;text:card.modelData.id===root.activeTheme ? Tr.tr("Current theme") : card.modelData.id;font:Tokens.font.label.small;color:Colours.palette.m3onSurfaceVariant;elide:Text.ElideRight;textFormat:Text.PlainText }
                    }
                    Behavior on color { CAnim {} }
                }
            }
        }
        SettingsGuide {
            visible:!AppearanceThemes.loading && root.filtered.length===0
            icon:"search_off"
            title:root.themes.length ? Tr.tr("No matching themes") : Tr.tr("No themes installed")
            description:root.themes.length ? Tr.tr("Try another name or clear the search.") : Tr.tr("Install a theme in ~/.local/share/icons, then refresh this list.")
        }
        StyledText {
            Layout.fillWidth:true
            text:Tr.tr("GTK, Qt 5 and Qt 6 share this selection. Changes are saved for your next sign-in. Applications with built-in icons or cursors may keep their own appearance.") + (AppearanceThemes.flatpak ? "\n"+Tr.tr("Flatpak: settings are updated for installed applications without granting access to your home folder. Support depends on the application's runtime.") : "")
            font:Tokens.font.body.small;color:Colours.palette.m3onSurfaceVariant;wrapMode:Text.WordWrap
        }
    }
}
