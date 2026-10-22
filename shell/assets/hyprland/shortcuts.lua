-- Keep the original Lua callbacks; never serialize or replay __lua identifiers.
local config_root=(os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME").."/.config")
package.path=package.path..";"..config_root.."/hypr/?.lua"
local json = require("utils.json")
local M = {}
function M.install()
    local config_dir=(os.getenv("XDG_CONFIG_HOME") or os.getenv("HOME").."/.config").."/hics"
    local settings={}
    local f=io.open(config_dir.."/workspace.json","r")
    if f then local ok,data=pcall(json.decode,f:read("*a"));f:close();if ok then settings=data.shortcuts or {} end end
    local bind,submap=hl.bind,hl.define_submap
    local current=""
    local catalogue={}
    local flags={"locked","mouse","release","repeating","long_press","non_consuming","transparent"}
    hl.bind=function(keys,callback,options)
        options=options or {}
        local description=options.description
        if type(description)=="function" then local ok,value=pcall(description);description=ok and value or nil end
        if type(description)~="string" or description=="" then description="Custom: "..keys end
        local labelled={};for k,v in pairs(options) do labelled[k]=v end
        labelled.description=description;options=labelled
        local id=description.."\n"..current
        local entry=catalogue[id] or {id=id,description=description,submap=current,keys={},flags={}}
        if not catalogue[id] then catalogue[id]=entry end
        if not (function() for _,k in ipairs(entry.keys) do if k==keys then return true end end return false end)() then table.insert(entry.keys,keys) end
        for _,flag in ipairs(flags) do if options[flag]~=nil then entry.flags[flag]=options[flag] end end
        local override=(settings.overrides or {})[id]
        if not override then return bind(keys,callback,options) end
        if override.disabled then return end
        local applied={};for k,v in pairs(options) do applied[k]=v end
        for _,flag in ipairs(flags) do if (override.flags or {})[flag]~=nil then applied[flag]=override.flags[flag] end end
        local result
        for _,key in ipairs(override.keys or {}) do
            hl.unbind(key)
            result=bind(key,callback,applied)
        end
        return result
    end
    hl.define_submap=function(name,callback,...)
        return submap(name,function(...)
            local previous=current;current=name
            local result=table.pack(pcall(callback,...));current=previous
            if not result[1] then error(result[2]) end
            return table.unpack(result,2,result.n)
        end,...)
    end
    M.finish=function()
        for _,action in ipairs(settings.custom or {}) do
            if not action.disabled and action.command and action.command~="" then
                local options={description=action.description}
                for _,flag in ipairs(flags) do options[flag]=(action.flags or {})[flag] end
                local install=function() for _,key in ipairs(action.keys or {}) do hl.unbind(key);bind(key,hl.dsp.exec_cmd(action.command),options) end end
                if action.submap and action.submap~="" then submap(action.submap,install) else install() end
            end
        end
        local actions={};for _,entry in pairs(catalogue) do table.insert(actions,entry) end
        local runtime=os.getenv("XDG_RUNTIME_DIR");local signature=os.getenv("HYPRLAND_INSTANCE_SIGNATURE")
        if runtime and signature and signature:match("^[%w_.-]+$") then
            local path=runtime.."/hics-shortcuts-"..signature..".json"
            local out=io.open(path..".tmp","w")
            if out then out:write(json.encode({actions=actions}));out:close();os.rename(path..".tmp",path) end
        end
    end
    hl.on("config.reloaded",function() M.finish() end)
    return M
end
return M
