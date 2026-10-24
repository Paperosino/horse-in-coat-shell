"""Temporarily isolate compositor shortcuts; restore them when the UI disappears."""
from __future__ import annotations
import json,os,selectors,signal,socket,subprocess,sys
from pathlib import Path
NAME='hics-onboarding'
def ctl(*args):
 result=subprocess.run(['hyprctl',*args],capture_output=True,text=True,timeout=5)
 if result.returncode:raise RuntimeError((result.stderr or result.stdout).strip())
 return result.stdout.strip()
def main():
 previous=ctl('submap');previous='reset' if previous in ('','default') else previous
 stopping=False
 def stop(*_):
  nonlocal stopping
  stopping=True
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 def activate():
  ctl('eval','hl.define_submap("'+NAME+'",function() hl.bind("F35",function() end,{description="hics setup shortcut guard"}) end);hl.dispatch(hl.dsp.submap("'+NAME+'"))')
 events=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
 try:
  endpoint=Path(os.environ['XDG_RUNTIME_DIR'])/'hypr'/os.environ['HYPRLAND_INSTANCE_SIGNATURE']/'.socket2.sock'
  events.connect(str(endpoint));activate();print('ONBOARDING_GUARD_READY',flush=True)
  with selectors.DefaultSelector() as poll:
   poll.register(sys.stdin,selectors.EVENT_READ);poll.register(events,selectors.EVENT_READ)
   while not stopping:
    for key,_ in poll.select(.25):
     if key.fileobj is sys.stdin:
      if not os.read(sys.stdin.fileno(),4096):stopping=True
     else:
      data=events.recv(65536)
      if not data:stopping=True;break
      lines=data.decode(errors='replace').splitlines()
      if any(l.startswith('configreloaded>>') or l.startswith('submap>>') and l.split('>>',1)[1]!=NAME for l in lines):activate()
 finally:
  events.close()
  try:
   if ctl('submap')==NAME:ctl('eval','hl.dispatch(hl.dsp.submap('+json.dumps(previous)+'))')
  except (OSError,RuntimeError,subprocess.SubprocessError):pass
if __name__=='__main__':
 try:
  if '--worker' in sys.argv:main()
  else:
   # Quickshell tracks this bridge, while the recovery worker survives a hard
   # shell kill. Its inherited input pipe closes when the shell disappears.
   child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr,start_new_session=True)
   sys.exit(child.wait())
 except Exception as error:print(str(error),file=sys.stderr);sys.exit(1)
