local home = os.getenv("HOME")
local config = os.getenv("XDG_CONFIG_HOME") or home .. "/.config"
local data = os.getenv("XDG_DATA_HOME") or home .. "/.local/share"
local installed = os.getenv("HYPRSTACK_DATA_DIR")
if not installed then
    local marker = data .. "/hyprstack/shell/assets/hyprland/layouts.lua"
    local file = io.open(marker, "r")
    if file then
        file:close()
        installed = data .. "/hyprstack"
    else
        installed = "/usr/share/hyprstack"
    end
end
dofile(installed .. "/shell/assets/hyprland/layouts.lua")
for _, name in ipairs({ "keyboard.lua", "monitors.lua", "system.lua", "local.lua" }) do
    local path = config .. "/hyprstack/" .. name
    local file = io.open(path)
    if file then file:close(); dofile(path) end
end
