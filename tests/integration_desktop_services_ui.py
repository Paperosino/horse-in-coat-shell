#!/usr/bin/env python3
"""Render desktop settings with actual jobs on an isolated D-Bus session."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
if '--fixture' not in sys.argv:
    raise SystemExit(subprocess.run(['dbus-run-session','--',sys.executable,__file__,'--fixture']).returncode)
with tempfile.TemporaryDirectory(prefix='hics-desktop-ui-service-') as temporary:
    env=dict(os.environ,XDG_STATE_HOME=temporary+'/state',XDG_CONFIG_HOME=temporary+'/config',XDG_DATA_HOME=temporary+'/data')
    mock=subprocess.Popen([sys.executable,str(ROOT/'tests/mock_desktop_jobs_bus.py')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    assert mock.stdout.readline().strip()=='ready'
    try:
        result=subprocess.run([sys.executable,str(ROOT/'tests/integration_settings_design.py')],env=dict(os.environ,HICS_TEST_WIDGET="1",HICS_TEST_NATIVE_DESKTOP="1"),timeout=150)
        if result.returncode:raise SystemExit(result.returncode)
        print('PASS: real desktop job cards, failures and service-backed settings in a private bus')
    finally:
        mock.terminate();mock.wait(timeout=3)
