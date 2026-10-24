"""Display profiles and crash-resistant preview transactions, tied to one compositor.

The watchdog is independent of Quickshell. Preview never writes monitors.lua;
only explicit confirmation commits the managed block.
"""
from __future__ import annotations
import argparse, collections, fcntl, hashlib, json, math, os, re, selectors, signal, socket, subprocess, sys, tempfile, time, uuid
from pathlib import Path
from feature_common import CONFIG, atomic_json, read_json, output
from application_environment import application_environment

REGISTRY = CONFIG / 'display-profiles.json'
MONITOR_CONFIG = CONFIG / 'monitors.lua'
START = '-- Hyprstack display settings: start'
END = '-- Hyprstack display settings: end'
PORT = re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')
MODE = re.compile(r'^(\d{2,5})x(\d{2,5})@(\d+(?:\.\d+)?)$')

def paths():
    signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
    if not signature or '/' in signature or len(signature)>256:
        raise ValueError('A running Hyprland session is required')
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/'+str(os.getuid())))
    folder = runtime / ('hics-displays-'+hashlib.sha256(signature.encode()).hexdigest()[:16])
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.is_symlink() or folder.stat().st_uid != os.getuid():
        raise ValueError('Unsafe display runtime directory')
    return folder, runtime/'hypr'/signature/'.socket2.sock'

def ctl(*args):
    result = subprocess.run(['hyprctl', *args], env=application_environment(), capture_output=True, text=True, timeout=8)
    if result.returncode or result.stdout.lstrip().lower().startswith(('error', 'invalid')):
        raise ValueError((result.stderr or result.stdout or 'Hyprland rejected display settings').strip()[:2000])
    return result.stdout

def connected():
    result = json.loads(ctl('monitors', 'all', '-j'))
    if not isinstance(result, list) or len(result)>64:
        raise ValueError('Invalid monitor response')
    return [m for m in result if isinstance(m, dict) and PORT.fullmatch(str(m.get('name', '')))]

def device(m):
    return {k:str(m.get(k, ''))[:512] for k in ('name','make','model','serial','description')}

def identity(m, ports=False):
    serial = str(m.get('serial','')).strip()
    if serial.lower() in ('','unknown','none','0','0x00000000'): serial = ''
    key = [str(m.get('make','')), str(m.get('model','')), serial]
    if not any(key): key = [str(m.get('description','')) or str(m['name'])]
    if ports: key.append(m['name'])
    return json.dumps(key, ensure_ascii=False)

def topology(monitors, ports=False):
    return '|'.join(sorted(identity(m,ports) for m in monitors))

def map_outputs(profile, monitors, ports=False):
    if collections.Counter(identity(m,ports) for m in profile['devices']) != collections.Counter(identity(m,ports) for m in monitors):
        raise ValueError('This profile needs a different set of connected displays')
    remaining = list(monitors); mapping = {}
    for saved in profile['devices']:
        choices = [m for m in remaining if identity(m,ports)==identity(saved,ports)]
        exact = next((m for m in choices if m['name']==saved['name']), None)
        if not exact and len(choices)!=1:
            raise ValueError('Identical displays cannot be distinguished; keep their connector assignments')
        chosen = exact or choices[0]; remaining.remove(chosen); mapping[saved['name']] = chosen['name']
    result=[]
    for item in profile['outputs']:
        row=dict(item,name=mapping[item['name']])
        if row.get('mirror'): row['mirror']=mapping.get(row['mirror'],row['mirror'])
        result.append(row)
    return result

def capture(monitors):
    rows=[]
    for m in monitors:
        rate=float(m.get('refreshRate') or 60)
        row=dict(name=m['name'],mode=f"{m.get('width',1920)}x{m.get('height',1080)}@{rate:.6f}".rstrip('0').rstrip('.'),
                 x=int(m.get('x',0)),y=int(m.get('y',0)),scale=float(m.get('scale') or 1),transform=int(m.get('transform',0)),disabled=bool(m.get('disabled',False)))
        if row['disabled'] or not m.get('width'): row['mode']='preferred'
        if isinstance(m.get('vrr'),(bool,int)): row['vrr']=int(m['vrr'])
        if PORT.fullmatch(str(m.get('mirrorOf',''))) and m['mirrorOf']!='none': row['mirror']=m['mirrorOf']
        rows.append(row)
    return rows

