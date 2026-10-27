"""The real QML facade must expose wired devices without Wi-Fi hardware."""
import os,select,subprocess,tempfile,unittest
from pathlib import Path
from integration_support import snapshot_qml_runtime,run_snapshot_qml
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.environ.get("WAYLAND_DISPLAY") and Path("/usr/share/hics/qs/bin/hics-qs").exists(),"requires a Wayland session and hics runtime")
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
import qs.modules.utilities.cards as UtilityCards
ShellRoot {
 id:root
 property bool noWifi:Quickshell.env("NETWORK_TEST_NO_WIFI")==="1"
 UtilityCards.Toggles {id:quickToggles;screenState:null;popouts:null;visible:false}
 property int phase:0
 property var original:null
 Component.onCompleted:{NetworkService;Nmcli;}
 function check(value,message){if(!value){console.error("WIRED_FAIL",message);Qt.exit(1);return false;}return true;}
 Process {id:change;command:["gdbus","call","--system","--dest","org.freedesktop.NetworkManager","--object-path","/org/freedesktop/NetworkManager","--method","org.hics.Test.SetWiredState",root.phase===1?"false":"true"]}
 Timer {interval:100;repeat:true;running:true;onTriggered:{
  if(root.phase===0){
   if(!Nmcli.activeEthernet)return;
   if(!root.check(Nmcli.hasWirelessHardware===!root.noWifi&&Nmcli.networks.length===(root.noWifi?0:1)&&Nmcli.networkIcon==="cable"&&Nmcli.ethernetDevices.length===1,"connected Ethernet was shown as missing Wi-Fi"))return;
   if(!root.check(quickToggles.quickToggles.some(item=>item.id==="wifi")===!root.noWifi,"quick toggles offered Wi-Fi without hardware"))return;
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
   runtime_env=snapshot_qml_runtime(ROOT,base)
   bus_config=base/'bus.conf'
   bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(base)+'</listen><auth>EXTERNAL</auth><policy context="default"><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
   bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(bus_config)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
   self.addCleanup(self.stop_process,bus)
   self.assertTrue(select.select([bus.stdout],[],[],3)[0],'Private bus did not start')
   env=dict(os.environ,DBUS_SYSTEM_BUS_ADDRESS=bus.stdout.readline().strip(),NETWORK_TEST_LOG=str(base/'calls.jsonl'),NETWORK_TEST_NO_WIFI='1',HOME=str(base),XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),QT_QPA_PLATFORM='wayland',HICS_SHELL_DIR=str(shell),QML_IMPORT_PATH=str(ROOT/'build/qml'))
   env['DBUS_SESSION_BUS_ADDRESS']=env['DBUS_SYSTEM_BUS_ADDRESS']
   env.update(runtime_env,PIPEWIRE_REMOTE='hics-network-fixture-absent',PULSE_SERVER='unix:'+str(base/'absent-pulse'))
   display=Path(os.environ['WAYLAND_DISPLAY'])
   env['WAYLAND_DISPLAY']=str(display if display.is_absolute() else Path(os.environ['XDG_RUNTIME_DIR'])/display)
   runtime=base/'run';runtime.mkdir(mode=0o700);env['XDG_RUNTIME_DIR']=str(runtime)
   env['HYPRLAND_INSTANCE_SIGNATURE']='hics-network-qml-fixture'
   if not no_wifi:env.pop('NETWORK_TEST_NO_WIFI',None)
   mock=subprocess.Popen(['python3',str(ROOT/'tests/mock_network_bus.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   self.addCleanup(self.stop_process,mock)
   try:
    self.assertTrue(select.select([mock.stdout],[],[],5)[0],'Private network mock did not start')
    self.assertEqual(mock.stdout.readline().strip(),'ready')
    result=run_snapshot_qml(['/usr/share/hics/qs/bin/hics-qs','-p',str(shell)],env,ROOT/'build',15)
    output=result.stdout+result.stderr
    self.assertEqual(result.returncode,0,output[-6000:]);self.assertIn('WIRED_QML_OK',output)
    self.assertNotIn('TypeError:',output);self.assertNotIn('ReferenceError:',output)
   finally:
    self.stop_process(mock);self.stop_process(bus)
 @staticmethod
 def stop_process(process):
  if process.poll() is None:
   process.terminate()
   try:process.wait(timeout=3)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
  for stream in (process.stdin,process.stdout,process.stderr):
   if stream and not stream.closed:stream.close()
