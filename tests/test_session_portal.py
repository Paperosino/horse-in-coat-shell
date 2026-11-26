"""Portal owners follow compositor generations without disturbing matching sessions."""
import importlib.util, os, subprocess, unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('session_portal',Path(__file__).resolve().parents[1]/'shell/assets/session_portal.py')
portal=importlib.util.module_from_spec(spec);spec.loader.exec_module(portal)
BACKEND='xdg-desktop-portal-hyprland.service'
FRONTEND='xdg-desktop-portal.service'
ENV={'XDG_CURRENT_DESKTOP':'HICS:Hyprland','WAYLAND_DISPLAY':'wayland-1','HYPRLAND_INSTANCE_SIGNATURE':'new'}
MATCH=b'XDG_CURRENT_DESKTOP=HICS:Hyprland\0WAYLAND_DISPLAY=wayland-1\0HYPRLAND_INSTANCE_SIGNATURE=new\0'

class SessionPortal(unittest.TestCase):
    def invoke(self,states=None,environment=MATCH,monitors='[{"width":1280}]'):
        states=states or {}
        def command(args,**kwargs):
            if args[0]=='hyprctl':return subprocess.CompletedProcess(args,0,monitors)
            if args[2]=='show':return subprocess.CompletedProcess(args,0,states.get(args[3],'MainPID=0\nActiveState=inactive\n'))
            return subprocess.CompletedProcess(args,0,'')
        with patch.dict(os.environ,ENV),patch.object(portal.subprocess,'run',side_effect=command) as run,patch.object(portal.Path,'read_bytes',return_value=environment):
            portal.refresh();return [c.args[0] for c in run.call_args_list]
    def test_failed_backend_recovers_after_readiness_and_rate_limit_reset(self):
        calls=self.invoke({BACKEND:'MainPID=0\nActiveState=failed\n'})
        self.assertLess(calls.index(['hyprctl','-j','monitors']),calls.index(['systemctl','--user','reset-failed',BACKEND]))
        self.assertLess(calls.index(['systemctl','--user','reset-failed',BACKEND]),calls.index(['systemctl','--user','restart',BACKEND]))
    def test_reused_wayland_name_still_detects_previous_generation(self):
        calls=self.invoke({BACKEND:'MainPID=123\nActiveState=active\n'},MATCH.replace(b'=new',b'=old'))
        self.assertIn(['systemctl','--user','try-restart',BACKEND],calls)
    def test_matching_owners_keep_requests(self):
        calls=self.invoke({unit:'MainPID=123\nActiveState=active\n' for unit in (BACKEND,FRONTEND)})
        self.assertEqual(len(calls),2)
    def test_inactive_portals_remain_lazy(self):self.assertEqual(len(self.invoke()),2)
    def test_stale_frontend_identity_is_replaced(self):
        calls=self.invoke({FRONTEND:'MainPID=123\nActiveState=active\n'},MATCH.replace(b'HICS:Hyprland',b'Hyprland'))
        self.assertIn(['systemctl','--user','try-restart',FRONTEND],calls)
    def test_no_output_does_not_start_backend(self):
        with self.assertRaisesRegex(RuntimeError,'outputs are ready'):
            self.invoke({BACKEND:'MainPID=0\nActiveState=failed\n'},monitors='[]')
    def test_disappearing_owner_is_not_an_error(self):
        with patch.dict(os.environ,ENV),patch.object(portal.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'MainPID=123\nActiveState=active')) as run,patch.object(portal.Path,'read_bytes',side_effect=FileNotFoundError):
            portal.refresh();self.assertEqual(run.call_count,2)
