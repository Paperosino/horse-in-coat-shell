"""Prepare a separate HICS desktop session without replacing another WM setup."""
import json, os, sys, tempfile
from pathlib import Path


def copy_missing(source, target):
    if os.path.lexists(target):return
    if source.stat().st_size>1024*1024:raise ValueError('Session default is too large')
    content=source.read_bytes()
    target.parent.mkdir(parents=True,exist_ok=True)
    descriptor, temporary=tempfile.mkstemp(prefix='.hics-bootstrap-',dir=target.parent)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        # Publish complete contents without replacing a file another startup
        # or the user created concurrently. A killed copy never leaves a partial target.
        try:os.link(temporary,target,follow_symlinks=False)
        except FileExistsError:pass
    finally:
        Path(temporary).unlink(missing_ok=True)


def prepare(data, config):
    data=Path(data).resolve();config=Path(config)
    if not config.is_absolute():raise ValueError('XDG_CONFIG_HOME must be absolute')
    shipped=data/'shell/assets/hyprland/config'
    if not (shipped/'hyprland.lua').is_file() or not (data/'defaults/hics/hypr-user.lua').is_file():
        raise ValueError('HICS session defaults are missing; reinstall the package')
    legacy=config/'hypr/hyprland.lua'
    # Preserve a pre-existing HICS installation, including local monitor rules.
    try:text=legacy.read_text() if legacy.is_file() and legacy.stat().st_size<=1024*1024 else ''
    except (OSError,UnicodeError):text=''
    managed_legacy=all(marker in text for marker in ('hics_shortcuts','require("hypr-user")','require("hyprland.execs")'))
    directory=config/'hypr' if managed_legacy else config/'hics/hypr'
    for source in sorted((data/'defaults/hics').iterdir()):
        if source.is_file():copy_missing(source,config/'hics'/source.name)
    # Keep the watched entrypoint outside pacman's replacement transaction.
    # A removed package-owned root could otherwise trigger a partial reload
    # and leave a persistent config error in a running compositor.
    copy_missing(shipped/'hyprland.lua',directory/'hyprland.lua')
    copy_missing(shipped/'scheme/default.lua',directory/'scheme/current.lua')
    return {
        'HICS_DATA_DIR':str(data),'HYPRSTACK_DATA_DIR':str(data),
        'HICS_HYPR_CONFIG_DIR':str(directory),
        'XDG_CURRENT_DESKTOP':'HICS:Hyprland','XDG_SESSION_DESKTOP':'hics','XDG_SESSION_TYPE':'wayland',
    }, legacy if managed_legacy else directory/'hyprland.lua'


def main():
    if os.geteuid()==0:raise ValueError('Start HICS as your regular desktop user')
    if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE') and sys.argv[1:]!=['--prepare']:raise ValueError('A compositor is already running in this environment')
    if sys.argv[1:] not in ([],['--prepare']):raise ValueError('Usage: hics-start [--prepare]')
    data=os.environ.get('HICS_DATA_DIR',os.environ.get('HYPRSTACK_DATA_DIR','/usr/share/hics'))
    env,configuration=prepare(data,Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config')))
    os.environ.update(env)
    if sys.argv[1:]==['--prepare']:
        print(json.dumps({'environment':env,'configuration':str(configuration)}));return
    os.execvp('start-hyprland',['start-hyprland','--','--config',str(configuration)])


if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as error:
        print('hics-start: '+str(error),file=sys.stderr);sys.exit(1)
