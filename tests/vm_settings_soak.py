#!/usr/bin/env python3
"""Open/close real settings windows in the disposable guest; collect resource trends.

Only reads pages. Does not apply settings, close external applications, or infer
absence of a leak from a single RSS value. Leaves no settings windows open.
"""
import argparse,json,subprocess,threading
from pathlib import Path
from vm_cachyos import qmp
REMOTE=r'''
import json,os,re,subprocess,sys,time
from pathlib import Path
assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
assert Path('/etc/hostname').read_text().strip()=='hics-test'
state=json.loads(Path('/home/hics-test/.local/state/hics/shell-recovery.json').read_text());assert not state.get('safe')
user=['runuser','-u','hics-test','--','env','XDG_RUNTIME_DIR=/run/user/1000','DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','LANG=ru_RU.UTF-8']
instances=json.loads(subprocess.check_output(user+['hyprctl','instances','-j'],text=True));assert len(instances)==1
user+=['WAYLAND_DISPLAY='+instances[0]['wl_socket']]
runner=int(subprocess.check_output(user+['systemctl','--user','show','hic-session.service','-p','MainPID','--value'],text=True).strip())
children=Path(f'/proc/{runner}/task/{runner}/children').read_text().split()
uis=[int(p) for p in children if Path('/proc/'+p+'/comm').read_text().strip()=='hics-qs'];assert len(uis)==1,uis
pid=uis[0]
def process_stat(pid):return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
identity=process_stat(pid)[19]
allocatorKeys={'MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_','MALLOC_ARENA_MAX','GLIBC_TUNABLES'}
allocatorEnvironment={entry.split('=',1)[0]:entry.split('=',1)[1] for entry in Path(f'/proc/{pid}/environ').read_bytes().decode().split('\0') if '=' in entry and entry.split('=',1)[0] in allocatorKeys}
records=subprocess.check_output(['journalctl','-b','-n','1','-o','json','--no-pager'],text=True,timeout=10)
cursor=json.loads(records.strip().splitlines()[-1])['__CURSOR']

def ctl(*args):return subprocess.check_output(user+['hyprctl','-i',instances[0]['instance'],*args],text=True,timeout=8)
def own():return [w for w in json.loads(ctl('-j','clients')) if w['pid']==pid]
def unlocked():return subprocess.check_output(user+['/usr/share/hics/qs/bin/hics-qs','ipc','-p','/usr/share/hics/shell','call','lock','isLocked'],text=True,timeout=5).strip()=='false'
def wait(check,seconds=10):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  value=check()
  if value:return value
  time.sleep(.05)
 raise AssertionError('Guest UI did not reach the required state')
def sample(cycle):
 os.kill(pid,0)
 stats=process_stat(pid);assert stats[19]==identity,'Main UI PID was reused'
 lines=Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines()
 memory={k:int(next(line for line in lines if line.startswith(k+':')).split()[1]) for k in ('Rss','Pss','Private_Dirty')}
 return {'cycle':cycle,'seconds':time.monotonic()-started,'memoryKiB':memory,'fds':len(list(Path(f'/proc/{pid}/fd').iterdir())),'threads':len(list(Path(f'/proc/{pid}/task').iterdir())),'cpuTicks':int(stats[11])+int(stats[12])}
assert unlocked(),'Unlock the guest normally before running an interactive soak'
assert not own(),'Close guest settings/recovery windows before starting the soak'
started=time.monotonic();samples=[sample(0)];pages=['network','audio','storage','clipboard','display','configuration-history']
for index in range(int(sys.argv[1])):
 page=pages[index%len(pages)]
 if index%6==0:assert unlocked(),'Guest locked during the interactive soak; do not count hidden windows as rendered UI'
 opened_at=time.monotonic()
 subprocess.run(user+['/usr/share/hics/qs/bin/hics-qs','ipc','-p','/usr/share/hics/shell','call','nexus','page',page],capture_output=True,text=True,check=True,timeout=10)
 windows=wait(own);open_seconds=time.monotonic()-opened_at;assert len(windows)==1,windows
 window=windows[0];assert window['class']=='org.hics.Shell'
 time.sleep(.3)
 closed_at=time.monotonic()
 ctl('eval','hl.dispatch(hl.dsp.window.close({window=hl.get_window('+json.dumps('address:'+window['address'])+')}))')
 wait(lambda:not own());close_seconds=time.monotonic()-closed_at
 if (index+1)%len(pages)==0:time.sleep(.7)
 value=sample(index+1);value.update(page=page,openSeconds=open_seconds,closeSeconds=close_seconds);samples.append(value)
 if (index+1)%6==0:print('Completed '+str(index+1)+' UI cycles',file=sys.stderr,flush=True)
time.sleep(2);samples.append(sample(int(sys.argv[1])))
assert not ctl('configerrors').strip()
assert int(subprocess.check_output(user+['systemctl','--user','show','hic-session.service','-p','MainPID','--value'],text=True).strip())==runner
raw=subprocess.check_output(['journalctl','-b','--after-cursor='+cursor,'_SYSTEMD_USER_UNIT=hic-session.service','_UID=1000','-o','json','--no-pager'],text=True,timeout=10)
entries=[json.loads(line) for line in raw.splitlines() if line.startswith('{')]
failures=[]
pattern=re.compile(r'TypeError|ReferenceError|Binding loop|Cannot read propert|Unable to assign \[(?:undefined|null)\]|ASSERT|Segmentation fault')
for entry in entries:
 message=entry.get('MESSAGE','')
 if isinstance(message,str) and pattern.search(message):failures.append({'message':message[:2048],'cursor':entry.get('__CURSOR')})
assert not failures,failures
qslog=subprocess.check_output(user+['/usr/share/hics/qs/bin/hics-qs','log','--pid',str(pid),'--tail','10000','--no-color'],text=True,timeout=10)
qslines=qslog.splitlines();assert len(qslines)<10000,'Quickshell log exceeded acceptance bound'
qsfailures=[line[:2048] for line in qslines if pattern.search(line)]
assert not qsfailures,qsfailures
categories={}
for line in qslines:
 match=re.match(r'\s*(WARN|ERROR) ([^:]+):',line)
 if match:categories[match[2]]=categories.get(match[2],0)+1
print(json.dumps({'pid':pid,'runner':runner,'allocatorEnvironment':allocatorEnvironment,'clockTicksPerSecond':os.sysconf('SC_CLK_TCK'),'journalEntriesChecked':len(entries),'journalBindingErrors':failures,'quickshellLogLines':len(qslines),'quickshellBindingErrors':qsfailures,'warningCategories':categories,'pageDwellSeconds':0.3,'pages':pages,'cycles':int(sys.argv[1]),'keepActiveInput':'QMP Shift every 15 seconds; no text','logindInhibitor':True,'samples':samples,'package':subprocess.check_output(['pacman','-Q','hic-shell'],text=True).strip(),'kernel':os.uname().release,'gpuDrivers':sorted({p.resolve().name for p in Path('/sys/class/drm').glob('card[0-9]/device/driver')}),'scope':'QEMU software rendering; read-only page lifecycle, not all functions or proof of no leaks'},indent=2))
'''
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--lab',type=Path,required=True);parser.add_argument('--disposable-cachyos-vm',action='store_true',required=True);parser.add_argument('--cycles',type=int,default=60);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
 if not 1<=args.cycles<=500:raise SystemExit('Cycles must be between 1 and 500')
 if args.out.exists():raise SystemExit('Refusing to replace existing evidence')
 lab=args.lab.resolve()
 if not qmp(lab,'query-status').get('running'):raise SystemExit('VM is not running')
 command=['ssh','-i',str(lab/'guest_ed25519'),'-p','22280','-o','BatchMode=yes','-o','UserKnownHostsFile='+str(lab/'known_hosts-installed'),'root@127.0.0.1','timeout','--kill-after=3',str(25+args.cycles*15),'systemd-inhibit','--what=idle:sleep','--mode=block','--who=hics-tests','--why=hics-settings-lifecycle-test','python3','-',str(args.cycles)]
 stopped=threading.Event();input_errors=[]
 def keep_active():
  while not stopped.is_set():
   try:
    if not qmp(lab,'query-status').get('running'):raise RuntimeError('Guest stopped/suspended during interactive soak')
    qmp(lab,'send-key',{'keys':[{'type':'qcode','data':'shift'}],'hold-time':35})
   except Exception as error:input_errors.append(str(error));return
   stopped.wait(15)
 keeper=threading.Thread(target=keep_active);keeper.start()
 try:result=subprocess.run(command,input=REMOTE,text=True,capture_output=True,timeout=30+args.cycles*15)
 finally:stopped.set();keeper.join(timeout=6)
 if input_errors:raise SystemExit(str(input_errors))
 if result.returncode:raise SystemExit(result.stdout+result.stderr)
 report=json.loads(result.stdout);args.out.write_text(json.dumps(report,indent=2)+'\n');print(result.stderr.strip());print(json.dumps({'cycles':report['cycles'],'first':report['samples'][0],'last':report['samples'][-1]},indent=2))
if __name__=='__main__':main()