def validate(rows, monitors, check_modes=True):
    if not isinstance(rows,list) or not rows or len(rows)>64: raise ValueError('Invalid display layout')
    available={m['name']:m for m in monitors}; seen=set(); result=[]; rectangles=[]
    for raw in rows:
        if not isinstance(raw,dict) or set(raw)-{'name','mode','x','y','scale','transform','vrr','disabled','mirror'}: raise ValueError('Unknown display setting')
        row=dict(raw);name=row.get('name')
        if name not in available or name in seen: raise ValueError('A display disappeared or is listed twice')
        seen.add(name)
        if not isinstance(row.get('disabled',False),bool): raise ValueError('Invalid display enabled state')
        for field,low,high in (('x',-1000000,1000000),('y',-1000000,1000000),('transform',0,7),('vrr',-1,3)):
            if field not in row: continue
            if isinstance(row[field],bool) or not isinstance(row[field],int) or not low<=row[field]<=high: raise ValueError('Invalid display '+field)
        scale=row.get('scale',1)
        if isinstance(scale,bool) or not isinstance(scale,(int,float)) or not math.isfinite(scale) or not .5<=scale<=4: raise ValueError('Invalid display scale')
        mode=row.get('mode','preferred');match=MODE.fullmatch(str(mode))
        if mode!='preferred' and (not match or not 16<=int(match[1])<=16384 or not 16<=int(match[2])<=16384 or not 1<=float(match[3])<=1000): raise ValueError('Invalid display mode')
        if row.get('mirror') and (row['mirror'] not in available or row['mirror']==name): raise ValueError('Invalid mirror display')
        if match and not row.get('disabled',False):
            w,h,rate=int(match[1]),int(match[2]),float(match[3])
            advertised=[MODE.fullmatch(str(s).removesuffix('Hz')) for s in available[name].get('availableModes',[])]
            if check_modes and advertised and not any(m and int(m[1])==w and int(m[2])==h and abs(float(m[3])-rate)<.25 for m in advertised): raise ValueError('The selected display mode is unavailable')
            if any(abs(size/scale-round(size/scale))>.02 for size in (w,h)): raise ValueError('Scale must produce whole logical pixels')
            if row.get('transform',0) in (1,3,5,7):w,h=h,w
            if not row.get('mirror'):rectangles.append((row.get('x',0),row.get('y',0),w/scale,h/scale))
        result.append(row)
    if not any(not row.get('disabled',False) for row in result): raise ValueError('At least one display must remain enabled')
    # Outputs omitted by a partial manual patch stay enabled and are included by callers.
    for i,a in enumerate(rectangles):
        for b in rectangles[i+1:]:
            if min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0])>.5 and min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1])>.5: raise ValueError('Displays must not overlap')
    return result

def lua(row):
    fields={'output':row['name'],'mode':row.get('mode','preferred'),'position':f"{row.get('x',0)}x{row.get('y',0)}",'scale':row.get('scale',1),'transform':row.get('transform',0),'disabled':row.get('disabled',False)}
    for key in ('vrr','mirror'):
        if key in row:fields[key]=row[key]
    return '{ '+', '.join(k+' = '+json.dumps(v,ensure_ascii=False) for k,v in fields.items())+' }'

def apply_outputs(rows):
    # Enable target outputs before disabling any old ones.
    ordered=sorted(rows,key=lambda r:r.get('disabled',False))
    reply=ctl('eval',';'.join('hl.monitor('+lua(row)+')' for row in ordered))
    if reply.strip() not in ('ok',''):raise ValueError(reply.strip()[:2000])

def config_hash():
    return hashlib.sha256(MONITOR_CONFIG.read_bytes() if MONITOR_CONFIG.exists() else b'').hexdigest()

