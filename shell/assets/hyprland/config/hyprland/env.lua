local vars = require("variables")

-- Themes
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
hl.env("XCURSOR_THEME", vars.cursorTheme)
hl.env("XCURSOR_SIZE", vars.cursorSize)

-- User appearance choices survive compositor reloads and fresh logins.
local appearance_path = (os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME") .. "/.config") .. "/hyprstack/appearance.json"
local appearance_file = io.open(appearance_path, "r")
if appearance_file then
    local ok, appearance = pcall(require("utils.json").decode, appearance_file:read("*a"))
    appearance_file:close()
    if ok and type(appearance) == "table" then
        if type(appearance.cursors) == "string" then
            hl.env("XCURSOR_THEME", appearance.cursors)
            hl.env("HYPRCURSOR_THEME", appearance.cursors)
            local size = tostring(math.max(16, math.min(96, tonumber(appearance.size) or 24)))
            hl.env("XCURSOR_SIZE", size)
            hl.env("HYPRCURSOR_SIZE", size)
        end
        if appearance.icons then hl.env("QT_QPA_PLATFORMTHEME", "qt5ct:qt6ct") end
        hl.env("GTK2_RC_FILES", (os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME") .. "/.config") .. "/gtk-2.0/gtkrc")
    end
end

-- Toolkit backends
hl.env("GDK_BACKEND", "wayland,x11")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("SDL_VIDEODRIVER", "wayland,x11")
hl.env("CLUTTER_BACKEND", "wayland")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")

-- XDG specifications
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")

-- Others
hl.env("_JAVA_AWT_WM_NONREPARENTING", "1")
