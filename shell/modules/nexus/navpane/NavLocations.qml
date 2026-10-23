pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Hyprstack.Config
import qs.components
import qs.components.containers
import qs.services
import qs.modules.nexus

VerticalFadeFlickable {
    id: root

    required property NexusState nState

    function revealCurrent(): void {
        const index=PageRegistry.navigationPages.findIndex(p=>p.pageIndex===nState.currentPageIdx);
        const row=list.itemAt(index);
        if(!row || height<=0)return;
        const y=row.mapToItem(contentItem,0,0).y;
        let target=contentY;
        if(y<contentY+topMargin)target=y-topMargin;
        else if(y+row.height>contentY+height-bottomMargin)target=y+row.height-height+bottomMargin;
        cancelFlick();scrollTo.stop();
        scrollTo.to=Math.max(-topMargin,Math.min(Math.max(-topMargin,contentHeight-height+bottomMargin),target));
        scrollTo.restart();
    }
    Component.onCompleted:Qt.callLater(revealCurrent)
    Connections {target:root.nState;function onCurrentPageIdxChanged():void {Qt.callLater(root.revealCurrent);}}
    Anim {id:scrollTo;target:root;property:"contentY";type:Anim.FastEffects}

    fadeAmount:Math.min(0.08,16*Tokens.scale/Math.max(1,height))

    topMargin: Tokens.padding.large
    bottomMargin: Tokens.padding.large
    contentHeight: content.implicitHeight

    TapHandler {
        onTapped: root.focus = true
    }

    ColumnLayout {
        id: content

        anchors.left: parent.left
        anchors.right: parent.right
        spacing: Tokens.spacing.extraSmall

        Repeater {
            id: list

            model: PageRegistry.navigationPages

            StyledRect {
                id: item

                required property var modelData
                required property int index

                readonly property bool isCurrentPage: modelData.pageIndex === root.nState.currentPageIdx
                readonly property bool isCategoryStart: index === 0 || PageRegistry.navigationPages[index - 1].category !== modelData.category
                readonly property bool isCategoryEnd: index === list.model.length - 1 || PageRegistry.navigationPages[index + 1].category !== modelData.category

                Layout.fillWidth: true
                Layout.topMargin: isCategoryStart ? groupTitle.implicitHeight + Tokens.spacing.medium * 2 : 0
                implicitHeight: {
                    const h = layout.implicitHeight + layout.anchors.margins * 2;
                    return h % 2 === 0 ? h : h + 1;
                }

                scale: stateLayer.pressed ? 0.98 : 1
                Behavior on scale {
                    Anim {
                        type: Anim.FastSpatial
                    }
                }
                color: isCurrentPage ? Colours.palette.m3secondaryContainer : Colours.layer(Colours.palette.m3surfaceContainerHigh, 2)

                topLeftRadius: stateLayer.pressed ? Tokens.rounding.medium : isCurrentPage ? Tokens.rounding.extraLargeIncreased : isCategoryStart ? Tokens.rounding.extraLarge : Tokens.rounding.extraSmall
                topRightRadius: stateLayer.pressed ? Tokens.rounding.medium : isCurrentPage ? Tokens.rounding.extraLargeIncreased : isCategoryStart ? Tokens.rounding.extraLarge : Tokens.rounding.extraSmall
                bottomLeftRadius: stateLayer.pressed ? Tokens.rounding.medium : isCurrentPage ? Tokens.rounding.extraLargeIncreased : isCategoryEnd ? Tokens.rounding.extraLarge : Tokens.rounding.extraSmall
                bottomRightRadius: stateLayer.pressed ? Tokens.rounding.medium : isCurrentPage ? Tokens.rounding.extraLargeIncreased : isCategoryEnd ? Tokens.rounding.extraLarge : Tokens.rounding.extraSmall

                RadiusBehavior on topLeftRadius {}
                RadiusBehavior on topRightRadius {}
                RadiusBehavior on bottomLeftRadius {}
                RadiusBehavior on bottomRightRadius {}

                StyledText {
                    id: groupTitle
                    visible: item.isCategoryStart
                    anchors.left: parent.left
                    anchors.bottom: parent.top
                    anchors.bottomMargin: Tokens.spacing.small
                    text: PageRegistry.categoryLabel(item.modelData.category)
                    font: Tokens.font.label.medium
                    color: Colours.palette.m3onSurfaceVariant
                }

                StateLayer {
                    id: stateLayer

                    anchors.fill: parent
                    topLeftRadius: parent.topLeftRadius
                    topRightRadius: parent.topRightRadius
                    bottomLeftRadius: parent.bottomLeftRadius
                    bottomRightRadius: parent.bottomRightRadius

                    keyboardFocusable:true
                    Accessible.name:item.modelData.label
                    Accessible.description:item.modelData.description
                    Accessible.role:Accessible.PageTab
                    Accessible.selected:item.isCurrentPage
                    onClicked: root.nState.currentPageIdx = item.modelData.pageIndex
                }

                RowLayout {
                    id: layout

                    anchors.fill: parent
                    anchors.margins: Tokens.padding.medium
                    spacing: Tokens.spacing.medium

                    StyledRect {
                        Layout.alignment: Qt.AlignVCenter
                        implicitWidth: 32 * Tokens.scale
                        implicitHeight: implicitWidth

                        radius: Tokens.rounding.full
                        color: item.isCurrentPage ? Colours.palette.m3primary : Colours.palette.m3secondaryContainer

                        MaterialIcon {
                            anchors.centerIn: parent
                            anchors.verticalCenterOffset: 1

                            text: item.modelData.icon
                            color: item.isCurrentPage ? Colours.palette.m3onPrimary : Colours.palette.m3onSecondaryContainer
                            fontStyle: Tokens.font.icon.builders.medium.weight(Font.Medium).build()
                            grade: 25
                            fill: item.modelData.noFill ? 0 : 1
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: 0

                        StyledText {
                            Layout.fillWidth: true
                            text: item.modelData.label
                            font: Tokens.font.body.small
                            Layout.minimumWidth: 0
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        }

                        StyledText {
                            Layout.fillWidth: true
                            visible: item.isCurrentPage
                            maximumLineCount:2
                            elide:Text.ElideRight
                            text: item.modelData.description
                            color: Colours.palette.m3onSurfaceVariant
                            font: Tokens.font.label.small
                            Layout.minimumWidth: 0
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        }
                    }
                }
            }
        }
    }

    component RadiusBehavior: Behavior {
        Anim {
            type: Anim.DefaultEffects
        }
    }
}
