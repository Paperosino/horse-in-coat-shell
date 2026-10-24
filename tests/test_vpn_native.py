"""Exercise native libnm profiles and typed D-Bus requests on a private bus."""
import json,os,shlex,subprocess,tempfile,unittest,signal
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SERVICES=ROOT/'shell/plugin/src/Hyprstack/Services'
class VpnNativeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='hics-vpn-test-');cls.base=Path(cls.temp.name);cls.binary=cls.base/'probe'
  flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Qml','Qt6Concurrent','Qt6DBus','libnm','libsecret-1'],text=True))
  moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
  subprocess.run([str(moc),str(SERVICES/'networkmanagervpn.hpp'),'-o',str(cls.base/'moc.cpp'),*shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6Qml'],text=True))],check=True)
  subprocess.run([str(moc),str(SERVICES/'vpnsecretagent.hpp'),'-o',str(cls.base/'agent-moc.cpp'),*shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6Qml'],text=True))],check=True)
  qrc=cls.base/'vpn.qrc';qrc.write_text('<RCC><qresource prefix="/hics/vpn"><file alias="vpn-protocols.json">'+str(SERVICES/'vpn-protocols.json')+'</file></qresource></RCC>')
  rcc=moc.with_name('rcc');subprocess.run([str(rcc),str(qrc),'-o',str(cls.base/'rcc.cpp')],check=True)
  # Every package-manager path is redirected in this test-only source copy;
  # even a regression in the launcher must never invoke a real root installer.
  for name in ('fake-pacman','pkexec'):
   tool=cls.base/name;tool.write_text('#!/bin/sh\nexit 91\n');tool.chmod(0o700)
  native=cls.base/'networkmanagervpn-test.cpp'
  native.write_text((SERVICES/'networkmanagervpn.cpp').read_text().replace('/usr/bin/pacman',str(cls.base/'fake-pacman')).replace('/usr/bin/pkexec',str(cls.base/'pkexec')))
  subprocess.run(['c++','-std=c++20','-fPIC',str(ROOT/'tests/fixtures/vpn-probe.cpp'),str(native),str(cls.base/'moc.cpp'),str(SERVICES/'vpnsecretagent.cpp'),str(cls.base/'agent-moc.cpp'),str(cls.base/'rcc.cpp'),'-I',str(SERVICES),*flags,'-o',str(cls.binary)],check=True)
  cls.bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True)
  cls.env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=cls.bus.stdout.readline().strip(),VPN_TEST_LOG=str(cls.base/'calls.jsonl'))
  cls.env['DBUS_SESSION_BUS_ADDRESS']=cls.env['DBUS_SYSTEM_BUS_ADDRESS']
  cls.mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_vpn_bus.py')],env=cls.env,stdout=subprocess.PIPE,text=True)
  if cls.mock.stdout.readline().strip()!='ready':raise RuntimeError('VPN fixture did not start')
 @classmethod
 def tearDownClass(cls):
  cls.mock.terminate();cls.mock.wait();cls.bus.terminate();cls.bus.wait();cls.temp.cleanup()
 def run_probe(self,*args):
  Path(self.env['VPN_TEST_LOG']).write_text('')
  result=subprocess.run([str(self.binary),*args],env=self.env,capture_output=True,text=True,timeout=20)
  self.assertEqual(result.returncode,0,result.stderr)
  parsed=json.loads(result.stdout)
  if parsed.get('errorName','').endswith('.NoReply'):raise AssertionError(result.stderr)
  return parsed
 def calls(self):return [json.loads(line) for line in Path(self.env['VPN_TEST_LOG']).read_text().splitlines()]
 def test_dynamic_plugin_catalog_and_only_vpn_profiles(self):
  result=self.run_probe('list');self.assertEqual(result['error'],'');self.assertTrue(any(p['service']=='wireguard' and p['installed'] for p in result['plugins']));self.assertTrue(all(p['type']!='802-3-ethernet' for p in result['profiles']))
 def test_vanished_active_object_does_not_break_saved_profiles(self):
  for mode in ('vanished','unknown-object'):
   with self.subTest(mode=mode):
    result=self.run_probe('snapshot-'+mode)
    self.assertEqual(result['error'],'')
    self.assertTrue(result['profiles'])
    self.assertTrue(any(p['active'] and p['state']==2 for p in result['profiles']))
 def test_active_object_permission_error_is_not_ignored(self):
  result=self.run_probe('snapshot-active-denied')
  self.assertIn('Active state access denied',result['error'])
 def test_successful_refresh_clears_only_the_previous_read_error(self):
  result=self.run_probe('snapshot-root-denied')
  self.assertIn('Network state access denied',result['before'])
  self.assertEqual(result['error'],'')
  self.assertTrue(result['profiles'])
 def test_background_refresh_preserves_a_real_operation_failure(self):
  result=self.run_probe('snapshot-operation-error')
  self.assertIn('Permission denied',result['before'])
  self.assertEqual(result['before'],result['during'])
  self.assertEqual(result['before'],result['error'])
 def test_edit_preserves_password_unknown_plugin_data_and_route_attributes(self):
  self.assertEqual(self.run_probe('edit')['error'],'');update=next(c['data'] for c in self.calls() if c['method']=='Update2')
  self.assertEqual(update['vpn']['data']['vendor-option'],'keep-me');self.assertEqual(update['vpn']['secrets']['password'],'stored-password');self.assertEqual(update['ipv4']['route-data'][0]['table'],123);self.assertEqual(update['ipv4']['dns-priority'],-50)
 def test_new_pptp_is_a_networkmanager_connection(self):
  self.assertEqual(self.run_probe('create')['error'],'');data=next(c['data'] for c in self.calls() if c['method']=='AddConnection2');self.assertEqual(data['vpn']['service-type'],'org.freedesktop.NetworkManager.pptp');self.assertEqual(data['vpn']['secrets']['password'],'test-password')
 def test_wireguard_peers_dns_and_private_key(self):
  self.assertEqual(self.run_probe('wireguard')['error'],'');data=next(c['data'] for c in self.calls() if c['method']=='AddConnection2');self.assertIn('private-key',data['wireguard']);self.assertEqual(data['wireguard']['peers'][0]['persistent-keepalive'],25)
 def test_invalid_dns_is_rejected_before_any_bus_mutation(self):
  self.assertTrue(self.run_probe('invalid-dns').get('error'));self.assertEqual(self.calls(),[])
 def test_invalid_route_is_rejected_before_any_bus_mutation(self):
  self.assertTrue(self.run_probe('invalid-route').get('error'));self.assertEqual(self.calls(),[])
 def test_wireguard_import_is_an_unsaved_draft(self):
  import base64
  source=self.base/'wg-fixture.conf';source.write_text('[Interface]\nPrivateKey = '+base64.b64encode(b'a'*32).decode()+'\nAddress = 10.3.0.2/32\nDNS = 9.9.9.9\n\n[Peer]\nPublicKey = '+base64.b64encode(b'b'*32).decode()+'\nAllowedIPs = 0.0.0.0/0\nEndpoint = vpn.example:51820\n')
  result=self.run_probe('import','wireguard',str(source));self.assertEqual(result['error'],'');self.assertEqual(result['draft']['type'],'wireguard');self.assertEqual(result['draft']['secrets']['private-key'],base64.b64encode(b'a'*32).decode());self.assertEqual(self.calls(),[])

 def test_secret_agent_requires_trusted_networkmanager_sender(self):
  result=self.run_probe('agent-untrusted');self.assertEqual(result['errorName'],'org.freedesktop.DBus.Error.AccessDenied')
 def test_secret_agent_noninteractive_request_does_not_show_a_prompt(self):
  result=self.run_probe('agent-no-interaction');self.assertTrue(result['errorName'].endswith('.NoSecrets'))
 def test_secret_agent_responds_and_cancels_interactive_requests(self):
  result=self.run_probe('agent-submit');self.assertEqual(result.get('password'),'agent-fixture')
  result=self.run_probe('agent-cancel');self.assertTrue(result['errorName'].endswith('.UserCanceled'))
 def test_profile_export_is_private_and_preserves_secrets(self):
  target=self.base/'export.nmconnection';result=self.run_probe('export',str(target));self.assertEqual(result['error'],'');self.assertEqual(target.stat().st_mode&0o777,0o600);self.assertIn('stored-password',target.read_text())

 @unittest.skipUnless(Path('/usr/lib/nm-pptp-auth-dialog').exists(), 'PPTP auth helper is not installed')
 def test_plugin_external_ui_is_rendered_by_the_native_agent(self):
  result=self.run_probe('agent-plugin-submit');self.assertEqual(result.get('password'),'agent-fixture',result)

 def test_missing_stored_secrets_does_not_block_saving_a_new_password(self):
  self.assertEqual(self.run_probe('edit-no-secrets')['error'],'')
  update=next(c['data'] for c in self.calls() if c['method']=='Update2')
  self.assertEqual(update['vpn']['secrets']['xauthpassword'],'new-fixture-password')
  self.assertEqual(update['vpn']['data']['vendor-option'],'keep-me')
 def test_profile_without_secrets_can_save_dns_and_keep_secret_flags(self):
  self.assertEqual(self.run_probe('edit-empty-secrets')['error'],'')
  update=next(c['data'] for c in self.calls() if c['method']=='Update2')
  self.assertEqual(update['ipv4']['dns-priority'],-50)
  self.assertEqual(update['vpn']['data']['pskvalue-flags'],'0')
 def test_secret_permission_errors_still_prevent_destructive_updates(self):
  self.assertTrue(self.run_probe('edit-denied')['error'])
  self.assertFalse(any(c['method']=='Update2' for c in self.calls()))

 def test_secret_agent_returns_system_credentials_for_noninteractive_editor_reads(self):
  result=self.run_probe('agent-existing-secrets');self.assertEqual(result.get('password'),'system-fixture-password',result)

 def test_editor_loads_saved_credentials_for_masked_password_fields(self):
  result=self.run_probe('draft');self.assertEqual(result['error'],'');self.assertEqual(result['draft']['secrets']['password'],'stored-password')
 def test_libreswan_activation_starts_its_ipsec_service_first(self):
  result=self.run_probe('activate-libreswan');self.assertEqual(result['error'],'')
  calls=self.calls();start=next(i for i,c in enumerate(calls) if c['method']=='StartUnit');activate=next(i for i,c in enumerate(calls) if c['method']=='ActivateConnection')
  self.assertLess(start,activate);self.assertEqual(calls[start]['data'],'ipsec.service')
 def test_libreswan_waits_for_signal_without_polling(self):
  result=self.run_probe('activate-libreswan-delayed');self.assertEqual(result['error'],'')
  calls=self.calls();self.assertLessEqual(sum(c['method']=='IpsecState' for c in calls),2);self.assertTrue(any(c['method']=='ActivateConnection' for c in calls))
 def test_libreswan_failure_does_not_activate_profile(self):
  result=self.run_probe('activate-libreswan-failed');self.assertIn('failed to start',result['error']);self.assertFalse(any(c['method']=='ActivateConnection' for c in self.calls()))
 def test_libreswan_start_can_be_cancelled(self):
  result=self.run_probe('activate-libreswan-cancel');self.assertTrue(result['error']);self.assertFalse(any(c['method']=='ActivateConnection' for c in self.calls()))
 def test_shutdown_stops_only_installer_waiter_and_preserves_transaction(self):
  with tempfile.TemporaryDirectory(dir=self.base) as directory:
   base=Path(directory);marker=base/'service.pid';worker=base/'installer-worker.py'
   worker.write_text('import time\ntime.sleep(30)\n')
   runner=base/'systemd-run';runner.write_text('#!/usr/bin/python3\nimport subprocess,sys,pathlib,time,json\np=subprocess.Popen([sys.executable,'+repr(str(worker))+'],start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\npathlib.Path('+repr(str(marker))+').write_text(str(p.pid))\npathlib.Path('+repr(str(base/'args.json'))+').write_text(json.dumps(sys.argv[1:]))\ntime.sleep(30)\n');runner.chmod(0o700)
   pid=None
   try:
    with patch.dict(self.env,{'PATH':str(base)+':'+str(self.base)+':'+os.environ['PATH'],'HICS_INSTALL_TEST_MARKER':str(marker)}):result=self.run_probe('install-destroy')
    self.assertTrue(result['started'],result);self.assertTrue(result['busy'],result);self.assertFalse(result['canCancel'],result);self.assertLess(result['destroyMs'],1500,result)
    pid=int(marker.read_text());os.kill(pid,0)
    args=json.loads((base/'args.json').read_text());self.assertIn('--wait',args);self.assertIn('--collect',args);self.assertIn(str(self.base/'fake-pacman'),args)
   finally:
    if marker.exists():
     pid=int(marker.read_text())
     if Path(f'/proc/{pid}/cmdline').exists() and str(worker).encode() in Path(f'/proc/{pid}/cmdline').read_bytes():os.kill(pid,signal.SIGTERM)
 def test_interactive_prompt_is_prefilled_with_supplied_password(self):
  result=self.run_probe('agent-prompt-prefill');self.assertEqual(result.get('prefilled'),'system-fixture-password',result)

 def test_specific_vpn_failure_is_not_replaced_by_generic_reason_zero(self):
  result=self.run_probe('activate-failure');self.assertIn('service stopped',result['error']);self.assertNotIn('reason 0',result['error'])

 def test_disconnect_already_inactive_is_success(self):
  self.assertEqual(self.run_probe('deactivate-inactive')['error'],'')
 def test_disconnect_permission_failure_is_reported(self):
  self.assertIn('Permission denied',self.run_probe('deactivate-denied')['error'])
 def test_disconnect_active_is_success(self):
  self.assertEqual(self.run_probe('deactivate')['error'],'')

 def test_terminated_connection_is_not_shown_as_connecting(self):
  result=self.run_probe('list-disconnected');self.assertEqual(result['error'],'')
  self.assertTrue(result['profiles']);self.assertTrue(all(not p['active'] for p in result['profiles']))

 def test_protocol_change_replaces_plugin_data_and_credentials(self):
  self.assertEqual(self.run_probe('change-protocol')['error'],'')
  data=next(c['data'] for c in self.calls() if c['method']=='Update2')
  self.assertEqual(data['vpn']['service-type'],'org.freedesktop.NetworkManager.l2tp')
  self.assertNotIn('vendor-option',data['vpn']['data']);self.assertNotIn('remote',data['vpn']['data'])
  self.assertEqual(data['vpn']['secrets'],{'password':'new-protocol-password'})
  self.assertEqual(data['connection']['uuid'],'11111111-2222-4333-8444-555555555555')
  self.assertEqual(data['ipv4']['dns-priority'],-88)
 def test_active_protocol_change_is_rejected(self):
  self.assertIn('Disconnect the VPN',self.run_probe('change-protocol-active')['error'])
  self.assertFalse(any(c['method']=='Update2' for c in self.calls()))

 def test_protocol_change_between_wireguard_and_vpn_removes_old_settings(self):
  self.assertEqual(self.run_probe('change-wireguard')['error'],'')
  updates=[c['data'] for c in self.calls() if c['method']=='Update2']
  self.assertEqual(len(updates),2)
  self.assertIn('wireguard',updates[0]);self.assertNotIn('vpn',updates[0])
  self.assertIn('vpn',updates[1]);self.assertNotIn('wireguard',updates[1])
