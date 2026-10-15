-- Application choices, appearance and key bindings. See CONFIGURATION.md.
return {
    terminal = "kitty",
    browser = "firefox",
    editor = "xdg-open",
    fileExplorer = 'xdg-open "$HOME"',
    audioSettings = "pavucontrol",
    cursorTheme = "Adwaita",
    blurEnabled = false,
    windowOpacity = 1,
    kbLock = "CTRL + SUPER + L",
    kbShowPanels = "SUPER + ALT + K",
    sleepGestureCmd = "systemctl suspend",
}
