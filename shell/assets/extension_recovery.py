"""Detect an interrupted shell without executing third-party extension code."""
import json,os,sys,time
from pathlib import Path
from feature_common import CONFIG,STATE,atomic_json
from shell_recovery import read as read_recovery
from plugin_preferences import load as load_preferences
MARKER=STATE/'extension-session.json'

def marker():
    try:
        record=read_recovery(MARKER)
        if record and (type(record.get('clean')) is not bool or not isinstance(record.get('boot'),str)
                       or record.get('exitCode') is not None and type(record['exitCode']) is not int):
            raise ValueError('Invalid extension session marker')
        return record
    except (OSError,ValueError):
        # Unreadable crash evidence must not permit third-party code to run.
        return {'clean':False,'exitCode':1}


def begin():
    previous=marker()
    try:boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:boot=''
    interrupted=previous and not previous.get('clean',True) and (previous.get('exitCode') is not None or previous.get('boot')==boot)
    if interrupted or os.environ.get('HICS_SAFE_MODE')=='1':
        try:prefs=load_preferences(CONFIG/'plugins.json')
        except ValueError as error:
            # The catalogue also fails closed; do not overwrite damaged settings.
            print(str(error),file=sys.stderr)
        else:
            prefs['recoveryMode']=True;prefs['recoveryAllow']={}
            prefs['recoveryReason']='The previous shell exited unexpectedly' if interrupted else 'Recovery mode requested'
            atomic_json(CONFIG/'plugins.json',prefs)
    atomic_json(MARKER,{'clean':False,'boot':boot,'started':int(time.time()),'pid':os.getpid()})

def finish(exit_code=0):
    record=marker();record.update(clean=exit_code==0,exitCode=exit_code,ended=int(time.time()))
    atomic_json(MARKER,record)
