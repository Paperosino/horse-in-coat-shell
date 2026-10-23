import Hyprstack.I18n
import qs.modules.nexus.pages.apps

// The sidebar already exposes defaults, autostart and extensions. This page is
// the library itself; legacy subpage indices remain available for saved links.
AllApps {
    title:Tr.tr("Apps")
    pageIcon:"apps"
    isSubPage:nState.subPageIdxStack.length>0
}
