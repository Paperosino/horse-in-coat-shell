import Quickshell
import qs.services

// The singleton controls the compositor scene without an overview surface,
// replica windows, captions, toolbars or a keyboard-focus grab.
Scope {
    readonly property var controller: Overview
}
