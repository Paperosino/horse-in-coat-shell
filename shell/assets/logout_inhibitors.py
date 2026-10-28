"""Lifecycle model for session inhibitors; no D-Bus ownership or UI side effects.

Callers must pass the unique D-Bus owner, never a well-known name. The XDG
logout backend uses this model to own inhibition lifetimes.
"""
from dataclasses import dataclass
import re

LOGOUT = 1
SWITCH_USER = 2
SUSPEND = 4
IDLE = 8
VALID_FLAGS = LOGOUT | SWITCH_USER | SUSPEND | IDLE


@dataclass(frozen=True)
class Inhibitor:
    path: str
    owner: str
    app_id: str
    reason: str
    flags: int
    process_name: str = ''


class InhibitorRegistry:
    def __init__(self, limit=256):
        if type(limit) is not int or not 1 <= limit <= 4096:
            raise ValueError('Invalid inhibitor limit')
        self._limit = limit
        self._entries = {}
        self._generation = 0

    @property
    def generation(self):
        return self._generation

    def add(self, path, owner, app_id, reason, flags, process_name=''):
        if not isinstance(path,str) or len(path)>512 or not re.fullmatch(r'/org/freedesktop/portal/desktop/request/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)+',path):
            raise ValueError('Invalid request path')
        if not isinstance(owner,str) or len(owner)>255 or not re.fullmatch(r':[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',owner):
            raise ValueError('A unique D-Bus owner is required')
        if not isinstance(app_id,str) or not isinstance(reason,str) or not isinstance(process_name,str) or len(app_id)>512 or len(reason)>4096 or len(process_name)>255:
            raise ValueError('Invalid inhibitor description')
        if type(flags) is not int or flags <= 0 or flags & ~VALID_FLAGS:
            raise ValueError('Invalid inhibitor flags')
        if path in self._entries:
            raise ValueError('Request path is already registered')
        if len(self._entries) >= self._limit:
            raise OverflowError('Inhibitor capacity reached')
        entry=Inhibitor(path,owner,app_id,reason,flags,process_name)
        self._entries[path]=entry
        self._generation += 1
        return entry

    def close(self, path, owner):
        entry=self._entries.get(path)
        if entry is None or entry.owner != owner:
            return False
        del self._entries[path]
        self._generation += 1
        return True

    def owner_lost(self, owner):
        paths=[path for path,item in self._entries.items() if item.owner==owner]
        for path in paths:
            del self._entries[path]
        if paths:
            self._generation += 1
        return len(paths)

    def matching(self, flags):
        if type(flags) is not int or flags <= 0 or flags & ~VALID_FLAGS:
            raise ValueError('Invalid inhibitor flags')
        return tuple(item for item in self._entries.values() if item.flags & flags)