def write_config(rows):
    existing=MONITOR_CONFIG.read_text() if MONITOR_CONFIG.exists() else ''
    managed=START+'\n-- Generated by hics Display settings.\n'+'\n'.join('hl.monitor('+lua(row)+')' for row in rows)+'\n'+END+'\n'
    start,end=existing.find(START),existing.find(END)
    if (start<0)!=(end<0) or start>=0 and end<=start:raise ValueError('The managed display configuration block is damaged')
    if start>=0:
        begin=existing.rfind('\n',0,start)+1;finish=existing.find('\n',end)
        text=existing[:begin]+managed+(existing[finish+1:] if finish>=0 else '')
    else:text=existing+('\n' if existing and not existing.endswith('\n') else '')+managed
    MONITOR_CONFIG.parent.mkdir(parents=True,exist_ok=True)
    fd,path=tempfile.mkstemp(dir=MONITOR_CONFIG.parent,prefix='.monitors-')
    try:
        with os.fdopen(fd,'w') as file:file.write(text);file.flush();os.fsync(file.fileno())
        os.chmod(path,MONITOR_CONFIG.stat().st_mode&0o777 if MONITOR_CONFIG.exists() else 0o644)
        os.replace(path,MONITOR_CONFIG)
    finally:
        if os.path.exists(path):os.unlink(path)

