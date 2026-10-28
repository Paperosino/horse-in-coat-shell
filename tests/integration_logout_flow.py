#!/usr/bin/env python3
"""Exercise candidate logout flow in a nested compositor and private buses."""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import shutil
import subprocess
import tempfile
import time
from diagnose_session_logout import MOCK, WINDOW
from integration_support import require_wayland_session, snapshot_qml_runtime

ROOT=Path(__file__).resolve().parents[1]
QS='/usr/share/hics/qs/bin/hics-qs'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--action',choices=('cancel','save','force','lock'),required=True)
    parser.add_argument('--with-inhibitor',action='store_true')
    parser.add_argument('--pointer',action='store_true')
    parser.add_argument('--wrong-portal',action='store_true')
    parser.add_argument('--kill-frontend',action='store_true')
    parser.add_argument('--kill-backend',action='store_true')
    parser.add_argument('--empty',action='store_true')
    parser.add_argument('--deny-logind',action='store_true')
    parser.add_argument('--commit-race',action='store_true')
    args=parser.parse_args();require_wayland_session()
    if args.output.exists():parser.error('Use a fresh output directory')
    args.output.mkdir(parents=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix='hlo-') as directory:
        root=Path(directory);runtime=root/'run';runtime.mkdir(mode=0o700)
        shell=root/'shell';installed=os.environ.get('HICS_TEST_INSTALLED_RUNTIME')=='1'
        installed_candidate=os.environ.get('HICS_TEST_USE_INSTALLED_CANDIDATE')=='1'
        shutil.copytree(Path('/usr/share/hics/shell') if installed else ROOT/'shell',shell,ignore=shutil.ignore_patterns('plugin','extras','__pycache__'))
        if installed and not installed_candidate:
            for name in ('LogoutFlow.qml','LogoutBlockersWindow.qml'):
                shutil.copy2(ROOT/'shell/modules/session'/name,shell/'modules/session'/name)
        shutil.copy2(ROOT/'tests/fixtures/logout_flow.qml',shell/'shell.qml')
        prebuilt=os.environ.get('HICS_TEST_EDITOR_BINARY')
        if prebuilt:
            shutil.copy2(prebuilt,root/'editor')
        else:
            source=root/'editor.cpp';source.write_text(WINDOW)
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets'],text=True))
            subprocess.run(['c++','-std=c++20','-fPIC',str(source),*flags,'-o',str(root/'editor')],check=True)
        busconf=root/'bus.conf';busconf.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(root)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(busconf)],stdout=subprocess.PIPE,text=True)
        address=bus.stdout.readline().strip();assert address
        parent=os.environ['WAYLAND_DISPLAY']
        if not parent.startswith('/'):parent=str(Path(os.environ['XDG_RUNTIME_DIR'])/parent)
        env=dict(os.environ,HOME=str(root),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),
                 XDG_CACHE_HOME=str(root/'cache'),XDG_STATE_HOME=str(root/'state'),XDG_RUNTIME_DIR=str(runtime),
                 WAYLAND_DISPLAY=parent,AQ_BACKEND='wayland',DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address,
                 GSETTINGS_BACKEND='memory',PULSE_SERVER='unix:'+str(root/'no-pulse'),HICS_TEST_TRACE=str(root/'logind'),
                 HICS_TEST_WINDOW_TRACE=str(root/'window'),HICS_TEST_WINDOW_CONTROL=str(root/'control'))
        env.pop('HYPRLAND_INSTANCE_SIGNATURE',None);env.pop('LD_LIBRARY_PATH',None)
        layout_root=(Path('/usr/share/hics/shell/assets/hyprland') if installed else ROOT/'shell/assets/hyprland')
        config=root/'h.lua'
        config.write_text('package.path='+json.dumps(str(layout_root/'config/?.lua')+';')+'..package.path\n'
                          +'package.preload["scheme.current"]=function() return require("scheme.default") end\n'
                          +'hl.monitor({output="WAYLAND-1",mode="800x600@60",position="0x0",scale=1})\n'
                          +'hl.device({name="wl_pointer",enabled=false})\n'
                          +'dofile('+json.dumps(str(layout_root/'config/hyprland/animations.lua'))+')\n'
                          +'dofile('+json.dumps(str(layout_root/'config/hyprland/gestures.lua'))+')\n'
                          +'dofile('+json.dumps(str(layout_root/'layouts.lua'))+')\n')
        processes=[];logs=[]
        def launch(cmd,name,environment=env):
            log=(args.output/(name+'.log')).open('w');logs.append(log)
            process=subprocess.Popen(cmd,env=environment,stdout=log,stderr=subprocess.STDOUT);processes.append(process);return process
        def wait_until(predicate,description,seconds=15):
            deadline=time.monotonic()+seconds
            while not predicate():
                assert time.monotonic()<deadline,description
                time.sleep(.05)
        try:
            mock_source=MOCK
            if args.deny_logind:
                mock_source=mock_source.replace('  with open(os.environ[\'HICS_TEST_TRACE\'],\'a\') as stream:stream.write(\'Terminate\\n\')',
                    '  raise dbus.exceptions.DBusException(\'Test denial\',name=\'org.freedesktop.DBus.Error.AccessDenied\')')
                assert mock_source != MOCK
            mock=launch(['python3','-c',mock_source],'logind')
            backend_path=Path('/usr/share/hics/shell/assets/logout_portal_backend.py') if installed_candidate else ROOT/'shell/assets/logout_portal_backend.py'
            if args.commit_race:
                backend=launch(['python3',str(ROOT/'tests/fixtures/logout_delayed_backend.py')],'portal',dict(env,HICS_TEST_PRIVATE_BUS='1'))
            else:
                backend=launch(['python3',str(backend_path)],'portal')
            blocker=None
            data=root/'data';preferences=root/'config/xdg-desktop-portal';portals=data/'xdg-desktop-portal/portals'
            portals.mkdir(parents=True);preferences.mkdir(parents=True)
            (portals/'hics.portal').write_text('[portal]\nDBusName=org.freedesktop.impl.portal.desktop.hics\nInterfaces=org.freedesktop.impl.portal.Inhibit;\nUseIn=HICS\n')
            if args.wrong_portal:
                (portals/'wrong.portal').write_text('[portal]\nDBusName=org.freedesktop.impl.portal.desktop.hicsDelegateTest\nInterfaces=org.freedesktop.impl.portal.Inhibit;\nUseIn=HICS\n')
                (preferences/'portals.conf').write_text('[preferred]\ndefault=wrong\n')
                launch(['python3',str(ROOT/'tests/fixtures/logout_inhibit_delegate.py')],'wrong-backend',dict(env,HICS_TEST_PRIVATE_BUS='1'))
            else:
                (preferences/'portals.conf').write_text('[preferred]\ndefault=hics\n')
            portal_env=dict(env,XDG_DATA_DIRS='/usr/share',XDG_CURRENT_DESKTOP='HICS')
            frontend=launch(['/usr/lib/xdg-desktop-portal'],'frontend',portal_env)
            def has_frontend():
                reply=subprocess.run(['gdbus','call','--session','--dest','org.freedesktop.DBus','--object-path','/org/freedesktop/DBus',
                                      '--method','org.freedesktop.DBus.NameHasOwner','org.freedesktop.portal.Desktop'],env=portal_env,text=True,capture_output=True,timeout=3)
                return 'true' in reply.stdout
            wait_until(has_frontend,'Portal frontend did not start')
            if args.with_inhibitor:
                blocker=launch(['python3',str(ROOT/'tests/fixtures/logout_inhibit_client.py')],'blocker',portal_env)
                blocker_log=args.output/'blocker.log'
                wait_until(lambda:'ready' in blocker_log.read_text(),'Portal inhibitor did not start')
            compositor=launch(['Hyprland','--config',str(config)],'hyprland')
            def instance():
                try:data=json.loads(subprocess.check_output(['hyprctl','instances','-j'],env=env,text=True,timeout=3))
                except json.JSONDecodeError:return None
                return next((x for x in data if x['pid']==compositor.pid),None)
            wait_until(lambda:instance() is not None,'Nested compositor did not start')
            item=instance()
            def clients():return json.loads(subprocess.check_output(['hyprctl','-i',item['instance'],'clients','-j'],env=env,text=True,timeout=3))
            appenv=dict(env,WAYLAND_DISPLAY=str(runtime/item['wl_socket']),HYPRLAND_INSTANCE_SIGNATURE=item['instance'],QT_QPA_PLATFORM='wayland')
            editorenv=dict(appenv)
            if installed:editorenv['LD_LIBRARY_PATH']='/usr/share/hics/qs/lib'
            editor=None
            if not args.empty:
                editor=launch([str(root/'editor')],'editor',editorenv)
                wait_until(lambda:any(c.get('pid')==editor.pid and c.get('mapped') for c in clients()),'Editor did not map')
            if installed:
                qml=root/'qml';libs=root/'libs'
                shutil.copytree('/usr/share/hics/qml',qml,symlinks=False)
                shutil.copytree('/usr/share/hics/qml/Hyprstack/lib',libs,symlinks=False)
                if not installed_candidate:
                    shutil.copy2(ROOT/'candidate/libhyprstack-services.so',libs/'libhyprstack-services.so')
                    for name in ('libhyprstack-servicesplugin.so','hyprstack-services.qmltypes','qmldir'):
                        shutil.copy2(ROOT/'candidate'/name,qml/'Hyprstack/Services'/name)
                appenv.update(QML_IMPORT_PATH=str(qml),QML2_IMPORT_PATH=str(qml),
                              LD_LIBRARY_PATH=str(libs)+':/usr/share/hics/qs/lib')
            else:
                appenv.update(snapshot_qml_runtime(ROOT,root))
            qs=launch([QS,'-p',str(shell)],'shell',appenv)
            def do_action(action):
                if not args.pointer or action not in ('cancel','force'):
                    result=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture',action],env=appenv,text=True,capture_output=True,timeout=8)
                    assert result.returncode==0,result.stderr
                    return
                pointer_binary=os.environ.get('HICS_TEST_POINTER_BINARY')
                if not pointer_binary:
                    fixtures=ROOT/'tests/fixtures';xml=fixtures/'wlr-virtual-pointer-unstable-v1.xml'
                    subprocess.run(['wayland-scanner','client-header',str(xml),str(root/'virtual-pointer.h')],check=True)
                    subprocess.run(['wayland-scanner','private-code',str(xml),str(root/'virtual-pointer-protocol.c')],check=True)
                    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','wayland-client'],text=True))
                    pointer_binary=str(root/'pointer')
                    subprocess.run(['cc',str(fixtures/'virtual-pointer.c'),str(root/'virtual-pointer-protocol.c'),'-I',str(root),*flags,'-o',pointer_binary],check=True)
                result=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','button',action],env=appenv,text=True,capture_output=True,timeout=8,check=True)
                point=json.loads(result.stdout.strip())
                window=next(c for c in clients() if c.get('pid')==qs.pid and c.get('mapped'))
                focus='local w=hl.get_window('+json.dumps('address:'+window['address'])+');hl.dispatch(hl.dsp.focus({window=w}))'
                subprocess.run(['hyprctl','-i',item['instance'],'eval',focus],env=env,check=True,capture_output=True,timeout=3)
                time.sleep(.3)
                window=next(c for c in clients() if c.get('pid')==qs.pid and c.get('mapped'))
                result=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','button',action],env=appenv,text=True,capture_output=True,timeout=8,check=True)
                point=json.loads(result.stdout.strip())
                monitors=json.loads(subprocess.check_output(['hyprctl','-i',item['instance'],'monitors','-j'],env=env,text=True,timeout=3))
                pointer_env=dict(appenv,HYPRSTACK_POINTER_WIDTH=str(monitors[0]['width']),HYPRSTACK_POINTER_HEIGHT=str(monitors[0]['height']))
                pointer=subprocess.Popen([pointer_binary],env=pointer_env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
                try:
                    assert pointer.stdout.readline().strip()=='ready'
                    def send(op,x,y):
                        pointer.stdin.write(f'{op} {x} {y}\n');pointer.stdin.flush();assert pointer.stdout.readline().strip()=='ok'
                    px,py=round(window['at'][0]+point[0]),round(window['at'][1]+point[1])
                    send('move',max(0,px-20),max(0,py-20));send('move',px,py)
                    cursor=json.loads(subprocess.check_output(['hyprctl','-i',item['instance'],'cursorpos','-j'],env=env,text=True,timeout=3))
                    assert abs(cursor['x']-px)<=1 and abs(cursor['y']-py)<=1,(cursor,point,window)
                    time.sleep(.1);send('button',272,1);time.sleep(.1);send('button',272,0)
                finally:
                    pointer.stdin.close();pointer.wait(timeout=5)
            window_trace=root/'window';logind_trace=root/'logind'
            wait_until(lambda:logind_trace.exists() and ('GetSessionByPID '+str(compositor.pid)) in logind_trace.read_text(),
                       'Session manager did not resolve the nested compositor PID')
            if args.commit_race:
                def state():
                    reply=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','state'],env=appenv,text=True,capture_output=True,timeout=5)
                    try:return json.loads(reply.stdout)
                    except (ValueError,TypeError):return {}
                def call(action):
                    subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture',action],env=appenv,text=True,capture_output=True,timeout=5,check=True)
                wait_until(lambda:state().get('finishing') is True,'First commit did not start')
                call('lock')
                wait_until(lambda:not state().get('active',True) and not state().get('busy',True),'Lock did not cancel first commit')
                call('unlock');call('start')
                try:
                    wait_until(lambda:state().get('finishing') is True,'Second commit did not start')
                except AssertionError:
                    (args.output/'failure-state.json').write_text(json.dumps(state(),indent=2)+'\n'+json.dumps(clients(),indent=2)+'\n')
                    raise
                time.sleep(1)
                current=state()
                assert current.get('finishing') and current.get('busy') and (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),('Old reply changed new commit',current)
                wait_until(lambda:logind_trace.exists() and 'Terminate' in logind_trace.read_text(),'Second commit did not complete')
                report={'status':'passed','scope':'delayed commit reply after lock/cancel/retry, private bus and fake logind',
                        'oldReplyDidNotOverrideNewCommit':True}
                (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return
            if args.deny_logind:
                def denied():
                    state=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','state'],env=appenv,text=True,capture_output=True,timeout=5)
                    return 'Test denial' in state.stdout and '"active":true' in state.stdout
                wait_until(denied,'Logind denial was not presented')
                do_action('cancel')
                report={'status':'passed','scope':'logind denial keeps the logout UI open and is cancellable on a private bus',
                        'logindDenialShown':True}
                (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return
            if args.empty:
                wait_until(lambda:logind_trace.exists() and 'Terminate' in logind_trace.read_text(),'Empty session did not terminate')
                report={'status':'passed','scope':'empty nested session with real portal and fake logind','emptySessionTerminated':True}
                (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return
            if args.wrong_portal:
                def failed_probe():
                    state=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','state'],env=appenv,text=True,capture_output=True,timeout=5)
                    return 'did not forward logout inhibition' in state.stdout
                wait_until(failed_probe,'Wrong portal backend was not detected')
                assert not window_trace.exists() and (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()) and editor.poll() is None,'Wrong portal allowed logout to progress'
                do_action('cancel')
                report={'status':'passed','scope':'wrong portal selection fails closed with fake logind',
                        'wrongPortalDetected':True,'windowNotClosed':True}
                (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return
            if blocker:
                def listed():
                    query=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','blockers'],env=appenv,text=True,capture_output=True,timeout=5)
                    assert 'hics-logout-probe-' not in query.stdout, 'Internal portal probe was exposed as an application'
                    return 'Unsaved background work' in query.stdout
                wait_until(listed,'Controller did not expose portal inhibitor')
                assert not window_trace.exists() and (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Session advanced while portal inhibitor was active'
                if args.kill_backend:
                    backend.terminate();backend.wait(timeout=5)
                    def backend_failed():
                        state=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','state'],env=appenv,text=True,capture_output=True,timeout=5)
                        return 'Logout portal disconnected' in state.stdout
                    wait_until(backend_failed,'Portal backend disconnection was not reported')
                    time.sleep(1)
                    assert not window_trace.exists() and (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Backend disconnection allowed logout to progress'
                    do_action(args.action)
                    if args.action=='force':
                        wait_until(lambda:logind_trace.exists() and 'Terminate' in logind_trace.read_text(),'Explicit force after backend loss failed')
                    else:
                        assert (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Cancellation after backend loss terminated session'
                    report={'status':'passed','scope':'portal backend loss fails closed; fake logind',
                            'backendLossDetected':True,'action':args.action}
                    (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return
                if args.kill_frontend:
                    frontend.terminate();frontend.wait(timeout=5)
                    def frontend_failed():
                        state=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','state'],env=appenv,text=True,capture_output=True,timeout=5)
                        return 'Desktop portal disconnected' in state.stdout
                    wait_until(frontend_failed,'Portal disconnection was not reported')
                    time.sleep(1)
                    assert not window_trace.exists() and (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Portal disconnection allowed logout to progress'
                    do_action(args.action)
                    if args.action=='force':
                        wait_until(lambda:logind_trace.exists() and 'Terminate' in logind_trace.read_text(),'Explicit force after portal loss failed')
                    else:
                        assert (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Cancellation after portal loss terminated session'
                    report={'status':'passed','scope':'portal frontend loss fails closed; fake logind',
                            'frontendLossDetected':True,'action':args.action}
                    (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return
                if args.action in ('cancel','force'):
                    do_action(args.action)
                    if args.action=='force':
                        try:
                            wait_until(lambda:logind_trace.exists() and 'Terminate' in logind_trace.read_text(),'Force did not override portal inhibitor')
                        except AssertionError:
                            state=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','state'],env=appenv,text=True,capture_output=True,timeout=5)
                            (args.output/'failure-state.json').write_text(state.stdout+'\n'+json.dumps(clients(),indent=2)+'\n')
                            raise
                    else:
                        wait_until(lambda:subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','active'],env=appenv,text=True,capture_output=True,timeout=5).stdout.strip()=='false','Logout remained active')
                        time.sleep(1)
                        assert (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()) and editor.poll() is None,'Cancel terminated an inhibited session'
                    report={'status':'passed','action':args.action,'scope':'candidate QML controller with real XDG portal inhibitor and fake logind; isolated pointer or test IPC invokes action',
                            'portalInhibitorTested':True,'windowNotClosedBeforeAction':True,'pointerInput':args.pointer}
                    (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
                    return
                os.kill(blocker.pid,signal.SIGUSR1)
                wait_until(lambda:'released' in blocker_log.read_text(),'Portal inhibitor did not release')
            wait_until(lambda:window_trace.exists() and 'warning-shown' in window_trace.read_text(), 'Logout did not open unsaved warning')
            assert (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Logout terminated while the warning was visible'
            time.sleep(2)
            assert editor.poll() is None and (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Logout did not wait for the warning'
            if args.action=='save':
                (root/'control').write_text('save')
                wait_until(lambda:editor.poll() is not None,'Editor did not close after saving')
                try:
                    wait_until(lambda:logind_trace.exists() and 'Terminate' in logind_trace.read_text(),'Saving did not complete logout')
                except AssertionError:
                    state=subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','state'],env=appenv,text=True,capture_output=True,timeout=5)
                    (args.output/'failure-state.json').write_text(state.stdout+'\n'+json.dumps(clients(),indent=2)+'\n')
                    raise
            else:
                (root/'control').write_text('cancel')
                wait_until(lambda:'cancelled' in window_trace.read_text(),'Warning did not accept cancellation')
                assert editor.poll() is None and (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Cancellation did not keep the session'
                do_action(args.action)
                if args.action=='force':
                    wait_until(lambda:logind_trace.exists() and 'Terminate' in logind_trace.read_text(),'Explicit force did not request termination')
                else:
                    wait_until(lambda:subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','active'],env=appenv,text=True,capture_output=True,timeout=5).stdout.strip()=='false','Logout remained active')
                    if args.action=='lock':
                        subprocess.run([QS,'ipc','--pid',str(qs.pid),'call','logoutFixture','force'],env=appenv,text=True,capture_output=True,timeout=8,check=True)
                    time.sleep(1)
                    assert editor.poll() is None and (not logind_trace.exists() or 'Terminate' not in logind_trace.read_text()),'Cancel or lock terminated the session'
            report={'status':'passed','action':args.action,
                    'scope':'candidate QML controller, production window dispatch and real Qt warning in nested Hyprland with fake logind; isolated pointer or test IPC invokes cancellation or force',
                    'warningVisibleBeforeTerminate':True,'portalInhibitorTested':args.with_inhibitor,'pointerInput':args.pointer}
            (args.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
        finally:
            for proc in reversed(processes):
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
            bus.terminate();bus.wait(timeout=5)
            for log in logs:log.close()

if __name__=='__main__':main()
