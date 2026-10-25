import Hyprstack.I18n
import qs.modules.nexus.pages.apps

// The Applications overview owns defaults, startup and extensions.
// Legacy detail indices stay available for search and saved links.
AllApps {
    title:Tr.tr("Apps")
    pageIcon:"apps"
    isSubPage:nState.subPageIdxStack.length>0
}
