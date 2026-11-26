"""Portal startup replaces stale desktop identity without restarting matching owners."""
import importlib.util, os, subprocess, unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('session_portal',Path(__file__).resolve().parents[1]/'shell/assets/session_portal.py')
portal=importlib.util.module_from_spec(spec);spec.loader.exec_module(portal)

class SessionPortal(unittest.TestCase):
    def run_refresh(self,pid,environment):
        with patch.dict(os.environ,{'XDG_CURRENT_DESKTOP':'HICS:Hyprland'}), patch.object(portal.subprocess,'run',return_value=subprocess.CompletedProcess([],0,str(pid))) as run, patch.object(portal.Path,'read_bytes',return_value=environment) as read:
            portal.refresh();return run.call_args_list,read.call_count
    def test_surviving_hyprland_portal_is_restarted(self):
        calls,reads=self.run_refresh(123,b'XDG_CURRENT_DESKTOP=Hyprland\0')
        self.assertEqual(reads,1);self.assertEqual(calls[-1].args[0],['systemctl','--user','try-restart','xdg-desktop-portal.service'])
    def test_matching_owner_keeps_requests(self):
        calls,_=self.run_refresh(123,b'XDG_CURRENT_DESKTOP=HICS:Hyprland\0');self.assertEqual(len(calls),1)
    def test_inactive_portal_remains_lazy(self):
        calls,reads=self.run_refresh(0,b'');self.assertEqual(len(calls),1);self.assertEqual(reads,0)
    def test_disappearing_owner_is_not_an_error(self):
        with patch.dict(os.environ,{'XDG_CURRENT_DESKTOP':'HICS:Hyprland'}),patch.object(portal.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'123')) as run,patch.object(portal.Path,'read_bytes',side_effect=FileNotFoundError):
            portal.refresh();self.assertEqual(run.call_count,1)
