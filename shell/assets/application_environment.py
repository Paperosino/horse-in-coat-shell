"""Keep the shell's bundled libraries out of external application processes."""
import os
from pathlib import Path

def application_environment(environment=None):
    env=dict(os.environ if environment is None else environment)
    data=env.get('XDG_DATA_HOME',str(Path(env.get('HOME',str(Path.home())))/'.local/share'))
    roots=['/usr/share/hics','/usr/share/hyprstack',data+'/hics',data+'/hyprstack']
    configured=env.get('HICS_DATA_DIR',env.get('HYPRSTACK_DATA_DIR'))
    if configured:roots.append(configured)
    prefixes=[os.path.normpath(root+'/'+suffix) for root in roots for suffix in ('qs','qml','lib')]
    for key in ('LD_LIBRARY_PATH','LD_PRELOAD','QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QML_IMPORT_PATH','QML2_IMPORT_PATH'):
        if key not in env:continue
        kept=[entry for entry in env[key].split(':') if entry and not any(os.path.normpath(entry)==p or os.path.normpath(entry).startswith(p+'/') for p in prefixes)]
        if kept:env[key]=':'.join(kept)
        else:env.pop(key,None)
    return env
