pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import qs.services
import qs.modules.bar
import qs.components.containers
import Quickshell.Wayland
import Hyprstack.Config

Variants {
    model: Onboarding.running?[]:Screens.screens

    Scope {
        id: scope

        required property ShellScreen modelData

        readonly property var state: ShellState.forScreen(modelData)
        property bool requested: false
        Binding { target: scope; property: "requested"; value: scope.state.sidebar || scope.state.launcher || scope.state.dashboard || scope.state.session || scope.state.clipboard || scope.state.osd || Overview.active; delayed: true }
        // Destroy the inactive window tree rather than reparenting texture
        // providers between backing QQuickWindows on hide/show.
        Loader {
            id: contentLoader
            active: !GameMode.quietOn(scope.modelData) || scope.requested
            sourceComponent: Scope {
                property alias window: content
                ContentWindow { id: content; targetScreen: scope.modelData }
                Exclusions { screen: scope.modelData; bar: content.bar }
            }
        }
        Variants {
            model:GameMode.quietOn(scope.modelData)?[]:ExtraPanels.onScreen(scope.modelData.name).map(p=>p.id)
            Scope {
                id:extra
                required property string modelData
                readonly property var spec:ExtraPanels.panels.find(p=>p.id===modelData)??({id:modelData,edge:"top",thickness:48,autoHide:true,hideDelay:500})
                ExtraPanel {
                    spec:extra.spec
                    screen:scope.modelData
                    edgeOffset:(spec.edge==="top"?(contentLoader.item?.window.bar.topInset??0):(contentLoader.item?.window.bar.bottomInset??0))+ExtraPanels.before(spec.id)
                }
                StyledWindow {
                    visible:!GameMode.quietOn(scope.modelData)
                    name:"panel-exclusion-"+extra.modelData
                    screen:scope.modelData
                    anchors.left:true;anchors.right:true
                    anchors.top:extra.spec?.edge==="top"
                    anchors.bottom:extra.spec?.edge==="bottom"
                    implicitHeight:(extra.spec?.thickness??48)*Tokens.scale
                    exclusiveZone:extra.spec && !extra.spec.autoHide && !GameMode.quietOn(scope.modelData)?extra.spec.thickness*Tokens.scale:0
                    mask:Region {}
                }
            }
        }

    }
}
