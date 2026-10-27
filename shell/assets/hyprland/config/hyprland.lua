local home   = os.getenv("HOME")
local config = os.getenv("XDG_CONFIG_HOME") or home .. "/.config"
local hypr = os.getenv("HICS_HYPR_CONFIG_DIR") or config .. "/hypr"
local shipped = (os.getenv("HICS_DATA_DIR") or os.getenv("HYPRSTACK_DATA_DIR") or "/usr/share/hics") .. "/shell/assets/hyprland/config"
package.path = package.path .. ";" .. hypr .. "/?.lua;" .. shipped .. "/?.lua;" .. config .. "/hics/?.lua"

-- Create a file if it doesn't exist, optionally with initial content
local function maybe_create(file, content)
    local f = io.open(file)

    if f then
        f:close()
        return
    end

    f = io.open(file, "w")
    if f then
        if content then f:write(content) end
        f:close()
    end
end

-- Copy src to dst, but only if dst doesn't already exist
local function maybe_copy(src, dst)
    local out = io.open(dst)
    if out then
        out:close()
        return
    end

    local input = io.open(src, "r") or io.open(shipped .. "/scheme/default.lua", "r")
    if not input then return end

    out = io.open(dst, "w")
    if out then
        out:write(input:read("*a"))
        out:close()
    end
    input:close()
end

-- Maybe set current colours to defaults
maybe_copy(hypr .. "/scheme/default.lua", hypr .. "/scheme/current.lua")

-- User variables
maybe_create(config .. "/hics/hypr-vars.lua", "return {}\n")
local overrides = require("hypr-vars")
if type(overrides) == "table" then
    local vars = require("variables")
    for k, v in pairs(overrides) do
        vars[k] = v
    end
end

-- Let Hyprland choose the mode, position and scale for each connected output.
hl.monitor({
    output   = "",
    mode     = "preferred",
    position = "auto",
    scale    = "auto",
})

-- hics-shortcut-editor: preserve Lua callbacks for graphical editing
local shortcuts_root=os.getenv("HICS_DATA_DIR") or os.getenv("HYPRSTACK_DATA_DIR") or "/usr/share/hics"
local shortcuts_path=shortcuts_root.."/shell/assets/hyprland/shortcuts.lua"
local shortcuts_file=io.open(shortcuts_path,"r")
if shortcuts_file then shortcuts_file:close();hics_shortcuts=dofile(shortcuts_path).install() end

-- Configs
require("hyprland.env")
require("hyprland.general")
require("hyprland.input")
require("hyprland.misc")
require("hyprland.animations")
require("hyprland.decoration")
require("hyprland.group")
require("hyprland.execs")
require("hyprland.rules")
require("hyprland.gestures")
require("hyprland.keybinds")

-- User configs
maybe_create(config .. "/hics/hypr-user.lua")
require("hypr-user")
