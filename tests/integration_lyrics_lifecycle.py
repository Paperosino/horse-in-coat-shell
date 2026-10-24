#!/usr/bin/env python3
"""Real lyrics singleton: bounded scans, rapid track changes, clear and teardown."""
import json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-lyrics-') as directory:
 base=Path(directory);lyrics=base/'lyrics';lyrics.mkdir()
 for n in range(200):
  folder=lyrics/f'd{n}';folder.mkdir()
  for i in range(25):(folder/f'unrelated-{i}.txt').touch()
 (lyrics/'cycle').symlink_to(lyrics,target_is_directory=True)
 (lyrics/'Artist - Final.lrc').write_text('[00:01.00]Final lyrics\n')
 os.mkfifo(lyrics/'Artist - Pipe.lrc')
 qml=base/'test.qml';qml.write_text('''import QtQuick
import Quickshell
import Hyprstack.Config
import Hyprstack.Services
ShellRoot {
 id:root
 property int steps:0
 property int ticks:0
 property int phase:0
 function require(value,message){if(!value){console.error(message);Qt.exit(1);throw new Error(message)}}
 Component.onCompleted:{GlobalConfig.paths.lyricsDir=__LYRICS_DIR__;Lyrics.preferredBackend=LyricsBackend.Local;Lyrics.setTrack("Artist","Pipe");}
 Timer{interval:5;running:true;repeat:true;onTriggered:root.ticks++}
 Timer{interval:65;running:root.phase===0;repeat:true;onTriggered:{
  root.steps++;
  if(root.steps<20)Lyrics.setTrack("Artist","Missing"+root.steps);
  else{root.phase=1;Lyrics.setTrack("Artist","Final");}
 }}
 Timer{interval:40;running:true;repeat:true;onTriggered:{
  if(root.phase===1&&!Lyrics.loading&&Lyrics.hasLyrics){
   root.require(Lyrics.lyrics.join(" ").includes("Final lyrics"),"stale track won");
   root.require(root.ticks>50,"scan blocked UI timer");Lyrics.clearTrack();root.phase=2;
   settle.start();
  }
 }}
 Timer{id:settle;interval:200;onTriggered:{
  root.require(!Lyrics.hasLyrics&&Lyrics.trackTitle==="","clear resurrected old results");
  Lyrics.setTrack("Artist","MissingOnExit");exitTimer.start();
 }}
 Timer{id:exitTimer;interval:60;onTriggered:{console.log("LYRICS_LIFECYCLE_OK",root.ticks);Qt.exit(0)}}
 Timer{interval:6000;running:true;onTriggered:{console.error("lyrics timeout",Lyrics.loading,Lyrics.hasLyrics);Qt.exit(1)}}
}'''.replace('__LYRICS_DIR__',json.dumps(str(lyrics))))
 env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),QML_IMPORT_PATH=str(ROOT/'build/qml'),G_DEBUG='fatal-criticals')
 env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);env.pop('WAYLAND_DISPLAY',None)
 result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(qml)],env=env,capture_output=True,text=True,timeout=10)
 output=result.stdout+result.stderr
 assert result.returncode==0 and 'LYRICS_LIFECYCLE_OK' in output,output
 assert 'TypeError' not in output and 'ReferenceError' not in output,output
 print('PASS: FIFO and directory cycle rejected; rapid local scans preserve responsive UI, latest track, clear and shutdown')
