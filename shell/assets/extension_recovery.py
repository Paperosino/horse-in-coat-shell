"""Detect an interrupted shell without executing third-party extension code."""
import json,os,time
from pathlib import Path
from feature_common import CONFIG,STATE,read_json,atomic_json
MARKER=STATE/'extension-session.json'

def begin():
    previous=read_json(MARKER)
    try:boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:boot=''
    interrupted=previous and not previous.get('clean',True) and (previous.get('exitCode') is not None or previous.get('boot')==boot)
    if interrupted or os.environ.get('HICS_SAFE_MODE')=='1':
        prefs=read_json(CONFIG/'plugins.json')
        prefs['recoveryMode']=True;prefs['recoveryAllow']={}
        prefs['recoveryReason']='The previous shell exited unexpectedly' if interrupted else 'Recovery mode requested'
        atomic_json(CONFIG/'plugins.json',prefs)
    atomic_json(MARKER,{'clean':False,'boot':boot,'started':int(time.time()),'pid':os.getpid()})

def finish(exit_code=0):
    record=read_json(MARKER);record.update(clean=exit_code==0,exitCode=exit_code,ended=int(time.time()))
    atomic_json(MARKER,record)
