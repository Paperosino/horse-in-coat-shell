#!/usr/bin/env python3
"""Actual notify/ExecStopPost lifecycle against a disposable nested Lua compositor.

The package transaction lock is replaced with a private test file; the real
pacman database and the parent compositor are never modified.
"""
import json, os, shutil, signal, subprocess, tempfile, time, uuid
from pathlib import Path
from integration_support import require_wayland_session
require_wayland_session()
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'shell/assets'))
import session_bootstrap

def run(*args, **kwargs):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=25,**kwargs).stdout.strip()

with tempfile.TemporaryDirectory(prefix='hics package guard ') as directory:
    base=Path(directory); data=base/'data';data.mkdir()
    shutil.copytree(ROOT/'shell/assets/hyprland',data/'shell/assets/hyprland')
    (data/'defaults').symlink_to(ROOT/'distribution/defaults',target_is_directory=True)
    config=base/'config';variables,entry=session_bootstrap.prepare(data,config)
    env=dict(os.environ,**variables,XDG_CONFIG_HOME=str(config),AQ_BACKEND='wayland',HYPRSTACK_NESTED='1')
    env.pop('HYPRLAND_INSTANCE_SIGNATURE',None)
    unit='hics-test-package-guard-'+uuid.uuid4().hex
    with (base/'hyprland.log').open('w') as log:
        compositor=subprocess.Popen(['Hyprland','--config',str(entry)],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        instance=None
        for _ in range(100):
            instance=next((i for i in json.loads(run('hyprctl','instances','-j')) if i['pid']==compositor.pid),None)
            if instance:break
            if compositor.poll() is not None:raise AssertionError((base/'hyprland.log').read_text()[-5000:])
            time.sleep(.1)
        assert instance,'Nested compositor did not start'
        signature=instance['instance']
        def ctl(*args):return run('hyprctl','-i',signature,*args,env=env)
        def disabled():return json.loads(ctl('-j','getoption','misc:disable_autoreload'))['bool']
        assert not ctl('configerrors'),ctl('configerrors')
        binds=len(json.loads(ctl('-j','binds')));assert binds>10,binds
        # Capture the exact production argv, without allowing the hook to call
        # the real systemctl/systemd-run against the parent graphical session.
        tools=base/'tools';tools.mkdir();captured=base/'guard.json'
        stub='#!'+sys.executable+'\n'+'''import json,os,sys
from pathlib import Path
if Path(sys.argv[0]).name=='systemd-run':
 Path(os.environ['HICS_TEST_CAPTURE']).write_text(json.dumps(sys.argv[1:]))
elif sys.argv[1]=='list-units':print('user@'+str(os.getuid())+'.service loaded active running Test')
elif sys.argv[-1]=='show-environment':print(os.environ['HICS_TEST_ENV'])
else:raise SystemExit('Unexpected systemctl call')
'''
        for name in ('systemctl','systemd-run'):
            path=tools/name;path.write_text(stub);path.chmod(0o755)
        fixture=dict(env,PATH=str(tools)+':'+os.environ['PATH'],HICS_TEST_CAPTURE=str(captured),
                     HICS_TEST_ENV='HYPRLAND_INSTANCE_SIGNATURE='+signature+'\nWAYLAND_DISPLAY='+instance['wl_socket']+'\nXDG_RUNTIME_DIR='+os.environ['XDG_RUNTIME_DIR'])
        run('bash','-c','. "$1"; hics_pause_user_config','guard-fixture',str(ROOT/'packaging/arch/hic-shell.install'),env=fixture)
        arguments=json.loads(captured.read_text())
        assert any('Type=notify' in arg for arg in arguments)
        assert any('ExecStopPost=' in arg for arg in arguments)
        transaction=base/'transaction.lock'
        actual=[]
        for arg in arguments:
            if arg.startswith('--machine='):continue
            if arg=='--unit=hics-package-config-guard':arg='--unit='+unit
            if arg=='--property=RuntimeDirectory=hics-package-config-guard':arg='--property=RuntimeDirectory='+unit
            if "pathlib.Path('/var/lib/pacman/db.lck')" in arg:
                arg=arg.replace("pathlib.Path('/var/lib/pacman/db.lck')",'pathlib.Path('+repr(str(transaction))+')')
            actual.append(arg)
        # Service manager variables are explicitly overridden for this nested
        # instance. Never rely on its imported parent compositor environment.
        for key in ('HYPRLAND_INSTANCE_SIGNATURE','XDG_RUNTIME_DIR','WAYLAND_DISPLAY'):
            value=signature if key=='HYPRLAND_INSTANCE_SIGNATURE' else instance['wl_socket'] if key=='WAYLAND_DISPLAY' else os.environ[key]
            actual.insert(0,'--setenv='+key+'='+value)
        def start():return run('systemd-run',*actual,env=env)
        def restored(expected):
            for _ in range(60):
                if disabled()==expected:return
                time.sleep(.1)
            raise AssertionError('Autoreload state was not restored: '+str(expected))
        def inactive():
            for _ in range(60):
                response=subprocess.run(['systemctl','--user','is-active','--quiet',unit],env=env,timeout=3)
                if response.returncode:return
                time.sleep(.1)
            raise AssertionError('Guard did not finish')
        transaction.touch();start();assert disabled()
        module=data/'shell/assets/hyprland/config/variables.lua';content=module.read_bytes();module.unlink()
        scheme=config/'hics/hypr/scheme/current.lua';scheme.write_text(scheme.read_text()+'\n-- test package transaction\n')
        time.sleep(.8)
        assert not ctl('configerrors'),ctl('configerrors')
        assert len(json.loads(ctl('-j','binds')))==binds,'Partial reload lost key bindings'
        module.write_bytes(content);transaction.unlink();restored(False);inactive()
        # Re-enabled watching still responds to normal edits after the upgrade.
        entry.write_text(entry.read_text()+'\nhl.config({misc={mouse_move_enables_dpms=false}})\n')
        for _ in range(60):
            if not json.loads(ctl('-j','getoption','misc:mouse_move_enables_dpms'))['bool']:break
            time.sleep(.1)
        else:raise AssertionError('Restored watcher did not apply a real configuration change')
        assert not ctl('configerrors'),ctl('configerrors')
        assert len(json.loads(ctl('-j','binds')))==binds
        # An exception between changing the compositor and READY must fail the
        # preflight and still restore its option through ExecStopPost.
        failing=[arg.replace("    address = os.environ['NOTIFY_SOCKET']", "    raise ValueError('injected pre-READY failure')\n    address = os.environ['NOTIFY_SOCKET']") for arg in actual]
        transaction.touch()
        failure=subprocess.run(['systemd-run',*failing],env=env,capture_output=True,text=True,timeout=25)
        assert failure.returncode,'A failed guard reported readiness'
        restored(False);inactive();transaction.unlink()
        transaction.touch();start();assert disabled()
        run('systemctl','--user','kill','--kill-whom=main','--signal=KILL',unit,env=env)
        restored(False);inactive();transaction.unlink()
        ctl('eval','hl.config({misc={disable_autoreload=true}})')
        transaction.touch();start();inactive();assert disabled(),'User-disabled autoreload was overwritten'
        transaction.unlink();ctl('eval','hl.config({misc={disable_autoreload=false}})')
        print('PASS: package guard readiness, partial-module replacement, binds, watcher recovery, pre-READY failure, SIGKILL cleanup and user-disabled setting')
    finally:
        # This unit and compositor were created by this test alone.
        subprocess.run(['systemctl','--user','stop',unit],env=env,capture_output=True,timeout=12)
        try:os.killpg(compositor.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:compositor.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(compositor.pid,signal.SIGKILL);compositor.wait()
