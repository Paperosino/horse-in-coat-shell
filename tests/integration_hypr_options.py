#!/usr/bin/env python3
"""Read both Hyprland description formats and safely round-trip Lua options."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
for legacy in (False, True):
    with tempfile.TemporaryDirectory(prefix='hics-options-') as directory:
        base = Path(directory)
        runtime = base/'runtime'
        ipc = runtime/'hypr/fixture'
        ipc.mkdir(parents=True, mode=0o700)
        runtime.chmod(0o700)
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(str(ipc/'.socket.sock'))
        listener.listen()
        events = socket.socket(socket.AF_UNIX)
        events.bind(str(ipc/'.socket2.sock'))
        events.listen()
        requests=[]
        stopped=threading.Event()
        def serve():
            while not stopped.is_set():
                try: client,_=listener.accept()
                except OSError:return
                with client:
                    request=client.recv(65536).decode()
                    requests.append(request)
                    if request=='j/descriptions':
                        values={'general:gaps_in':'4 5 6 7','animations:enabled':False,'decoration:rounding':17}
                        data=[{'value':k,'data':{'current':v}} if legacy else {'name':k,'current':v} for k,v in values.items()]
                    elif request.startswith('[[BATCH]]j/getoption'):
                        # Metadata intentionally differs from live Lua values.
                        rows=[{'option':'general:gaps_in','css':'9 8 7 6'},
                              {'option':'animations:enabled','bool':False},
                              {'option':'decoration:rounding','int':23}]
                        client.sendall(('\n'.join(json.dumps(r) for r in rows)+'\n').encode())
                        continue
                    elif request=='j/devices':data={'keyboards':[],'mice':[],'touchpads':[],'tablets':[]}
                    else:data=None
                    raw=json.dumps(data).encode() if data is not None else b'ok'
                    # Fragmented responses must be assembled through EOF.
                    client.sendall(raw[:4]);client.sendall(raw[4:])
        thread=threading.Thread(target=serve,daemon=True);thread.start()
        qml=base/'test.qml'
        qml.write_text('''import QtQuick
import Quickshell
import Hyprstack.Services
ShellRoot {
 HyprExtras {id:extras;usingLua:true}
 property int phase:0
 Timer {interval:40;running:true;repeat:true;onTriggered:{
  if(phase===0&&extras.options["general:gaps_in"]!==undefined){
   if(extras.options["general:gaps_in"]!=="9 8 7 6"||extras.options["animations:enabled"]!==false||extras.options["decoration:rounding"]!==23){console.error("OPTION_VALUES_FAILED");Qt.exit(1);return}
   phase=1;extras.applyOptions({"general:gaps_in":extras.options["general:gaps_in"],"animations:enabled":false,"input:kb_layout":"us,ru"});
  }else if(phase===1){console.log("OPTIONS_OK");Qt.quit()}
 }}
 Timer {interval:4000;running:true;onTriggered:Qt.exit(1)}
}''')
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_RUNTIME_DIR=str(runtime),
            HYPRLAND_INSTANCE_SIGNATURE='fixture',QML_IMPORT_PATH=str(ROOT/'build/qml'),QML2_IMPORT_PATH=str(ROOT/'build/qml'))
        env.pop('WAYLAND_DISPLAY',None)
        try:
            result=subprocess.run(['/usr/share/hics/qs/bin/hics-qs','-p',str(qml)],env=env,capture_output=True,text=True,timeout=6)
            output=result.stdout+result.stderr
            assert result.returncode==0 and 'OPTIONS_OK' in output,output
            batch=next(r for r in requests if r.startswith('[[BATCH]]eval'))
            assert 'gaps_in = {top=9,right=8,bottom=7,left=6}' in batch,batch
            assert 'kb_layout = "us,ru"' in batch,batch
            assert 'enabled = false' in batch,batch
            print('PASS: '+('legacy' if legacy else '0.56 flat')+' option format and typed Lua restoration')
        finally:
            stopped.set();listener.close();events.close()
