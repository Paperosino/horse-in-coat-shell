import QtQuick
import QtQuick.Layouts
import M3Shapes
import Hyprstack.Config
import Hyprstack.I18n
import qs.components
import qs.components.controls
import qs.services
import qs.utils

StyledRect {
    id: root

    required property string icon
    required property string label
    required property string subLabel
    required property color accent
    required property real usage
    required property real temperature
    property bool temperatureAvailable: true

    color: Colours.tPalette.m3surfaceContainer
    radius: Tokens.rounding.extraLarge

    implicitWidth: Tokens.sizes.dashboard.perfHeroCardWidth
    implicitHeight: Math.max(tempProg.implicitHeight + detailsRow.implicitHeight + Tokens.spacing.large, usageColumn.implicitHeight) + Tokens.padding.large * 2

    CircularProgress {
        id: tempProg

        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: Tokens.padding.large

        fgColour: root.accent

        spacing: Tokens.spacing.extraSmall
        strokeWidth: Tokens.padding.extraSmall
        implicitSize: Math.max(icon.implicitWidth, icon.implicitHeight) + Tokens.padding.medium * 2
        value: root.usage

        Behavior on clampedVal {
            Anim {}
        }

        MaterialIcon {
            id: icon

            anchors.centerIn: parent
            text: root.icon
            color: root.accent
            fontStyle: Tokens.font.icon.medium
        }
    }

    ColumnLayout {
        anchors.left: tempProg.right
        anchors.right: usageColumn.left
        anchors.verticalCenter: tempProg.verticalCenter
        anchors.margins: Tokens.spacing.large
        spacing: Tokens.spacing.extraSmall

        StyledText {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: root.label
            font: Tokens.font.title.medium
            color: root.accent
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        }

        StyledText {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: root.subLabel
            font: Tokens.font.body.small
            color: Colours.palette.m3onSurfaceVariant
            elide: Text.ElideRight
        }
    }

    ColumnLayout {
        id: detailsRow

        anchors.left: parent.left
        anchors.right: usageColumn.left
        anchors.bottom: parent.bottom
        anchors.margins: Tokens.padding.largeIncreased
        spacing: Tokens.spacing.extraSmall

        RowLayout {
            Layout.leftMargin: -Tokens.padding.extraSmall
            spacing: Tokens.spacing.extraSmall

            MaterialIcon {
                Layout.topMargin: Math.round(fontInfo.pointSize * 0.08)
                text: root.temperature > 90 ? "thermometer_alert" : "thermometer"
                color: root.temperature > 90 ? Colours.palette.m3error : root.accent
                fontStyle: Tokens.font.icon.medium
                fill: 1
            }

            StyledText {
                objectName: "sensorTemperature"
                text: root.temperatureAvailable ? Units.formatSensorTemp(root.temperature) : "—"
                font: Tokens.font.body.builders.medium.build()
            }
        }

        StyledProgressBar {
            objectName: "sensorTemperatureProgress"
            value: root.temperatureAvailable ? root.temperature / 100 : 0
            implicitHeight: Tokens.padding.small
            fgColour: root.accent
            indeterminate: root.temperatureAvailable && (isNaN(root.usage) || isNaN(root.temperature))
        }
    }

    Column {
        id: usageColumn

        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Tokens.padding.medium
        width: Math.min(Math.max(usageShape.implicitWidth, usageLabel.implicitWidth),
            Math.max(0, root.width - tempProg.width - Tokens.padding.large * 2 - Tokens.spacing.large * 2))
        spacing: Tokens.spacing.extraSmall

        StyledText {
            id: usageLabel

            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere

            // TRANSLATORS: labels the CPU or GPU utilisation percentage shown below it
            text: Tr.trCtx("Usage", "resource usage")
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.body.small
        }

        MaterialShape {
            id: usageShape

            anchors.horizontalCenter: parent.horizontalCenter
            implicitSize: Tokens.sizes.dashboard.perfUsageShapeSize
            color: Colours.palette.m3secondaryContainer
            shape: {
                if (root.usage >= 0.8)
                    return MaterialShape.SoftBurst;
                if (root.usage >= 0.4)
                    return MaterialShape.Sunny;
                return MaterialShape.Cookie4Sided;
            }

            Behavior on color {
                CAnim {}
            }

            StyledText {
                anchors.centerIn: parent
                text: isNaN(root.usage) ? "..." : Strings.percentOne(root.usage)
                color: root.accent
                font: Tokens.font.headline.builders.small.width(50).build()
            }
        }
    }
}
