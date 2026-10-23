#!/usr/bin/env python3
"""Run the production controller against redirected kernel files and commands.

Only temporary copies of source paths are redirected; the installed executable
has no environment switch that could redirect privileged I/O.
"""
import json,os,re,shlex,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='hics-memory-controller-') as directory:
 base=Path(directory); tree=base/'host';src=base/'source';src.mkdir()
 def redirect(s):
  for prefix in ('/proc/','/sys/','/etc/','/run/','/var/lib/','/dev/','/usr/bin/'):
   s=s.replace(prefix,str(tree)+prefix)
  return s
 for name in ('backend.hpp','memory.hpp','memory.cpp','memory_worker.cpp'):
  text=redirect((ROOT/'native/system'/name).read_text())
  if name=='memory_worker.cpp':
   text=re.sub(r'if\s*\(geteuid\(\)\)', 'if(false)', text).replace('s.st_uid','false').replace('volume.fileSystemType()', 'QByteArray("ext4")')
  (src/name).write_text(text)
 (src/'stub.cpp').write_text('#include "backend.hpp"\nnamespace System {QString encode(const QJsonObject &){return {};}}')
 flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6DBus'],text=True))
 binary=base/'controller'
 subprocess.run(['c++','-std=c++20','-fPIC',str(src/'memory_worker.cpp'),str(src/'memory.cpp'),str(src/'stub.cpp'),'-I',str(src),'-DHYPRSTACK_SYSTEMD_RUN="/usr/bin/false"','-DHYPRSTACK_MEMORY_EXECUTABLE="/usr/bin/false"',*flags,'-o',str(binary)],check=True)
 def put(path,value):
  p=tree/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(str(value))
 def ram(available):put('proc/meminfo',f'MemTotal: 8388608 kB\nMemAvailable: {available} kB\n')
 def rows():
  return [line.split() for line in (tree/'proc/swaps').read_text().splitlines()[1:] if line.strip()]
 def set_rows(rows):put('proc/swaps','Filename Type Size Used Priority\n'+'\n'.join(' '.join(map(str,row)) for row in rows)+'\n')
 ram(7000000);set_rows([])
 for key,value in [('enabled','N'),('compressor','zstd'),('max_pool_percent',20)]:put('sys/module/zswap/parameters/'+key,value)
 put('sys/class/zram-control/hot_add',1);put('sys/class/zram-control/hot_remove','')
 for key,value in [('reset',0),('comp_algorithm','[zstd] lz4 lzo-rle'),('disksize',0)]:put('sys/block/zram1/'+key,value)
 put('dev/zram1','')
 tool=tree/'usr/bin/tool';tool.parent.mkdir(parents=True,exist_ok=True)
 tool.write_text('#!'+os.sys.executable+'\n'+'''import sys,pathlib,json,os
root=pathlib.Path(__file__).resolve().parents[2];name=pathlib.Path(sys.argv[0]).name;args=sys.argv[1:]
proc=root/'proc/swaps';rows=[s.split() for s in proc.read_text().splitlines()[1:] if s.strip()]
if name=='btrfs':pathlib.Path(args[-1]).mkdir(parents=True,exist_ok=True)
if name=='mkswap' and '--file' in args:
 p=pathlib.Path(args[-1]);p.write_text(args[args.index('--size')+1])
if name=='swapon':
 p=args[-1];size=int((root/'sys/block/zram1/disksize').read_text()) if '/dev/zram' in p else int(pathlib.Path(p).read_text())
 rows.append([p,'partition' if '/dev/zram' in p else 'file',str(size//1024),'0',args[args.index('--priority')+1]])
if name=='swapoff':rows=[r for r in rows if r[0]!=args[-1]]
proc.write_text('Filename Type Size Used Priority\\n'+'\\n'.join(' '.join(r) for r in rows)+'\\n')
''');tool.chmod(0o755)
 for name in ('systemctl','modprobe','btrfs','mkswap','swapon','swapoff'):(tool.parent/name).symlink_to(tool.name)
 config={'mode':'smart','zramMiB':256,'ramThreshold':75,'zramThreshold':80,'chunkMiB':64,'diskMaxMiB':128,'reserveMiB':512,'releaseSeconds':15}
 def configure(mode):
  c=dict(config,mode=mode)
  subprocess.run([str(binary),'configure',json.dumps(c)],check=True,capture_output=True)
 def status():
  try:return json.loads((tree/'run/hics-memory/status.json').read_text())
  except (FileNotFoundError,json.JSONDecodeError):return {}
 def until(check,timeout=12):
  deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   s=status()
   if s.get('error'):raise AssertionError(s)
   if check(s):return
   time.sleep(.15)
  raise AssertionError(status())
 process=None
 try:
  configure('smart');process=subprocess.Popen([str(binary)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
  until(lambda s:s.get('phase')=='ram');assert rows()==[]
  ram(1000000);until(lambda s:s.get('phase')=='zram');assert len(rows())==1
  data=rows();data[0][3]=str(int(data[0][2])*.85//1);data[0][3]=str(int(float(data[0][3])));set_rows(data)
  until(lambda s:s.get('phase')=='zswap');assert len(rows())==2,rows()
  assert (tree/'sys/module/zswap/parameters/enabled').read_text()=='1'
  data=rows();disk=next(r for r in data if r[1]=='file');first=Path(disk[0]);inode=first.stat().st_ino;disk[3]=str(int(int(disk[2])*.85));set_rows(data)
  until(lambda s:len(rows())==3);assert first.stat().st_ino==inode
  time.sleep(5.5);assert len(rows())==3 # hard disk limit
  data=rows()
  for r in data:r[3]='0'
  set_rows(data);ram(7000000)
  until(lambda s:s.get('phase')=='ram',timeout=28);assert rows()==[]
  assert not list((tree/'var/lib/hics-memory/swap').glob('swap-*.swap'))
  print('PASS: RAM → ZRAM → ZSwap, chunk growth, hard limit, delayed return and cleanup',flush=True)
  for mode,phase,count in [('zram','zram',1),('zswap','zswap',1),('both','zswap',2),('off','ram',0),('system','system',0)]:
   configure(mode);until(lambda s:s.get('phase')==phase and len(rows())==count)
  print('PASS: zram, zswap, both, off and system strategies',flush=True)
 finally:
  if process:
   process.terminate();process.wait(timeout=5)
