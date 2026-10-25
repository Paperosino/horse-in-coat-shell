pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Services.Notifications
import Hyprstack.Components
import Hyprstack.Config
import qs.components
import qs.components.controls
import qs.components.effects
import qs.services
import qs.utils

StyledRect {
    id: root
    objectName: "notificationPopup"

    required property NotifData modelData
    // Releasing the last UI lock can destroy the data before its child items.
    readonly property bool isScreenshot: root.modelData?.screenshot ?? false
    readonly property bool hasImage: (modelData?.image.length ?? 0) > 0
    readonly property bool hasAppIcon: (modelData?.appIcon.length ?? 0) > 0
    readonly property int bodyTextFormat: /[<*_`#\[\]]/.test(modelData?.body ?? "") ? Text.MarkdownText : Text.PlainText
    readonly property int nonAnimHeight: root.isScreenshot
        ? (TokenConfig.sizes.notifs.image + Tokens.spacing.small + screenshotCard.implicitHeight + Tokens.spacing.small + screenshotActions.implicitHeight + inner.anchors.margins * 2)
        : (summary.implicitHeight + (root.expanded ? Tokens.spacing.extraSmall * 2 + appName.height + body.height + actions.height + actions.anchors.topMargin : bodyPreview.height) + inner.anchors.margins * 2)
    property bool expanded: Config.notifs.openExpanded

    color: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3secondaryContainer : Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.large

    implicitHeight: inner.implicitHeight

    x: implicitWidth
    Component.onCompleted: {
        x = 0;
        modelData?.lock(this);
    }
    Component.onDestruction: modelData?.unlock(this)

    Behavior on x {
        Anim {
            easing: Tokens.anim.emphasizedDecel
        }
    }

    MouseArea {
        property int startY

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.expanded && body.hoveredLink ? Qt.PointingHandCursor : pressed ? Qt.ClosedHandCursor : undefined
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        preventStealing: true

        onEntered: root.modelData?.pauseExpiry()
        onExited: {
            if (!pressed && root.modelData && root.modelData.expireTimeout !== 0)
                root.modelData.resumeExpiry();
        }

        drag.target: parent
        drag.axis: Drag.XAxis

        onPressed: event => {
            root.modelData?.pauseExpiry();
            startY = event.y;
            if (event.button === Qt.MiddleButton)
                root.modelData?.close();
        }
        onReleased: event => {
            if (!containsMouse && root.modelData && root.modelData.expireTimeout !== 0)
                root.modelData.resumeExpiry();

            if (Math.abs(root.x) < root.implicitWidth * Config.notifs.clearThreshold)
                root.x = 0;
            else if (root.modelData)
                root.modelData.popup = false;
        }
        onPositionChanged: event => {
            if (pressed) {
                const diffY = event.y - startY;
                if (Math.abs(diffY) > Config.notifs.expandThreshold)
                    root.expanded = diffY > 0;
            }
        }
        onClicked: event => {
            if (!GlobalConfig.notifs.actionOnClick || event.button !== Qt.LeftButton)
                return;

            root.modelData?.activate();
        }

        Item {
            id: inner

            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Tokens.padding.medium

            implicitHeight: root.nonAnimHeight

            Behavior on implicitHeight {
                Anim {}
            }

            Loader {
                id: image

                asynchronous: true
                active: !root.isScreenshot && root.hasImage

                anchors.left: parent.left
                anchors.top: parent.top
                width: TokenConfig.sizes.notifs.image
                height: TokenConfig.sizes.notifs.image
                visible: (!root.isScreenshot && root.hasImage) || root.hasAppIcon

                sourceComponent: StyledClippingRect {
                    radius: Tokens.rounding.full
                    color: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3error : root.modelData?.urgency === NotificationUrgency.Low ? Colours.layer(Colours.palette.m3surfaceContainerHighest, 2) : Colours.palette.m3secondaryContainer
                    implicitWidth: TokenConfig.sizes.notifs.image
                    implicitHeight: TokenConfig.sizes.notifs.image

                    Image {
                        anchors.fill: parent
                        source: Paths.fileUrl(root.modelData?.image ?? "")
                        fillMode: Image.PreserveAspectCrop
                        sourceSize: {
                            const size = TokenConfig.sizes.notifs.image * ((QsWindow.window as QsWindow)?.devicePixelRatio ?? 1);
                            return Qt.size(size, size);
                        }
                        cache: false
                        asynchronous: true
                    }
                }
            }

            Loader {
                id: appIcon

                asynchronous: true
                active: root.isScreenshot || root.hasAppIcon || !root.hasImage

                anchors.horizontalCenter: (root.hasImage && !root.isScreenshot) ? undefined : image.horizontalCenter
                anchors.verticalCenter: (root.hasImage && !root.isScreenshot) ? undefined : image.verticalCenter
                anchors.right: (root.hasImage && !root.isScreenshot) ? image.right : undefined
                anchors.bottom: (root.hasImage && !root.isScreenshot) ? image.bottom : undefined

                sourceComponent: StyledRect {
                    radius: Tokens.rounding.full
                    color: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3error : root.modelData?.urgency === NotificationUrgency.Low ? Colours.layer(Colours.palette.m3surfaceContainerHighest, 2) : Colours.palette.m3secondaryContainer
                    implicitWidth: (root.hasImage && !root.isScreenshot) ? Tokens.sizes.notifs.badge : TokenConfig.sizes.notifs.image
                    implicitHeight: (root.hasImage && !root.isScreenshot) ? Tokens.sizes.notifs.badge : TokenConfig.sizes.notifs.image

                    Loader {
                        id: icon

                        asynchronous: true
                        active: !root.isScreenshot && root.hasAppIcon

                        anchors.centerIn: parent

                        width: Math.round(parent.width * 0.6)
                        height: Math.round(parent.width * 0.6)

                        sourceComponent: ColouredIcon {
                            anchors.fill: parent
                            source: Quickshell.iconPath(root.modelData?.appIcon ?? "")
                            colour: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3onError : root.modelData?.urgency === NotificationUrgency.Low ? Colours.palette.m3onSurface : Colours.palette.m3onSecondaryContainer
                            layer.enabled: root.modelData?.appIcon.endsWith("symbolic") ?? false
                        }
                    }

                    Loader {
                        asynchronous: true
                        active: root.isScreenshot || !root.hasAppIcon
                        anchors.centerIn: parent
                        anchors.verticalCenterOffset: 1

                        sourceComponent: MaterialIcon {
                            text: root.isScreenshot ? "screenshot_monitor" : Icons.getNotifIcon(root.modelData?.summary ?? "", root.modelData?.urgency ?? NotificationUrgency.Normal)
                            color: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3onError : root.modelData?.urgency === NotificationUrgency.Low ? Colours.palette.m3onSurface : Colours.palette.m3onSecondaryContainer
                            fontStyle: Tokens.font.icon.medium
                        }
                    }
                }
            }

            Shape {
                id: progressIndicator

                visible: !root.isScreenshot

                anchors.centerIn: appIcon
                width: appIcon.implicitWidth + progressShape.strokeWidth * 2
                height: appIcon.implicitHeight + progressShape.strokeWidth * 2
                preferredRendererType: Shape.CurveRenderer

                ShapePath {
                    id: progressShape

                    capStyle: ShapePath.RoundCap
                    fillColor: "transparent"
                    strokeWidth: 2
                    strokeColor: Colours.palette.m3primary

                    PathAngleArc {
                        id: progressArc

                        radiusX: progressIndicator.width / 2 - root.Tokens.padding.extraSmall / 2
                        centerX: progressIndicator.width / 2
                        radiusY: progressIndicator.height / 2 - root.Tokens.padding.extraSmall / 2
                        centerY: progressIndicator.height / 2

                        startAngle: -90
                        sweepAngle: ((root.modelData?.hints?.value ?? 0) / 100) * 360

                        Behavior on sweepAngle {
                            Anim {
                                easing: Tokens.anim.emphasizedDecel
                            }
                        }
                    }
                }
            }

            StyledText {
                id: appName

                anchors.top: parent.top
                anchors.left: image.right
                anchors.leftMargin: Tokens.spacing.medium

                animate: true
                text: appNameMetrics.elidedText
                maximumLineCount: 1
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.label.medium

                opacity: (root.expanded || root.isScreenshot) ? 1 : 0

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }

            TextMetrics {
                id: appNameMetrics

                text: root.modelData?.appName ?? ""
                font: appName.font
                elide: Text.ElideRight
                elideWidth: expandBtn.x - time.width - timeSep.width - summary.x - root.Tokens.spacing.small * 3
            }

            StyledText {
                id: summary

                anchors.top: parent.top
                anchors.left: image.right
                anchors.leftMargin: Tokens.spacing.medium

                animate: true
                text: summaryMetrics.elidedText
                maximumLineCount: 1
                height: implicitHeight

                states: State {
                    name: "expanded"
                    when: root.expanded || root.isScreenshot

                    PropertyChanges {
                        summary.maximumLineCount: undefined
                        summary.anchors.topMargin: root.Tokens.spacing.extraSmall
                        bodyPreview.anchors.topMargin: root.Tokens.spacing.extraSmall
                        body.anchors.topMargin: root.Tokens.spacing.extraSmall
                    }

                    AnchorChanges {
                        target: summary
                        anchors.top: appName.bottom
                    }
                }

                transitions: Transition {
                    PropertyAction {
                        target: summary
                        property: "maximumLineCount"
                    }
                    Anim {
                        property: "topMargin"
                    }
                    AnchorAnim {}
                }

                Behavior on height {
                    Anim {}
                }
            }

            TextMetrics {
                id: summaryMetrics

                text: root.modelData?.summary ?? ""
                font: summary.font
                elide: Text.ElideRight
                elideWidth: expandBtn.x - time.width - timeSep.width - summary.x - root.Tokens.spacing.small * 3
            }

            StyledText {
                id: timeSep

                anchors.top: parent.top
                anchors.left: summary.right
                anchors.leftMargin: Tokens.spacing.small

                text: "•"
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small

                states: State {
                    name: "expanded"
                    when: root.expanded || root.isScreenshot

                    AnchorChanges {
                        target: timeSep
                        anchors.left: appName.right
                    }
                }

                transitions: Transition {
                    AnchorAnim {}
                }
            }

            StyledText {
                id: time

                anchors.top: parent.top
                anchors.left: timeSep.right
                anchors.leftMargin: Tokens.spacing.small

                animate: true
                horizontalAlignment: Text.AlignLeft
                text: root.modelData?.timeStr ?? ""
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small
            }

            Item {
                id: expandBtn

                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: -Tokens.padding.extraSmall

                implicitWidth: expandIcon.implicitHeight
                implicitHeight: expandIcon.implicitHeight

                StateLayer {
                    radius: Tokens.rounding.full
                    color: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3onSecondaryContainer : Colours.palette.m3onSurface
                    onClicked: {
                        if (root.isScreenshot) {
                            root.modelData?.close();
                        } else {
                            root.expanded = !root.expanded;
                        }
                    }
                }

                MaterialIcon {
                    id: expandIcon

                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: root.isScreenshot ? 0 : (root.expanded ? -1 : 1)
                    text: root.isScreenshot ? "close" : "expand_more"
                    fontStyle: Tokens.font.icon.medium
                    rotation: root.isScreenshot ? 0 : (root.expanded ? 180 : 0)

                    Behavior on anchors.verticalCenterOffset {
                        Anim {}
                    }

                    Behavior on rotation {
                        Anim {}
                    }
                }
            }

            StyledText {
                id: bodyPreview

                visible: !root.isScreenshot
                anchors.left: summary.left
                anchors.right: expandBtn.left
                anchors.top: summary.bottom
                anchors.rightMargin: Tokens.spacing.small

                animate: true
                textFormat: root.bodyTextFormat
                text: bodyPreviewMetrics.elidedText
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small

                opacity: root.expanded ? 0 : 1

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }

            TextMetrics {
                id: bodyPreviewMetrics

                text: root.modelData?.body ?? ""
                font: bodyPreview.font
                elide: Text.ElideRight
                elideWidth: bodyPreview.width
            }

            StyledText {
                id: body

                visible: !root.isScreenshot
                anchors.left: summary.left
                anchors.right: expandBtn.left
                anchors.top: summary.bottom
                anchors.rightMargin: Tokens.spacing.small

                animate: true
                textFormat: root.bodyTextFormat
                text: root.modelData?.body ?? ""
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.small
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                height: text ? implicitHeight : 0

                onLinkActivated: link => {
                    if (!root.expanded)
                        return;

                    Qt.openUrlExternally(link);
                    if (root.modelData)
                        root.modelData.popup = false;
                }

                opacity: root.expanded ? 1 : 0

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }
            }

            StyledRect {
                id: screenshotCard

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: (summary.y + summary.height > image.height) ? summary.bottom : image.bottom
                anchors.topMargin: Tokens.spacing.small

                visible: root.isScreenshot
                implicitHeight: root.isScreenshot ? Math.min(200 * Tokens.scale, (parent ? parent.width : 360) * 0.5625) : 0
                radius: Tokens.rounding.medium
                color: Colours.palette.m3surfaceContainerLowest
                clip: true

                Image {
                    id: screenshotImage
                    anchors.fill: parent
                    anchors.margins: 4 * Tokens.scale
                    source: Paths.fileUrl(root.modelData?.image ?? "")
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    cache: false
                }

                MaterialIcon {
                    anchors.centerIn: parent
                    visible: screenshotImage.status === Image.Error
                    text: "broken_image"
                    fontStyle: Tokens.font.icon.large
                    color: Colours.palette.m3onSurfaceVariant
                }

                StateLayer {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    color: Colours.palette.m3primary
                    onClicked: root.modelData?.imageAction("open")
                }
            }

            Flow {
                id: screenshotActions

                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: screenshotCard.bottom
                anchors.topMargin: Tokens.spacing.small

                visible: root.isScreenshot
                spacing: Tokens.spacing.extraSmall

                Repeater {
                    model: root.isScreenshot ? (root.modelData?.actions ?? []) : []

                    IconTextButton {
                        required property var modelData

                        isRound: true
                        shapeMorph: true
                        font: Tokens.font.label.medium
                        inactiveColour: Colours.layer(Colours.palette.m3surfaceContainerHighest, 2)
                        inactiveOnColour: Colours.palette.m3onSurfaceVariant
                        icon: ({open: "open_in_new", copy: "content_copy", save: "save", reveal: "folder_open"})[modelData.identifier] ?? ""
                        text: modelData?.text ?? ""
                        onClicked: modelData?.invoke()
                    }
                }
            }

            ButtonRow {
                id: actions

                visible: !root.isScreenshot

                anchors.left: body.left
                anchors.right: body.right
                anchors.top: body.bottom
                anchors.topMargin: Tokens.spacing.small

                spacing: Tokens.spacing.extraSmall
                opacity: root.expanded ? 1 : 0

                Behavior on opacity {
                    Anim {
                        type: Anim.DefaultEffects
                    }
                }

                IconButton {
                    isRound: true
                    shapeMorph: true
                    fillWidth: (root.modelData?.actions.length ?? 0) === 0
                    inactiveColour: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3secondary : Colours.layer(Colours.palette.m3surfaceContainerHighest, 2)
                    inactiveOnColour: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3onSecondary : Colours.palette.m3onSurfaceVariant
                    icon: "close"
                    padding: Tokens.padding.extraSmall
                    onClicked: root.modelData?.close()
                }

                Repeater {
                    model: root.modelData?.actions ?? []

                    TextButton {
                        required property var modelData

                        isRound: true
                        shapeMorph: true
                        fillWidth: true
                        inactiveColour: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3secondary : Colours.layer(Colours.palette.m3surfaceContainerHighest, 2)
                        inactiveOnColour: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3onSecondary : Colours.palette.m3onSurfaceVariant
                        text: modelData?.text ?? ""
                        onClicked: modelData?.invoke()

                        label.horizontalAlignment: Text.AlignHCenter
                        label.anchors.left: left
                        label.anchors.right: right
                        label.anchors.verticalCenter: verticalCenter
                        label.anchors.centerIn: undefined
                        label.anchors.margins: Tokens.padding.medium
                        label.elide: Text.ElideRight
                    }
                }

                IconButton {
                    isRound: true
                    shapeMorph: true
                    fillWidth: (root.modelData?.actions.length ?? 0) === 0
                    inactiveColour: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3secondary : Colours.layer(Colours.palette.m3surfaceContainerHighest, 2)
                    inactiveOnColour: root.modelData?.urgency === NotificationUrgency.Critical ? Colours.palette.m3onSecondary : Colours.palette.m3onSurfaceVariant
                    icon: copyTimer.running ? "inventory" : "content_copy"
                    padding: Tokens.padding.extraSmall
                    onClicked: {
                        if (!root.modelData)
                            return;
                        Quickshell.clipboardText = root.modelData.body;
                        copyTimer.restart();
                    }
                    label.animate: true

                    Timer {
                        id: copyTimer

                        interval: 3000
                    }
                }
            }
        }
    }
}
