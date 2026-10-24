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

        Exclusions {
            screen: scope.modelData
            bar: content.bar
        }

        ContentWindow {
            id: content

            screen: scope.modelData
        }
        Variants {
            model:ExtraPanels.onScreen(scope.modelData.name).map(p=>p.id)
            Scope {
                id:extra
                required property string modelData
                readonly property var spec:ExtraPanels.panels.find(p=>p.id===modelData)??({id:modelData,edge:"top",thickness:48,autoHide:true,hideDelay:500})
                ExtraPanel {
                    spec:extra.spec
                    screen:scope.modelData
                    edgeOffset:(spec.edge==="top"?content.bar.topInset:content.bar.bottomInset)+ExtraPanels.before(spec.id)
                }
                StyledWindow {
                    name:"panel-exclusion-"+extra.modelData
                    screen:scope.modelData
                    anchors.left:true;anchors.right:true
                    anchors.top:extra.spec?.edge==="top"
                    anchors.bottom:extra.spec?.edge==="bottom"
                    implicitHeight:(extra.spec?.thickness??48)*Tokens.scale
                    exclusiveZone:extra.spec && !extra.spec.autoHide && !content.hasFullscreen?extra.spec.thickness*Tokens.scale:0
                    mask:Region {}
                }
            }
        }

    }
}
