import QtQuick
import QtQuick.Controls
import Hyprstack.Config
import qs.components
import qs.modules.nexus

StackView {
    id: root

    required property NexusState nState
    default property list<Component> pages
    property int ownerPageIdx: -1
    readonly property int animMovement: 12 * Tokens.scale

    function openSubPage(idx: int, immediate: bool): void {
        const page = pages[idx];
        if (page) {
            push(page, {
                nState
            }, immediate ? StackView.Immediate : StackView.PushTransition);
        } else {
            console.warn(logCat, "Attempted to open invalid sub-page index", idx);
            nState.closeSubPage();
        }
    }

    clip: busy

    Component.onCompleted: {
        ownerPageIdx = nState.currentPageIdx;
        openSubPage(0, true);
        for (const page of nState.subPageIdxStack)
            openSubPage(page, true);
    }

    pushEnter: Transition {
        SequentialAnimation {
            PropertyAction {
                property: "opacity"
                value: 0
            }
            PauseAnimation {
                duration: 0
            }
            ParallelAnimation {
                Anim {
                    property: "opacity"
                    to: 1
                    type: Anim.FastSpatial
                }
                Anim {
                    property: "x"
                    from: root.animMovement
                    to: 0
                    type: Anim.FastSpatial
                }
            }
        }
    }

    pushExit: Transition {
        Anim {
            property: "opacity"
            to: 0
            type: Anim.DefaultEffects
        }
    }

    popEnter: Transition {
        SequentialAnimation {
            PropertyAction {
                property: "opacity"
                value: 0
            }
            PauseAnimation {
                duration: 0
            }
            ParallelAnimation {
                Anim {
                    property: "opacity"
                    to: 1
                    type: Anim.FastSpatial
                }
                Anim {
                    property: "x"
                    from: -root.animMovement
                    to: 0
                    type: Anim.FastSpatial
                }
            }
        }
    }

    popExit: Transition {
        Anim {
            property: "opacity"
            to: 0
            type: Anim.DefaultEffects
        }
    }

    LoggingCategory {
        id: logCat

        name: "hyprstack.nexus"
        defaultLogLevel: LoggingCategory.Info
    }

    Connections {
        enabled: !root.nState.showingSection && root.ownerPageIdx === root.nState.currentPageIdx
        function onSubPageOpened(idx: int): void {
            root.openSubPage(idx, false);
        }

        function onSubPageClosed(): void {
            if (root.depth < root.nState.subPageIdxStack.length) {
                console.log(logCat, "Attempted to close page while depth < stack depth. Ignoring.");
                return;
            }
            if (root.depth > 1)
                root.pop();
        }

        target: root.nState
    }
}
