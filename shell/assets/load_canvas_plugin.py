#!/usr/bin/env python3
"""Load the canvas once the compositor has completed its first configuration."""
import json
import subprocess
import sys
import time
from pathlib import Path


def query(*args):
    result = subprocess.run(['hyprctl', *args], capture_output=True, text=True, timeout=2)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Hyprland IPC failed')
    return result.stdout.strip()


def load(plugin, timeout=30):
    plugin = Path(plugin)
    if not plugin.is_file():
        return False
    deadline = time.monotonic() + timeout
    last_error = 'Compositor configuration is not ready'
    while time.monotonic() < deadline:
        try:
            plugins = json.loads(query('-j', 'plugin', 'list'))
            if any(p.get('name') == 'spatialoverview' for p in plugins):
                return True
            monitors = json.loads(query('-j', 'monitors'))
            # IPC alone can be available before init finishes. Require both
            # configured outputs and the last-stage shell Lua integration.
            ready = query('repl', 'return hyprstack_layouts ~= nil and hl.plugin.hyprbars ~= nil and hl.plugin.hyprbars.ready ~= nil and hl.plugin.hyprbars.ready()')
            if monitors and ready == 'true':
                break
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            last_error = str(error)
        time.sleep(.1)
    else:
        raise RuntimeError('Timed out waiting for Hyprland readiness: ' + last_error)
    # Never repeat a partially failed dlopen/PLUGIN_INIT in the running compositor.
    response = query('plugin', 'load', str(plugin))
    if response.lower() != 'ok':
        raise RuntimeError('Cannot load canvas: ' + response)
    return True


if __name__ == '__main__':
    try:
        load(sys.argv[1])
    except Exception as error:
        print('hics: ' + str(error), file=sys.stderr)
        sys.exit(1)