class Manager:
    def __init__(self,folder):
        self.folder=folder;self.pending=None;self.deadline=0;self.monitors=connected();self.error='';self.notice='';self.active=''
        self.registry=read_json(REGISTRY,{'version':1,'settings':{},'profiles':[]})
        if self.registry.get('version')!=1 or not isinstance(self.registry.get('profiles'),list):raise ValueError('Invalid display profile registry')
        self.registry.setdefault('settings',{});self.registry.setdefault('preferred',{})
        if len(self.registry['profiles'])>64:raise ValueError('Too many display profiles')
        for profile in self.registry['profiles']:
            if not isinstance(profile,dict) or not isinstance(profile.get('devices'),list) or not profile['devices'] or len(profile['devices'])>64:raise ValueError('Invalid saved display profile')
            if not isinstance(profile.get('id'),str) or not isinstance(profile.get('name'),str):raise ValueError('Invalid saved display profile')
            if any(not isinstance(m,dict) or not PORT.fullmatch(str(m.get('name',''))) for m in profile['devices']):raise ValueError('Invalid saved display identity')
            validate(profile.get('outputs'),profile['devices'],False)
        self.settings={'autoApply':True,'timeout':15,'matchPorts':False,**self.registry['settings']}
        if not isinstance(self.settings['autoApply'],bool) or not isinstance(self.settings['matchPorts'],bool) or isinstance(self.settings['timeout'],bool) or not isinstance(self.settings['timeout'],int) or not 10<=self.settings['timeout']<=60:raise ValueError('Invalid display protection settings')
        self.attempt=read_json(folder/'automatic.json').get('attempt','')
        previous=read_json(folder/'pending.json')
        if previous:
            self.pending=previous;self.rollback('Display changes were reverted after the display service restarted')
        self.publish()
    def publish(self):
        profiles=[];active_candidates=[]
        for p in self.registry['profiles']:
            row=dict(p)
            try:map_outputs(p,self.monitors,self.settings['matchPorts']);row['matches']=True
            except (ValueError,KeyError):row['matches']=False
            row['preferred']=self.registry['preferred'].get(topology(p['devices'],self.settings['matchPorts']))==p['id']
            if row['matches'] and same_layout(map_outputs(p,self.monitors,self.settings['matchPorts']),capture(self.monitors)):active_candidates.append((p['id'],row['preferred']))
            profiles.append(row)
        if not self.pending and self.active not in [p[0] for p in active_candidates]:
            self.active=next((p[0] for p in active_candidates if p[1]),active_candidates[0][0] if len(active_candidates)==1 else '')
        state={'revision':time.time_ns(),'statePath':str(self.folder/'state.json'),'settings':self.settings,'profiles':profiles,'connected':[device(m) for m in self.monitors],
               'pending':{k:self.pending[k] for k in ('token','label','deadline','profileId','automatic')} if self.pending else None,
               'error':self.error,'notice':self.notice,'activeProfileId':self.active}
        atomic_json(self.folder/'state.json',state,private=True)
        return state
    def save_registry(self):
        self.registry['settings']=self.settings;atomic_json(REGISTRY,self.registry,private=True)
    def find(self,identifier):
        profile=next((p for p in self.registry['profiles'] if p['id']==identifier),None)
        if not profile:raise ValueError('Display profile not found')
        return profile
    def start(self,rows,label='',profile_id='',automatic=False):
        if self.pending:raise ValueError('Confirm or revert the current display changes first')
        self.monitors=connected();rows=validate(rows,self.monitors);self.error=''
        if not automatic:
            self.attempt=topology(self.monitors,True);atomic_json(self.folder/'automatic.json',{'attempt':self.attempt},private=True)
        timeout=self.settings['timeout'];now=time.time()
        self.pending=dict(token=str(uuid.uuid4()),label=label,profileId=profile_id,automatic=automatic,deadline=now+timeout,
                          before=capture(self.monitors),devices=[device(m) for m in self.monitors],outputs=rows,configHash=config_hash())
        self.deadline=time.monotonic()+timeout
        atomic_json(self.folder/'pending.json',self.pending,private=True);self.publish()
        try:
            apply_outputs(rows)
            self.deadline=time.monotonic()+timeout;self.pending['deadline']=time.time()+timeout
            atomic_json(self.folder/'pending.json',self.pending,private=True);self.publish()
        except Exception:
            self.rollback('Display changes could not be applied');raise
    def rollback(self,reason='Display changes were reverted'):
        pending=self.pending
        if not pending:return
        live=connected();names={m['name'] for m in live}
        previous={m['name']:identity(m) for m in pending['devices']}
        current={m['name']:identity(m) for m in live}
        rows=[dict(r) for r in pending['before'] if r['name'] in names and previous.get(r['name'])==current.get(r['name'])]
        # Do not disable the last remaining output if a cable was unplugged.
        if not any(not r.get('disabled',False) for r in rows) and live:
            candidate=next((m for m in live if not m.get('disabled')),live[0])
            rows=[r for r in rows if r['name']!=candidate['name']]+[dict(name=candidate['name'],mode='preferred',scale=1,x=0,y=0,transform=0,disabled=False)]
        if rows:
            try:apply_outputs(rows)
            except Exception:
                if not live:raise
                apply_outputs([dict(name=live[0]['name'],mode='preferred',scale=1,x=0,y=0,transform=0,disabled=False)])
        self.pending=None;self.deadline=0;(self.folder/'pending.json').unlink(missing_ok=True)
        self.notice=reason;self.error='';self.monitors=connected();self.publish()
    def confirm(self,token):
        if not self.pending or token!=self.pending['token']:raise ValueError('This display confirmation has expired')
        if time.monotonic()>=self.deadline:self.rollback();raise ValueError('The display confirmation timer expired')
        if config_hash()!=self.pending['configHash']:self.rollback();raise ValueError('Display configuration changed elsewhere; preview was reverted')
        live=connected()
        if topology(live,True)!=topology(self.pending['devices'],True):self.rollback();raise ValueError('Connected displays changed; preview was reverted')
        if not same_layout(self.pending['outputs'],capture(live)):raise ValueError('The requested layout is not active yet; wait or revert the changes')
        write_config(self.pending['outputs']);self.active=self.pending['profileId']
        self.pending=None;self.deadline=0;(self.folder/'pending.json').unlink(missing_ok=True)
        self.notice='Display changes were kept';self.monitors=live
    def automatic(self):
        if self.pending or not self.settings['autoApply'] or not self.monitors:return
        key=topology(self.monitors,self.settings['matchPorts'])
        attempt=topology(self.monitors,True)
        if attempt==self.attempt:return
        self.attempt=attempt;atomic_json(self.folder/'automatic.json',{'attempt':attempt},private=True)
        matches=[]
        for p in self.registry['profiles']:
            if not p.get('autoApply',True):continue
            try:rows=map_outputs(p,self.monitors,self.settings['matchPorts']);validate(rows,self.monitors)
            except (ValueError,KeyError):continue
            matches.append((p,rows))
        preferred=self.registry['preferred'].get(key)
        selected=next((pair for pair in matches if pair[0]['id']==preferred),matches[0] if len(matches)==1 else None)
        if not selected:
            if len(matches)>1:self.notice='Several profiles match; choose a preferred profile for these displays'
            return
        p,rows=selected
        if same_layout(rows,capture(self.monitors)):self.active=p['id'];return
        self.start(rows,p['name'],p['id'],True)
    def refresh(self):
        live=connected()
        if self.pending and topology(live,True)!=topology(self.pending['devices'],True):self.rollback('Connected displays changed; display preview was reverted')
        self.monitors=live;self.automatic();self.publish()
    def dispatch(self,request):
        op=request.get('operation');value=request.get('value') or {};self.error=''
        if op=='status':self.monitors=connected()
        elif op=='confirm':self.confirm(value.get('token'))
        elif op=='revert':
            if not self.pending or value.get('token')!=self.pending['token']:raise ValueError('This display confirmation has expired')
            self.rollback()
        elif op=='preview':
            live=connected();rows=capture(live);patches=value.get('patches')
            if not isinstance(patches,dict) or set(patches)-{r['name'] for r in rows}:raise ValueError('A display disappeared before applying changes')
            for row in rows:
                patch=patches.get(row['name'],{})
                if not isinstance(patch,dict) or 'name' in patch:raise ValueError('Invalid display patch')
                row.update(patch)
            self.start(rows)
        elif op=='apply':
            p=self.find(value.get('id'));self.start(map_outputs(p,connected(),self.settings['matchPorts']),p['name'],p['id'])
        elif op=='save':
            if self.pending:raise ValueError('Confirm display changes before saving a profile')
            name=value.get('name','').strip()
            if not name or len(name)>128 or any(ord(c)<32 for c in name):raise ValueError('Enter a valid profile name')
            self.monitors=connected();rows=validate(capture(self.monitors),self.monitors)
            p=dict(id=str(uuid.uuid4()),name=name,devices=[device(m) for m in self.monitors],outputs=rows,autoApply=True,updated=int(time.time()))
            if len(self.registry['profiles'])>=64:raise ValueError('At most 64 display profiles are supported')
            self.registry['profiles'].append(p);key=topology(self.monitors,self.settings['matchPorts']);self.registry['preferred'][key]=p['id'];self.active=p['id'];self.save_registry()
        elif op=='update':
            p=self.find(value.get('id'));changes=value.get('changes',{})
            if not isinstance(changes,dict) or set(changes)-{'name','autoApply','preferred'}:raise ValueError('Invalid profile update')
            if 'name' in changes:
                name=changes['name'].strip()
                if not name or len(name)>128 or any(ord(c)<32 for c in name):raise ValueError('Enter a valid profile name')
                p['name']=name
            if 'autoApply' in changes:
                if not isinstance(changes['autoApply'],bool):raise ValueError('Expected an automatic profile switch')
                p['autoApply']=changes['autoApply']
            if changes.get('preferred'):self.registry['preferred'][topology(p['devices'],self.settings['matchPorts'])]=p['id']
            self.save_registry()
        elif op=='delete':
            if self.pending:raise ValueError('Confirm or revert the current display changes first')
            p=self.find(value.get('id'));self.registry['profiles'].remove(p)
            self.registry['preferred']={k:v for k,v in self.registry['preferred'].items() if v!=p['id']};self.save_registry()
            if self.active==p['id']:self.active=''
        elif op=='configure':
            if not isinstance(value,dict) or set(value)-{'autoApply','timeout','matchPorts'}:raise ValueError('Invalid display profile settings')
            for k,v in value.items():
                if k=='timeout':
                    if isinstance(v,bool) or not isinstance(v,int) or not 10<=v<=60:raise ValueError('Confirmation timeout must be between 10 and 60 seconds')
                elif not isinstance(v,bool):raise ValueError('Expected a display settings switch')
            self.settings.update(value);self.save_registry()
        else:raise ValueError('Unknown display profile operation')
        return self.publish()

