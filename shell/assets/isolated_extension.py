"""Bounded JSON-lines transport for hics-2 workers in a bubblewrap namespace."""
import collections,ctypes,json,os,selectors,signal,subprocess,sys,time
from pathlib import Path
from plugin_manager import find
from feature_common import STATE

def validate_state(state):
    if not isinstance(state,dict) or set(state)-{'slots'} or not isinstance(state.get('slots'),dict):raise ValueError('Expected declarative extension slots')
    result={'slots':{}}
    for slot,rows in state['slots'].items():
        if slot not in ('barWidget','desktopWidget','panel','settings','main') or not isinstance(rows,list) or len(rows)>(1 if slot=='barWidget' else 32):raise ValueError('Invalid extension slot')
        output=[]
        for row in rows:
            if not isinstance(row,dict) or row.get('type') not in ('label','button','toggle','progress','heading'):raise ValueError('Unsupported extension component')
            if set(row)-{'type','text','icon','id','value','enabled'}:raise ValueError('Unsupported extension component property')
            for field in ('text','icon','id'):
                if field in row and (not isinstance(row[field],str) or len(row[field])>512):raise ValueError('Invalid extension text')
            if row.get('icon') and not __import__('re').fullmatch(r'[a-z0-9_]{1,64}',row['icon']):raise ValueError('Invalid extension icon')
            if 'enabled' in row and not isinstance(row['enabled'],bool):raise ValueError('Invalid extension enabled state')
            if row['type']=='progress' and (isinstance(row.get('value'),bool) or not isinstance(row.get('value'),(int,float)) or not 0<=row['value']<=1):raise ValueError('Invalid extension progress')
            if row['type']=='toggle' and not isinstance(row.get('value'),bool):raise ValueError('Invalid extension toggle')
            output.append(row)
        result['slots'][slot]=output
    return result

def sandbox_command(plugin):
    folder=Path(plugin['path']).resolve();worker=Path(plugin['worker']).resolve()
    if not worker.is_relative_to(folder):raise ValueError('Invalid worker path')
    data=STATE/'plugins'/plugin['id'];data.mkdir(parents=True,exist_ok=True,mode=0o700)
    if data.is_symlink():raise ValueError('Unsafe extension data directory')
    args=['bwrap','--die-with-parent','--new-session','--unshare-all','--cap-drop','ALL',
          '--ro-bind','/usr','/usr','--symlink','usr/lib','/lib','--symlink','usr/lib','/lib64',
          '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/home',
          '--ro-bind',str(folder),'/plugin','--bind',str(data),'/data','--chdir','/plugin',
          '--clearenv','--setenv','LANG','C.UTF-8','--setenv','HOME','/data','--setenv','PATH','/usr/bin',
          '--setenv','PYTHONDONTWRITEBYTECODE','1']
    if plugin.get('networkRequested') and plugin.get('networkGranted'):
        args+=['--share-net']
        for path in ('/etc/resolv.conf','/etc/ssl/certs','/etc/ca-certificates'):
            if Path(path).exists():args+=['--ro-bind',path,path]
    program='''import resource,runpy
resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))
resource.setrlimit(resource.RLIMIT_CPU,(60,60))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
resource.setrlimit(resource.RLIMIT_FSIZE,(16777216,16777216))
resource.setrlimit(resource.RLIMIT_NPROC,(1,1))
runpy.run_path(%r,run_name="__main__")
'''%('/plugin/'+str(worker.relative_to(folder)))
    return args+['/usr/bin/python3','-I','-u','-c',program]

def run(identifier):
    plugin=find(identifier)
    if not plugin.get('enabled') or not plugin.get('isolated'):raise ValueError('Extension is not enabled as an isolated worker')
    # Qt can crash without destroying child QProcesses. Keep workers tied to
    # their actual parent rather than the shell's process group.
    parent=os.getppid();ctypes.CDLL(None).prctl(1,signal.SIGTERM,0,0,0)
    if os.getppid()!=parent:return
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    process=subprocess.Popen(sandbox_command(plugin),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,start_new_session=True)
    try:
        process.stdin.write((json.dumps({'type':'init','settings':plugin.get('settings',{})})+'\n').encode())
        buffers={};times=collections.deque();stderr_size=0;first_state=False;deadline=time.monotonic()+10
        with selectors.DefaultSelector() as selector:
            for file in (sys.stdin.buffer,process.stdout,process.stderr):
                os.set_blocking(file.fileno(),False);selector.register(file,selectors.EVENT_READ);buffers[file]=b''
            while process.poll() is None:
                if not first_state and time.monotonic()>deadline:raise ValueError('Extension did not publish its initial state')
                for key,_ in selector.select(1):
                    file=key.fileobj;chunk=os.read(file.fileno(),8192)
                    if not chunk:
                        if file is sys.stdin.buffer:return
                        selector.unregister(file);continue
                    if file is process.stderr:
                        stderr_size+=len(chunk)
                        if stderr_size>16384:raise ValueError('Extension error output limit exceeded')
                        sys.stderr.buffer.write(chunk[:8192]);sys.stderr.flush();continue
                    buffers[file]+=chunk
                    if len(buffers[file])>65536:raise ValueError('Extension message limit exceeded')
                    while b'\n' in buffers[file]:
                        line,buffers[file]=buffers[file].split(b'\n',1)
                        value=json.loads(line)
                        if file is process.stdout:
                            now=time.monotonic()
                            while times and times[0]<now-1:times.popleft()
                            if len(times)>=20:raise ValueError('Extension update rate exceeded')
                            times.append(now);first_state=True;print(json.dumps(validate_state(value)),flush=True)
                        else:
                            if not isinstance(value,dict) or value.get('type')!='action' or not isinstance(value.get('id'),str) or len(value['id'])>512:raise ValueError('Invalid extension action')
                            payload=(json.dumps(value)+'\n').encode()
                            if len(payload)>8192:raise ValueError('Extension action is too large')
                            process.stdin.write(payload)
            if process.returncode:raise ValueError('Isolated extension exited with status '+str(process.returncode))
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':
    try:run(sys.argv[1])
    except Exception as error:print(str(error),file=sys.stderr);sys.exit(1)
