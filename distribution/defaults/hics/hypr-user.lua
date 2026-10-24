local home = os.getenv("HOME")
local config = os.getenv("XDG_CONFIG_HOME") or home .. "/.config"
local data = os.getenv("XDG_DATA_HOME") or home .. "/.local/share"
local installed = os.getenv("HYPRSTACK_DATA_DIR")
if not installed then
    local marker = data .. "/hics/shell/assets/hyprland/layouts.lua"
    local file = io.open(marker, "r")
    if file then
        file:close()
        installed = data .. "/hics"
    else
        installed = "/usr/share/hics"
    end
end
dofile(installed .. "/shell/assets/hyprland/layouts.lua")
for _, name in ipairs({ "keyboard.lua", "monitors.lua", "system.lua", "rules.lua", "local.lua" }) do
    local path = config .. "/hics/" .. name
    local file = io.open(path)
    if file then file:close(); dofile(path) end
end
