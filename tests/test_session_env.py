"""The managed Hyprland environment preserves the hics portal identity."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'shell/assets/hyprland/config/hyprland/env.lua'
LUA='''
package.preload["variables"]=function() return {cursorTheme="fixture",cursorSize="24"} end
local values={}
hl={env=function(name,value) values[name]=value end}
dofile(arg[0])
print(values.XDG_CURRENT_DESKTOP)
print(values.XDG_SESSION_DESKTOP)
print(values.XDG_SESSION_TYPE)
'''

class SessionEnvironment(unittest.TestCase):
    def check_session(self,session,desktop):
        with tempfile.TemporaryDirectory(prefix='hics-env-test-') as directory:
            env=dict(os.environ,HOME=directory,XDG_CONFIG_HOME=directory,XDG_SESSION_DESKTOP=session)
            result=subprocess.check_output(['lua','-e',LUA,str(SCRIPT)],env=env,text=True)
            self.assertEqual(result.splitlines()[:3],[desktop,session,'wayland'])
    def test_hics_identity_is_preserved(self):self.check_session('hics','HICS:Hyprland')
    def test_other_hyprland_identity_is_preserved(self):self.check_session('Hyprland','Hyprland')

if __name__=='__main__':unittest.main()
