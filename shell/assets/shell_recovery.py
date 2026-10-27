"""Bounded crash-loop protection; idle sessions do not poll or spawn helpers."""
from __future__ import annotations
import json, math, os, stat, subprocess, sys, time
from pathlib import Path
from feature_common import CONFIG, STATE, atomic_json

RECORD = STATE / 'shell-recovery.json'
GOOD = STATE / 'shell-startup-good.json'
CORE = ('shell.json', 'shell-tokens.json', 'dock.json', 'panels.json', 'effects.json')
LIMIT = 8 * 1024 * 1024


def strict_object(text):
    value=json.loads(text,parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite recovery value')))
    if not isinstance(value,dict):raise ValueError('Invalid recovery record')
    return value


def read(path, default=None):
    # Nonblocking open rejects FIFOs without waiting; no-follow also closes the
    # symlink race between checking a record and opening it.
    try:descriptor=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    except FileNotFoundError:return {} if default is None else default
    with os.fdopen(descriptor,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size>LIMIT:
            raise ValueError('Recovery record is not a bounded regular file')
        text=stream.read(LIMIT+1)
        if len(text)>LIMIT:raise ValueError('Recovery record is too large')
    return strict_object(text)


def boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def begin(now=None):
    now = time.monotonic() if now is None else now
    try: previous = read(RECORD)
    except (OSError, ValueError): previous = {}
    same = previous.get('boot') == boot() and previous.get('session') == os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
    stamps=previous.get('failures',[])
    failures = [stamp for stamp in stamps if type(stamp) in (int,float) and math.isfinite(stamp) and 0 <= now-stamp <= 120][-7:] if same and isinstance(stamps,list) else []
    if same and previous.get('active'): failures.append(now)
    safe = bool(previous.get('requested')) or len(failures) >= 2 or os.environ.get('HICS_SAFE_MODE') == '1'
    record = dict(boot=boot(), session=os.environ.get('HYPRLAND_INSTANCE_SIGNATURE',''), active=True,
                  failures=failures[-8:], started=now, safe=safe, requested=bool(previous.get('requested')))
    atomic_json(RECORD, record, private=True)
    return safe


def finish(code, now=None):
    now = time.monotonic() if now is None else now
    record = read(RECORD)
    record['active'] = False
    if code and not record.get('safe'):
        record['failures'] = [stamp for stamp in record.get('failures', []) if 0 <= now-stamp <= 120][-7:] + [now]
    atomic_json(RECORD, record, private=True)


def candidate():
    files = {}
    total = 0
    for name in CORE:
        path = CONFIG/name
        if path.is_symlink(): raise ValueError('Symlinked startup configuration: '+name)
        if not path.exists(): files[name] = '{}'; continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024*1024:
            raise ValueError('Unsupported startup configuration: '+name)
        text = path.read_text(); total += len(text.encode())
        if total > 2*1024*1024 or not isinstance(json.loads(text,parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite configuration value'))),dict): raise ValueError('Invalid startup configuration: '+name)
        files[name] = text
    return files


def healthy(files):
    # A checkpoint belongs to the configuration that actually started, not to
    # edits made while waiting for the startup acknowledgement.
    preview=STATE/'configuration-preview.json'
    if preview.exists() or files != candidate() or preview.exists(): return False
    atomic_json(GOOD, dict(version=1, created=time.time(), files=files), private=True)
    return True


def good(path=None):
    saved = read(path or GOOD)
    if not saved: return {}
    files = saved.get('files')
    if saved.get('version') != 1 or not isinstance(files,dict) or set(files) != set(CORE): raise ValueError('Invalid startup checkpoint')
    for name,text in files.items():
        if not isinstance(text,str) or len(text.encode()) > 1024*1024 or not isinstance(strict_object(text),dict): raise ValueError('Invalid checkpoint section: '+name)
    return saved


def command(action):
    if action in ('on','resume'):
        record = read(RECORD)
        record.update(requested=action=='on', active=False, failures=[])
        atomic_json(RECORD,record,private=True)
        subprocess.run(['systemctl','--user','reset-failed','hic-session.service'],check=True,timeout=8,capture_output=True)
        subprocess.run(['systemctl','--user','--no-block','restart','hic-session.service'],check=True,timeout=8,capture_output=True)
        return {'restarting':True}
    from configuration_manager import request
    if action == 'restore': return request('restore-startup',{})
    if action == 'mark': return request('mark-startup',{})
    if action == 'status':
        data = request('status',{})
        return {**data, 'safeMode':read(RECORD).get('safe',False)}
    raise ValueError('Unknown recovery action')


if __name__ == '__main__':
    try:
        result=command(sys.argv[1] if len(sys.argv)==2 else 'status')
        print(json.dumps(result));sys.exit(1 if result.get('error') else 0)
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print(json.dumps({'error':str(error)}));sys.exit(1)
