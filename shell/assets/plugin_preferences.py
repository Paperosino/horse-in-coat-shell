"""Strict bounded extension preferences; failed reads never authorize writes."""
from shell_recovery import read_text, strict_object


def load(path):
    try:
        try: text=read_text(path,8*1024*1024)
        except FileNotFoundError:return {}
        prefs=strict_object(text)
        for key in ('enabled','recoveryAllow','settings','desktopLayout','permissions','faults'):
            if key in prefs and not isinstance(prefs[key],dict):raise ValueError('Invalid mapping')
        for key in ('enabled','recoveryAllow'):
            if any(type(value) is not bool for value in prefs.get(key,{}).values()):raise ValueError('Invalid switch')
        for key in ('settings','desktopLayout','permissions'):
            if any(not isinstance(value,dict) for value in prefs.get(key,{}).values()):raise ValueError('Invalid extension mapping')
        if any(not isinstance(value,list) for value in prefs.get('faults',{}).values()):raise ValueError('Invalid fault history')
        if 'recoveryMode' in prefs and type(prefs['recoveryMode']) is not bool:raise ValueError('Invalid recovery switch')
        return prefs
    except (OSError,ValueError) as error:
        raise ValueError('Cannot read extension settings (plugins.json). The file was preserved; restore a valid configuration before saving changes.') from error
