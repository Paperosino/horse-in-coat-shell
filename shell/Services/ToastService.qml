pragma Singleton
import Hyprstack
import Quickshell
Singleton {
    function showNotice(title: string, message = ""): void { CUtils.execDetached(["notify-send", "-a", "Hyprstack", title, message]); }
    function showError(title: string, message = ""): void { CUtils.execDetached(["notify-send", "-a", "Hyprstack", "-u", "critical", title, message]); }
    function showWarning(title: string, message = ""): void { showNotice(title, message); }
}
