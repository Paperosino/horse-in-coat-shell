"""QMP can retain stale device axes after the compositor warps its cursor."""
import json
from pathlib import Path
import shlex
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import vm_guest_pointer as pointer


class GuestPointerTests(unittest.TestCase):
    def setup_guest(self, *, hostname='hics-test', locked=False, warp_after_move=False):
        state = {'device':[640,150],'cursor':[640,425],'presses':[]}
        def remote(command, **kwargs):
            args = shlex.split(command[-1])
            if args[:2]==['cat','/etc/hostname']:return hostname+'\n'
            if args==['systemd-detect-virt']:return 'kvm\n'
            if 'monitors' in args:return json.dumps([{'width':1280,'height':800,'scale':1,'transform':0,'x':0,'y':0}])
            if 'locked' in args:return json.dumps({'locked':locked})
            if 'cursorpos' in args:
                if warp_after_move and state['device']!=[640,150]:state['cursor']=[640,425]
                # The second read may observe another compositor warp.
                if warp_after_move:state['cursor']=[640,425]
                return json.dumps(dict(zip(('x','y'),state['cursor'])))
            raise AssertionError(args)
        def qmp(lab,execute,arguments=None):
            if execute=='query-status':return {'running':True}
            for event in arguments['events']:
                data=event['data']
                if event['type']=='abs':
                    index=0 if data['axis']=='x' else 1
                    value=round(data['value']*(1280 if index==0 else 800)/32767)
                    # Emulate QEMU's unchanged-device-axis suppression.
                    if state['device'][index]!=value:
                        state['device'][index]=value;state['cursor'][index]=value
                else:
                    state['presses'].append((data['down'],tuple(state['cursor'])))
        return state,remote,qmp

    def test_corrects_stale_device_position_before_click(self):
        state,remote,qmp=self.setup_guest()
        with patch.object(pointer.subprocess,'check_output',side_effect=remote), \
             patch.object(pointer,'qmp',side_effect=qmp),patch.object(pointer.time,'sleep'):
            result=pointer.click_guest(Path('/test/lab'),640,150)
        self.assertEqual(result['verifiedPositionBeforePress'],{'x':640,'y':150})
        self.assertEqual(state['presses'],[(True,(640,150)),(False,(640,150))])

    def test_refuses_to_press_after_another_compositor_warp(self):
        state,remote,qmp=self.setup_guest(warp_after_move=True)
        with patch.object(pointer.subprocess,'check_output',side_effect=remote), \
             patch.object(pointer,'qmp',side_effect=qmp),patch.object(pointer.time,'sleep'):
            with self.assertRaises(AssertionError):pointer.click_guest(Path('/test/lab'),640,150)
        self.assertEqual(state['presses'],[])

    def test_refuses_host_and_locked_session_before_sending_input(self):
        for options in ({'hostname':'workstation'},{'locked':True}):
            with self.subTest(options=options):
                state,remote,qmp=self.setup_guest(**options)
                with patch.object(pointer.subprocess,'check_output',side_effect=remote), \
                     patch.object(pointer,'qmp',side_effect=qmp),patch.object(pointer.time,'sleep'):
                    with self.assertRaises(AssertionError):pointer.click_guest(Path('/test/lab'),640,150)
                self.assertEqual(state['presses'],[])
