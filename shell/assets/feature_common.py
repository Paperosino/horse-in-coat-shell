"""Shared storage for desktop features. All paths are user-owned."""
from __future__ import annotations
import json, os, tempfile, subprocess
from pathlib import Path
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'hics'
STATE = Path(os.environ.get('XDG_STATE_HOME', Path.home()/'.local/state'))/'hics'
DATA = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'hics'
def read_json(path, default=None):
    fallback = {} if default is None else default
    try:
        value = json.loads(Path(path).read_text())
        return value if isinstance(value, type(fallback)) else fallback
    except (OSError, ValueError): return fallback

def atomic_json(path, value, private=False):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name)
    try:
        with os.fdopen(fd,'w') as f: json.dump(value,f,ensure_ascii=False,indent=2); f.write('\n')
        os.chmod(tmp,0o600 if private else 0o644); os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def run(argv, timeout=15, check=True):
    p=subprocess.run(argv,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode: raise ValueError((p.stderr or p.stdout or f'{argv[0]} failed').strip()[:1500])
    return p.stdout.strip()

def output(value): print(json.dumps(value,ensure_ascii=False),flush=True)

def lua(value):
    if isinstance(value,bool): return 'true' if value else 'false'
    if isinstance(value,(float,int)): return str(value)
    if isinstance(value,(list,tuple)): return "{"+",".join(lua(v) for v in value)+"}"
    if isinstance(value,dict): return '{'+','.join('['+json.dumps(k)+']='+lua(v) for k,v in value.items())+'}'
    return json.dumps(str(value),ensure_ascii=False)
