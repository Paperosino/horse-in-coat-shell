#!/usr/bin/env python3
"""Normal QMP/PAM unlock for the fixed disposable guest lock-screen fixture.

Credentials remain in a private file outside Git and are never emitted.
Unsupported layouts/screens fail before typing. No lock owner is restarted.
"""
import json,os,shlex,stat,string,subprocess,time
from pathlib import Path
from vm_cachyos import qmp

def unlock_guest(lab):
 lab=Path(lab).resolve()
 def remote(args):
  command=['ssh','-i',str(lab/'guest_ed25519'),'-p','22280','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','UserKnownHostsFile='+str(lab/'known_hosts-installed'),'root@127.0.0.1',shlex.join(args)]
  return subprocess.check_output(command,text=True,timeout=10).strip()
 state=qmp(lab,'query-status')
 if state.get('status')=='suspended':qmp(lab,'system_wakeup')
 elif not state.get('running'):raise RuntimeError('Inspect the current VM state before authenticating')
 assert remote(['cat','/etc/hostname'])=='hics-test'
 assert remote(['systemd-detect-virt']) in ('qemu','kvm')
 user=['runuser','-u','hics-test','--','env','XDG_RUNTIME_DIR=/run/user/1000','LANG=ru_RU.UTF-8']
 def ctl(*args):return remote(user+['hyprctl','-i','0',*args])
 def locked():return json.loads(ctl('-j','locked'))['locked']
 if not locked():return False
 monitors=json.loads(ctl('monitors','-j'))
 assert len(monitors)==1 and all(monitors[0].get(k)==v for k,v in {'width':1280,'height':800,'scale':1,'transform':0,'x':0,'y':0}.items()),'Inspect unsupported lock-screen geometry before typing'
 devices=json.loads(ctl('devices','-j'));keyboards=[k for k in devices['keyboards'] if k.get('main')]
 assert len(keyboards)==1 and keyboards[0].get('layout','').split(',')[0]=='us','Inspect keyboard mapping before typing'
 descriptor=os.open(lab/'guest-user-password',os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(descriptor,'rb') as stream:
  info=os.fstat(stream.fileno());assert stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and not info.st_mode&0o077 and info.st_size<=128
  raw=stream.read(129);assert len(raw)<=128
 secret=raw.removesuffix(b'\n').decode('ascii')
 plain=dict(zip('-=[];\'`,./\\ ',['minus','equal','bracket_left','bracket_right','semicolon','apostrophe','grave_accent','comma','dot','slash','backslash','spc']))
 shifted=dict(zip('!@#$%^&*()_+{}:"~<>?|',['1','2','3','4','5','6','7','8','9','0','minus','equal','bracket_left','bracket_right','semicolon','apostrophe','grave_accent','comma','dot','slash','backslash']))
 assert secret and all(c in string.ascii_letters+string.digits or c in plain or c in shifted for c in secret),'Unsupported test credential encoding'
 ctl('switchxkblayout','all','0')
 def key(codes,hold=40):qmp(lab,'send-key',{'keys':[{'type':'qcode','data':code} for code in codes],'hold-time':hold})
 key(['shift'],50);time.sleep(.4)
 qmp(lab,'input-send-event',{'events':[{'type':'abs','data':{'axis':'x','value':16384}},{'type':'abs','data':{'axis':'y','value':24166}},{'type':'btn','data':{'button':'left','down':True}}]});time.sleep(.15)
 qmp(lab,'input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':False}}]})
 key(['ctrl','a'])
 for char in secret:
  code=char.lower() if char.isalnum() else shifted.get(char,plain.get(char))
  key((['shift'] if char.isupper() or char in shifted else [])+[code]);time.sleep(.05)
 key(['ret'],60)
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  if not locked():return True
  time.sleep(.2)
 raise RuntimeError('PAM did not unlock; inspect the guest before another attempt')
