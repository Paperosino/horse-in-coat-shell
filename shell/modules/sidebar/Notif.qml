pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.utils

StyledRect {
    id: root

    required property NotifData modelData
    required property Props props
    required property bool expanded
    required property ScreenState screenState

    readonly property StyledText body: bodyText
    readonly property real nonAnimHeight: content.implicitHeight + Tokens.padding.medium * 2

    implicitHeight: nonAnimHeight
    radius: Tokens.rounding.medium
    color: Colours.layer(Colours.palette.m3surfaceContainerHigh, 2)

    ColumnLayout {
        id: content

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Tokens.padding.medium
        spacing: Tokens.spacing.small

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.extraSmall

            Rectangle {
                visible: !(root.modelData?.read ?? true)
                width: 5 * Tokens.scale
                height: 5 * Tokens.scale
                radius: 3 * Tokens.scale
                color: Colours.palette.m3primary
            }

            Item {
                Layout.fillWidth: true
                implicitHeight: summary.implicitHeight

                StateLayer {
                    onClicked: {
                        if (root.modelData?.activate())
                            root.screenState.sidebar = false;
                        else {
                            const app = root.modelData?.appName;
                            if (root.props.expandedNotifs.includes(app))
                                root.props.expandedNotifs.splice(root.props.expandedNotifs.indexOf(app), 1);
                            else
                                root.props.expandedNotifs.push(app);
                        }
                    }
                }
                StyledText {
                    id: summary
                    anchors.fill: parent
                    text: root.modelData?.summary ?? ""
                    textFormat: Text.PlainText
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    maximumLineCount: root.expanded ? 5 : 2
                    elide: Text.ElideRight
                }
            }

            IconButton {
                objectName: "dismissNotification_" + (root.modelData?.historyId ?? "")
                icon: "close"
                type: IconButton.Text
                padding: 2 * Tokens.scale
                onClicked: root.modelData?.close()
                Accessible.name: Tr.tr("Dismiss notification")
            }
        }

        StyledText {
            id: bodyText

            Layout.fillWidth: true
            visible: text.length > 0
            text: root.modelData?.body ?? ""
            textFormat: Text.RichText
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.body.small
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            maximumLineCount: root.expanded ? Number.MAX_SAFE_INTEGER : 2
            elide: Text.ElideRight
            onLinkActivated: link => {
                Qt.openUrlExternally(link);
                root.screenState.sidebar = false;
            }
        }

        Item {
            Layout.fillWidth: true
            visible: root.modelData?.screenshot ?? false
            implicitHeight: Math.min(180, width * .625)

            Rectangle {
                anchors.fill: parent
                radius: Tokens.rounding.small
                color: Colours.palette.m3surfaceContainerLowest
            }
            Image {
                id: screenshot
                objectName: "notificationScreenshot_" + (root.modelData?.historyId ?? "")
                anchors.fill: parent
                anchors.margins: 2 * Tokens.scale
                source: Paths.fileUrl(root.modelData?.image ?? "")
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                sourceSize.width: 800
            }
            MaterialIcon {
                anchors.centerIn: parent
                visible: screenshot.status === Image.Error
                text: "broken_image"
                color: Colours.palette.m3onSurfaceVariant
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.modelData?.imageAction("open")
            }
        }

        StyledText {
            Layout.alignment: Qt.AlignRight
            text: root.modelData?.timeStr ?? ""
            color: Colours.palette.m3outline
            font: Tokens.font.label.small
        }

        NotifActionList {
            visible: root.expanded || (root.modelData?.screenshot ?? false)
            notif: root.modelData
        }
    }

    Behavior on implicitHeight { Anim {} }
}
