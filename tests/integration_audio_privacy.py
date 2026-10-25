#!/usr/bin/env python3
"""Exercise balance, amplification and microphone privacy on a private PipeWire graph."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-audio-privacy-') as directory:
 base=Path(directory);runtime=base/'runtime';runtime.mkdir(mode=0o700);(base/'config/hics').mkdir(parents=True)
 shutil.copytree(ROOT/'shell',base/'shell',ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
 env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime),PIPEWIRE_RUNTIME_DIR=str(runtime),XDG_CONFIG_HOME=str(base/'config'),XDG_CACHE_HOME=str(base/'cache'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'),QT_QPA_PLATFORM='offscreen',QML_IMPORT_PATH=str(ROOT/'build/qml'),HICS_NO_ONBOARDING='1')
 env.pop('WAYLAND_DISPLAY',None);env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
 processes=[]
 try:
  bus=subprocess.Popen(['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True);processes.append(bus);address=bus.stdout.readline().strip();env.update(DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address)
  parent=os.environ['WAYLAND_DISPLAY'];parent=parent if parent.startswith('/') else str(Path(os.environ['XDG_RUNTIME_DIR'])/parent)
  (base/'hyprland.lua').write_text('hl.monitor({output="WAYLAND-1",mode="800x600@60",position="0x0",scale=1})\n')
  with (base/'compositor.log').open('w') as log:compositor=subprocess.Popen(['Hyprland','--config',str(base/'hyprland.lua')],env=dict(env,AQ_BACKEND='wayland',WAYLAND_DISPLAY=parent),stdout=log,stderr=subprocess.STDOUT);processes.append(compositor)
  instance=None
  for _ in range(80):
   raw=subprocess.check_output(['hyprctl','instances','-j'],env=env,text=True).strip()
   instance=next((i for i in (json.loads(raw) if raw.startswith('[') else []) if i['pid']==compositor.pid),None)
   if instance:break
   time.sleep(.1)
  assert instance,(base/'compositor.log').read_text()[-3000:]
  env.update(WAYLAND_DISPLAY=instance['wl_socket'],HYPRLAND_INSTANCE_SIGNATURE=instance['instance'],QT_QPA_PLATFORM='wayland')
  env['PULSE_SERVER']='unix:'+str(runtime/'pulse/native')
  for program in ('pipewire','wireplumber','pipewire-pulse'):
   with (base/(program+'.log')).open('w') as log:processes.append(subprocess.Popen([program],env=env,stdout=log,stderr=subprocess.STDOUT))
   time.sleep(.6)
  for name,kind in [('hics-output','Sink'),('hics-input','Source')]:
   result=subprocess.run(['pw-cli','create-node','adapter','{ factory.name = support.null-audio-sink node.name = '+name+' media.class = Audio/'+kind+' object.linger = true audio.position = [ FL FR ] }'],env=env,capture_output=True,text=True,timeout=5);assert result.returncode==0,result.stderr
  with (base/'record.log').open('w') as log:processes.append(subprocess.Popen(['pw-record','--target','hics-output','--rate','48000','--channels','2',str(base/'capture.wav')],env=env,stdout=log,stderr=subprocess.STDOUT))
  (base/'shell/shell.qml').write_text('''import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import Hyprstack.Services
import Hyprstack.Config
import qs.services
ShellRoot {
 id:root;property int phase:0;property int rounds:0
 Component.onCompleted:{GlobalConfig.utilities.toasts.audioOutputChanged=false;GlobalConfig.utilities.toasts.audioInputChanged=false;GlobalConfig.services.maxVolume=1.5;}
 function check(ok,message){if(!ok){console.error("AUDIO_FAILED",phase,message);Qt.exit(1);}}
 Timer{interval:100;running:true;repeat:true;onTriggered:{
  if(++root.rounds>100){console.error("AUDIO_TIMEOUT",root.phase,JSON.stringify(Audio.streams.map(n=>({name:n.name,sink:n.isSink,type:n.type}))));Qt.exit(1);return;}
  const output=Audio.sinks.find(n=>n.name==="hics-output"),input=Audio.sources.find(n=>n.name==="hics-input");
  switch(root.phase){
   case 0:if(!output?.ready||!input?.ready)return;Audio.setAudioSink(output);Audio.setAudioSource(input);root.phase++;break;
   case 1:if(Audio.sink!==output||Audio.source!==input)return;Audio.setVolume(.6);root.phase++;break;
   case 2:if(Math.abs(Audio.volume-.6)>.03)return;root.check(Audio.stereoOutput,"not stereo");Audio.setBalance(.5);root.phase++;break;
   case 3:if(Math.abs(Audio.balance-.5)>.03)return;Audio.setVolume(1.3);root.phase++;break;
   case 4:if(Audio.volume<1.25)return;root.check(Audio.volume<=1.51,"amplification clamp");Audio.setMicrophonePrivacy(true);root.phase++;break;
   case 5:if(!input.audio.muted)return;Audio.setSourceVolume(.7);root.check(input.audio.muted,"volume unmuted microphone");input.audio.muted=false;root.phase++;break;
   case 6:if(!input.audio.muted)return;Audio.setMicrophonePrivacy(false);root.phase++;break;
   case 7:if(input.audio.muted)return;DesktopConveniences.testSpeaker(0);root.phase++;break;
   case 8:if(DesktopConveniences.speakerTesting)return;root.check(!DesktopConveniences.error,"left speaker test failed: "+DesktopConveniences.error);DesktopConveniences.testSpeaker(1);root.phase++;break;
   case 9:if(DesktopConveniences.speakerTesting||Audio.microphoneStreams.length===0)return;root.check(!DesktopConveniences.error,"right speaker test failed: "+DesktopConveniences.error);console.log("AUDIO_PRIVACY_OK");Qt.quit();break;
  }
 }}
}''')
  result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(base/'shell')],env=env,capture_output=True,text=True,timeout=18);output=result.stdout+result.stderr
  assert result.returncode==0 and 'AUDIO_PRIVACY_OK' in output,output[-7000:]
  assert not any(e in output for e in ('TypeError:','ReferenceError:','Binding loop')),output[-7000:]
  print('PASS: real private PipeWire stereo balance, >100% volume, enforced microphone mute and previous-state restoration')
 finally:
  for process in reversed(processes):
   if process.poll() is None:process.terminate();process.wait(timeout=5)
  if processes and processes[0].stdout:processes[0].stdout.close()