def same_layout(first,second):
    indexed={r['name']:r for r in second}
    for row in first:
        current=indexed.get(row['name'])
        if not current:return False
        for key in ('disabled','x','y','transform'):
            if row.get(key,False if key=='disabled' else 0)!=current.get(key,False if key=='disabled' else 0):return False
        if row.get('disabled',False):continue
        if abs(row.get('scale',1)-current.get('scale',1))>.001:return False
        if row.get('mode')=='preferred':continue
        a,b=MODE.fullmatch(row.get('mode','')),MODE.fullmatch(current.get('mode',''))
        if bool(a)!=bool(b) or a and ((a[1],a[2])!=(b[1],b[2]) or abs(float(a[3])-float(b[3]))>.25):return False
    return True

def watch():
    folder,event_path=paths()
    with (folder/'watch.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        endpoint=folder/'control.sock';endpoint.unlink(missing_ok=True)
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server,socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as events:
            events.connect(str(event_path));server.bind(str(endpoint));os.chmod(endpoint,0o600);server.listen(8)
            manager=Manager(folder);refresh_at=time.monotonic()+1;event_buffer=b'';stopping=False
            def stop(*_):
                nonlocal stopping
                stopping=True
            signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
            with selectors.DefaultSelector() as selector:
                selector.register(server,selectors.EVENT_READ);selector.register(events,selectors.EVENT_READ)
                while not stopping:
                    now=time.monotonic()
                    if manager.pending and now>=manager.deadline:
                        try:manager.rollback('Display changes were automatically reverted')
                        except Exception as e:manager.error=str(e);manager.deadline=now+2;manager.publish()
                    if refresh_at and now>=refresh_at:
                        refresh_at=0
                        try:manager.refresh()
                        except Exception as e:manager.error=str(e);manager.publish()
                    deadlines=[t for t in (manager.deadline if manager.pending else 0,refresh_at) if t]
                    timeout=min(1,max(0,min(deadlines)-time.monotonic())) if deadlines else 1
                    for key,_ in selector.select(timeout):
                        if key.fileobj is events:
                            chunk=events.recv(65536)
                            if not chunk:return
                            event_buffer+=chunk
                            while b'\n' in event_buffer:
                                line,event_buffer=event_buffer.split(b'\n',1)
                                if line.startswith((b'monitoradded',b'monitorremoved',b'configreloaded')):refresh_at=time.monotonic()+.8
                        else:
                            with server.accept()[0] as client:
                                client.settimeout(2)
                                try:
                                    data=b''
                                    while b'\n' not in data:
                                        part=client.recv(16384)
                                        if not part:raise ValueError('Display client disconnected')
                                        data+=part
                                        if not data or len(data)>65536:raise ValueError('Display request is too large')
                                    request=json.loads(data.split(b'\n',1)[0]);reply=manager.dispatch(request)
                                except Exception as e:manager.error=str(e);reply=manager.publish()
                                try:client.sendall((json.dumps(reply,ensure_ascii=False)+'\n').encode())
                                except OSError:pass
            if manager.pending:manager.rollback('Display changes were reverted when the display service stopped')

def request(operation,value=None):
    folder,_=paths();endpoint=folder/'control.sock'
    def send():
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.settimeout(25);client.connect(str(endpoint));client.sendall((json.dumps({'operation':operation,'value':value})+'\n').encode());data=b''
            while b'\n' not in data:
                part=client.recv(65536)
                if not part:raise ValueError('Display service disconnected')
                data+=part
                if len(data)>4194304:raise ValueError('Display response is too large')
            return json.loads(data.split(b'\n',1)[0])
    try:return send()
    except (FileNotFoundError,ConnectionRefusedError):
        # An independent process survives shell reloads. The compositor socket
        # ends its lifetime; a lock prevents duplicate watchdogs during races.
        if not os.environ.get('HICS_DISPLAY_NO_SYSTEMD'):
            managed=subprocess.run(['systemctl','--user','start','hics-displays.service'],env=application_environment(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8,check=False)
            if managed.returncode==0:
                # Type=simple reports 'started' before Python has bound the
                # socket. Do not race the supervised service with a fallback.
                for _ in range(100):
                    try:return send()
                    except (FileNotFoundError,ConnectionRefusedError):time.sleep(.05)
                raise ValueError('Display protection service did not become ready')
        try:return send()
        except (FileNotFoundError,ConnectionRefusedError):pass
        subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'watch'],env=application_environment(),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        for _ in range(60):
            try:return send()
            except (FileNotFoundError,ConnectionRefusedError):time.sleep(.05)
        raise ValueError('Unable to start the display protection service')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['watch','status','preview','confirm','revert','save','update','delete','configure','apply']);args=parser.parse_args()
    try:
        if args.operation=='watch':watch();return 0
        value=json.load(sys.stdin) if args.operation!='status' else None
        result=request(args.operation,value);output(result);return 1 if result.get('error') else 0
    except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':sys.exit(main())
