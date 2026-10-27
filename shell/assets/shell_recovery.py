"""Bounded crash-loop protection; idle sessions do not poll or spawn helpers."""
from __future__ import annotations
import errno, json, os, stat, subprocess, sys, time
from pathlib import Path
from feature_common import CONFIG, STATE, atomic_json

RECORD = STATE / 'shell-recovery.json'
GOOD = STATE / 'shell-startup-good.json'
CORE = ('shell.json', 'shell-tokens.json', 'dock.json', 'panels.json', 'effects.json')
LIMIT = 8 * 1024 * 1024


def strict_object(text):
    try:value=json.loads(text,parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite recovery value')))
    except RecursionError as error:raise ValueError('JSON nesting limit exceeded') from error
    if not isinstance(value,dict):raise ValueError('Invalid recovery record')
    stack=[iter(value.values())]
    while stack:
        try:child=next(stack[-1])
        except StopIteration:stack.pop();continue
        if isinstance(child,(dict,list)):
            if len(stack)>=128:raise ValueError('JSON nesting limit exceeded')
            stack.append(iter(child.values()) if isinstance(child,dict) else iter(child))
    return value


def read_text(path, limit):
    # Validate the opened inode, not a path that can change before read().
    try:descriptor=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    except OSError as error:
        if error.errno==errno.ELOOP:raise ValueError("Symlinked recovery configuration") from error
        raise
    with os.fdopen(descriptor,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size>limit:
            raise ValueError('Recovery record is not a bounded regular file')
        text=stream.read(limit+1)
        if len(text)>limit:raise ValueError('Recovery record is too large')
    return text.decode('utf-8')


def read(path, default=None):
    try:return strict_object(read_text(path,LIMIT))
    except FileNotFoundError:return {} if default is None else default


def boot():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def recent_failures(record, now):
    stamps=record.get('failures',[])
    if not isinstance(stamps,list):return []
    return [stamp for stamp in stamps if type(stamp) in (int,float) and now-120 <= stamp <= now][-7:]


def begin(now=None):
    now = time.monotonic() if now is None else now
    try: previous = read(RECORD)
    except (OSError, ValueError): previous = {}
    same = previous.get('boot') == boot() and previous.get('session') == os.environ.get('HYPRLAND_INSTANCE_SIGNATURE', '')
    failures = recent_failures(previous,now) if same else []
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
        record['failures'] = recent_failures(record,now) + [now]
    atomic_json(RECORD, record, private=True)


def candidate():
    files = {}
    total = 0
    for name in CORE:
        path = CONFIG/name
        try:text=read_text(path,1024*1024)
        except FileNotFoundError:files[name]='{}';continue
        total += len(text.encode())
        if total > 2*1024*1024:raise ValueError('Startup configuration is too large')
        strict_object(text)
        files[name] = text
    return files


def healthy(files):
    # A checkpoint belongs to the configuration that actually started, not to
    # edits made while waiting for the startup acknowledgement.
    preview=STATE/'configuration-preview.json'
    if preview.exists() or preview.is_symlink() or files != candidate() or preview.exists() or preview.is_symlink(): return False
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
        # Only the process owning the lock can decide to exit safely. A remote
        # isLocked check followed by systemctl restart has a TOCTOU window.
        data=Path(os.environ.get('HICS_DATA_DIR',os.environ.get('HYPRSTACK_DATA_DIR','/usr/share/hics')))
        reply=None
        normal=Path(os.environ.get('HICS_SHELL_DIR',os.environ.get('HYPRSTACK_SHELL_DIR',str(data/'shell'))))
        for root in (normal,data/'shell/recovery'):
            reply=subprocess.run([str(data/'qs/bin/hics-qs'),'ipc','-p',str(root),
                              'call','sessionControl','transition',action],
                             timeout=4,capture_output=True,text=True)
            if reply.returncode==0:break
        if reply.returncode:raise ValueError('The shell does not support a coordinated mode change. Log out and back in after updating HICS.')
        if reply.stdout.strip()!='true':raise ValueError('Unlock the session before changing shell mode, or start the session service if it is stopped.')
        return {'restarting':True}
    from configuration_manager import request
    if action == 'restore': return request('restore-startup',{})
    if action == 'mark': return request('mark-startup',{})
    if action == 'status':
        data = request('status',{})
        try: record = read(RECORD)
        except (OSError, ValueError):
            # Keep the independent configuration guard usable even when the
            # crash counter cannot be read. Do not repair storage on a read.
            return {**data, 'safeMode':False, 'recoveryWarning':'; '.join(filter(None,[data.get('recoveryWarning',''), 'Shell crash journal is unreadable; safe-mode state is unknown.']))}
        return {**data, 'safeMode':record.get('safe',False)}
    raise ValueError('Unknown recovery action')


if __name__ == '__main__':
    try:
        result=command(sys.argv[1] if len(sys.argv)==2 else 'status')
        print(json.dumps(result));sys.exit(1 if result.get('error') else 0)
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print(json.dumps({'error':str(error)}));sys.exit(1)
