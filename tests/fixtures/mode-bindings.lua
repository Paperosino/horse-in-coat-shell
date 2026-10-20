local source = assert(io.open(arg[1])):read("*a")
local code = assert(source:match("local mode_bindings = {}.-\nrefresh_mode_bindings%(%)"))
local mode, last = "scrolling", nil
local binds = {}
layouts = {
    mode=function() return mode end,
    toggle_width=function() last={"width"} end,
    step=function(value) last={"workspace",value} end,
    focus=function(value) last={"workspace",value} end,
    focus_column=function(value) last={"column",value} end,
    canvas_action=function(value) last={"canvas",value} end,
}
plugin_action=function(name,value) last={name,value} end
local function action(name) return function(value) return {name,value} end end
hl = {
    unbind=function(key) binds[key]=nil end,
    bind=function(key,callback,options) binds[key]={callback=callback,description=options.description} end,
    dispatch=function(value) last=value end,
    dsp={focus=action("focus"),global=action("global"),window={move=action("move"),resize=action("resize")}},
}
assert(load(code))()
binds["SUPER + H"].callback()
assert(last[1]=="column" and last[2]==-1)
assert(binds["SUPER + H"].description=="Workspaces: Focus column left")
binds["SUPER + CTRL + F"].callback();assert(last[1]=="width")
mode="canvas";refresh_mode_bindings()
binds["SUPER + H"].callback();assert(last[1]=="navigate" and last[2]=="left")
binds["SUPER + SHIFT + Right"].callback();assert(last[2]=="nudge right")
binds["SUPER + CTRL + Down"].callback();assert(last[2]=="pan down")
binds["SUPER + CTRL + Z"].callback();assert(last[2]=="undo")
binds["SUPER + CTRL + SHIFT + Z"].callback();assert(last[2]=="redo")
binds["SUPER + CTRL + SHIFT + Left"].callback();assert(last[1]=="resize" and last[2].x==-32)
assert(binds["SUPER + CTRL + Down"].description=="Canvas: Pan down")
mode="tiling";refresh_mode_bindings()
binds["SUPER + H"].callback();assert(last[1]=="focus" and last[2].direction=="l")
binds["SUPER + SHIFT + J"].callback();assert(last[1]=="move" and last[2].direction=="down")
assert(binds["SUPER + CTRL + Down"].description~="Canvas: Pan down")
binds["SUPER + F1"].callback();assert(last[1]=="global" and last[2]=="hyprstack:shortcutHelp")
