"""Actual configuration daemon remains reachable after malformed disk state."""
import json,os,socket,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Watcher(unittest.TestCase):
 def test_bad_startup_and_later_plugin_fifo_do_not_stop_ipc(self):
  with tempfile.TemporaryDirectory(prefix='hics-watcher-fault-') as directory:
   root=Path(directory);config=root/'config/hics';config.mkdir(parents=True);runtime=root/'run';runtime.mkdir(mode=0o700)
   (config/'dock.json').write_text('[]')
   env=dict(os.environ,XDG_CONFIG_HOME=str(root/'config'),XDG_STATE_HOME=str(root/'state'),XDG_DATA_HOME=str(root/'data'),XDG_CACHE_HOME=str(root/'cache'),XDG_RUNTIME_DIR=str(runtime),HICS_CONFIG_NO_SYSTEMD='1')
   env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
   with (root/'daemon.log').open('w+') as log:
    process=subprocess.Popen([sys.executable,str(ROOT/'shell/assets/configuration_manager.py'),'watch'],env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
     def status():
      for _ in range(80):
       self.assertIsNone(process.poll(),'Daemon exited: '+(root/'daemon.log').read_text())
       endpoints=list(runtime.glob('hics-configuration-*/control.sock'))
       if endpoints:
        try:
         with socket.socket(socket.AF_UNIX) as client:
          client.settimeout(2);client.connect(str(endpoints[0]));client.sendall(b'{"operation":"status"}\n');data=b''
          while b'\n' not in data:data+=client.recv(65536)
          return json.loads(data)
        except (ConnectionRefusedError,FileNotFoundError):pass
       time.sleep(.05)
      self.fail('Configuration IPC did not become ready')
     self.assertNotIn('error',status())
     backups=list((root/'state/hics/configuration-recovery').glob('*.invalid'));self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),b'[]')
     os.mkfifo(config/'plugins.json');time.sleep(1.2)
     result=status();self.assertNotIn('error',result);self.assertTrue(result['recoveryWarning'])
     warning=root/'state/hics/configuration-recovery-warning.json';stamp=warning.stat().st_mtime_ns
     history=list((root/'state/hics/configuration-history').glob('*.json.gz'))
     time.sleep(1.2);self.assertEqual(warning.stat().st_mtime_ns,stamp)
     self.assertEqual(list((root/'state/hics/configuration-history').glob('*.json.gz')),history)
     prefs=config/'plugins.json';prefs.unlink();prefs.write_text('{}');time.sleep(1.2)
     result=status();self.assertNotIn('error',result);self.assertFalse(result['recoveryWarning']);self.assertIsNone(process.poll())
     dock=config/'dock.json';dock.unlink();os.mkfifo(dock);time.sleep(1.2)
     self.assertIn('dock.json',status()['recoveryWarning']);self.assertIsNone(process.poll())
     dock.unlink()
     with dock.open('wb') as stream:stream.truncate(2*1024*1024)
     time.sleep(1.2);self.assertNotIn('error',status());self.assertEqual(json.loads(dock.read_text()),{})
     backups=list((root/'state/hics/configuration-recovery').glob('*.invalid'))
     self.assertTrue(any(path.stat().st_size==2*1024*1024 for path in backups));self.assertIsNone(process.poll())
    finally:
     process.terminate()
     try:process.wait(timeout=5)
     except subprocess.TimeoutExpired:process.kill();process.wait()
