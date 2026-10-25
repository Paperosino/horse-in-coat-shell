"""The real QML facade must expose wired devices without Wi-Fi hardware."""
import os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get("WAYLAND_DISPLAY") and Path("/usr/bin/hics-shell").exists(),"requires a Wayland session and hics runtime")
class NetworkQml(unittest.TestCase):
 def test_wired_only_state_and_object_lifecycle(self):self.exercise(True)
 def test_wired_with_inactive_wifi_and_object_lifecycle(self):self.exercise(False)
 def exercise(self,no_wifi):
  with tempfile.TemporaryDirectory(prefix='hics-wired-qml-') as directory:
   base=Path(directory);shell=base/'shell';shell.mkdir()
   for source in (ROOT/'shell').iterdir():
    if source.is_dir() and source.name!='plugin':(shell/source.name).symlink_to(source,target_is_directory=True)
   (shell/'shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Io
import Hyprstack.Services
import qs.services
ShellRoot {
 id:root
 property bool noWifi:Quickshell.env("NETWORK_TEST_NO_WIFI")==="1"
 property int phase:0
 property var original:null
 Component.onCompleted:{NetworkService;Nmcli;}
 function check(value,message){if(!value){console.error("WIRED_FAIL",message);Qt.exit(1);return false;}return true;}
 Process {id:change;command:["gdbus","call","--system","--dest","org.freedesktop.NetworkManager","--object-path","/org/freedesktop/NetworkManager","--method","org.hics.Test.SetWiredState",root.phase===1?"false":"true"]}
 Timer {interval:100;repeat:true;running:true;onTriggered:{
  if(root.phase===0){
   if(!Nmcli.activeEthernet)return;
   if(!root.check(Nmcli.hasWirelessHardware===!root.noWifi&&Nmcli.networks.length===(root.noWifi?0:1)&&Nmcli.networkIcon==="cable"&&Nmcli.ethernetDevices.length===1,"connected Ethernet was shown as missing Wi-Fi"))return;
   root.original=Nmcli.activeEthernet;
   for(let i=0;i<10;i++)Nmcli.syncState();
   if(!root.check(Nmcli.activeEthernet===root.original&&Nmcli.ethernetDevices.length===1,"refresh replaced or duplicated wired wrappers"))return;
   root.phase=1;change.running=true;
  }else if(root.phase===1){
   if(Nmcli.ethernetInterfaces[0]?.connected)return;
   if(!root.check(!Nmcli.activeEthernet&&Nmcli.networkIcon===(root.noWifi?"lan":"wifi_off")&&Nmcli.ethernetDevices[0]===root.original,"disconnect state or wrapper identity is wrong"))return;
   root.phase=2;change.running=true;
  }else{
   if(!Nmcli.activeEthernet)return;
   if(!root.check(Nmcli.activeEthernet===root.original&&Nmcli.networkIcon==="cable","reconnection did not restore the wired icon"))return;
   console.log("WIRED_QML_OK");Qt.quit();
  }
 }}
 Timer {interval:6000;running:true;onTriggered:{console.error("WIRED_TIMEOUT",JSON.stringify(NetworkService.state));Qt.exit(1);}}
}''')
   bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
   env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=bus.stdout.readline().strip(),NETWORK_TEST_LOG=str(base/'calls.jsonl'),NETWORK_TEST_NO_WIFI='1',HOME=str(base),XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),QT_QPA_PLATFORM='wayland',HICS_SHELL_DIR=str(shell),QML_IMPORT_PATH=str(ROOT/'build/qml'))
   if not no_wifi:env.pop('NETWORK_TEST_NO_WIFI',None)
   mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_network_bus.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   try:
    self.assertEqual(mock.stdout.readline().strip(),'ready')
    result=subprocess.run(['/usr/bin/hics-shell'],env=env,capture_output=True,text=True,timeout=15)
    output=result.stdout+result.stderr
    self.assertEqual(result.returncode,0,output[-6000:]);self.assertIn('WIRED_QML_OK',output)
    self.assertNotIn('TypeError:',output);self.assertNotIn('ReferenceError:',output)
   finally:
    mock.terminate();mock.wait(timeout=3);bus.terminate();bus.wait(timeout=3)
    mock.stdout.close();mock.stderr.close();bus.stdout.close()
