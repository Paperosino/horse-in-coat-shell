#!/usr/bin/env python3
"""Actual ScreenCast permission UI and PipeWire frames in disposable CachyOS.

Run as the guest user; approve/cancel the real picker through the VM UI.
No host portal changes, permanent restore token, frame files or shell commands.
"""
import argparse
import hashlib
import json
import os
import select
import signal
from pathlib import Path
import subprocess
import sys
import time
import uuid
from gi.repository import Gio, GLib


class UserCancelled(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe-binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--picker-timeout',type=int,default=90,help='Bounded manual selection deadline in seconds (15..600)')
    parser.add_argument('--trace-maps', action='store_true', help='Diagnostic-only bounded consumer mappings before module teardown')
    parser.add_argument('--source', choices=('monitor', 'window'), default='monitor')
    parser.add_argument('--expect-cancel', action='store_true')
    parser.add_argument('--backend-exit-after-frames',type=Path,help='Diagnostic-only instrumented backend executable; normal teardown while the sharing session remains open')
    parser.add_argument('--consumer-active-at-exit',action='store_true',help='Keep receiving frames when the diagnostic backend exits')
    parser.add_argument('--disposable-cachyos-vm', required=True, action='store_true')
    args = parser.parse_args()
    if args.backend_exit_after_frames and args.expect_cancel:parser.error('Exit requires a successful stream')
    if args.consumer_active_at_exit and not args.backend_exit_after_frames:parser.error('Active consumer requires diagnostic backend exit')
    if not 15<=args.picker_timeout<=600:parser.error('Picker timeout must be 15..600 seconds')
    assert os.getuid() == 1000 and Path('/etc/hostname').read_text().strip() == 'hics-test'
    assert subprocess.check_output(['systemd-detect-virt'], text=True).strip() in ('kvm', 'qemu')
    assert not json.loads(subprocess.check_output(['hyprctl','-i','0','-j','locked'], text=True))['locked']
    if args.output.exists():
        parser.error('Use a fresh evidence directory')
    os.umask(0o077)
    root = args.output.resolve()
    root.mkdir(mode=0o700)
    started=time.monotonic()
    report = {'pid': os.getpid(), 'startedUnixMillis':round(time.time()*1000), 'pickerTimeoutSeconds':args.picker_timeout, 'status': 'starting', 'source': args.source,
              'probeSha256': hashlib.file_digest(args.probe_binary.open('rb'),'sha256').hexdigest(),
              'steps': [], 'frameFilesSaved': False, 'persistentPermissionRequested': False}
    def save():
        temporary = root/'result.pending'
        temporary.write_text(json.dumps(report, indent=2)+'\n')
        temporary.replace(root/'result.json')
    save()
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    destination = 'org.freedesktop.portal.Desktop'
    path = '/org/freedesktop/portal/desktop'
    interface = 'org.freedesktop.portal.ScreenCast'
    if args.backend_exit_after_frames:
        backend='org.freedesktop.impl.portal.desktop.hyprland'
        owner,=bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner',
            GLib.Variant('(s)',(backend,)),None,Gio.DBusCallFlags.NONE,3000,None).unpack()
        backend_pid,=bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID',
            GLib.Variant('(s)',(owner,)),None,Gio.DBusCallFlags.NONE,3000,None).unpack()
        backend_process=Path('/proc')/str(backend_pid)
        assert (backend_process/'exe').resolve()==args.backend_exit_after_frames.resolve()
        backend_start=(backend_process/'stat').read_text().rsplit(')',1)[1].split()[19]
        report['backendBeforeFrames']={'pid':backend_pid,'startTicks':backend_start}
        save()
    responses = {}
    pending = set()
    def response(connection, sender, object_path, iface, signal, parameters):
        responses[object_path] = parameters.unpack()
    subscription = bus.signal_subscribe(destination, 'org.freedesktop.portal.Request',
        'Response', None, None, Gio.DBusSignalFlags.NONE, response)
    context = GLib.MainContext.default()
    session = None
    def call(method, parameters, timeout=10000, reply='(o)'):
        return bus.call_sync(destination,path,interface,method,parameters,
            GLib.VariantType.new(reply),Gio.DBusCallFlags.NONE,timeout,None).unpack()
    def request(method, signature, values, timeout=15):
        report['pendingMethod'] = method
        if method in ('SelectSources','Start'):
            report['status'] = 'awaiting-real-picker'
        save()
        handle, = call(method,GLib.Variant(signature,values))
        pending.add(handle)
        until = time.monotonic()+timeout
        while handle not in responses:
            while context.pending():
                context.iteration(False)
            if time.monotonic()>=until:
                report['timedOutMethod']=method
                report['elapsedSeconds']=round(time.monotonic()-started,3)
                save()
                raise AssertionError(method+' response timed out')
            time.sleep(.02)
        pending.discard(handle)
        code, result = responses.pop(handle)
        report['steps'].append({'method':method,'response':code,'elapsedSeconds':round(time.monotonic()-started,3)})
        save()
        if code == 1 and args.expect_cancel and method in ('SelectSources','Start'):
            report['cancelled'] = True
            raise UserCancelled()
        assert code == 0, method+' failed with response '+str(code)
        return result
    try:
        token = 'hics_'+uuid.uuid4().hex
        result = request('CreateSession','(a{sv})',({'handle_token':GLib.Variant('s',token),
            'session_handle_token':GLib.Variant('s',token+'_session')},))
        session = result['session_handle']
        request('SelectSources','(oa{sv})',(session,{'handle_token':GLib.Variant('s',token+'_select'),
            'types':GLib.Variant('u',1 if args.source=='monitor' else 2),
            'multiple':GLib.Variant('b',False),'persist_mode':GLib.Variant('u',0),
            'cursor_mode':GLib.Variant('u',2)}),timeout=args.picker_timeout)
        report['status'] = 'awaiting-real-picker'
        save()
        result = request('Start','(osa{sv})',(session,'',{
            'handle_token':GLib.Variant('s',token+'_start')}),timeout=args.picker_timeout)
        assert not args.expect_cancel, 'The requested cancellation did not occur'
        if not args.expect_cancel:
            streams = result['streams']
            assert len(streams)==1, 'Expected exactly one user-selected stream'
            node, properties = streams[0]
            assert isinstance(node,int) and node>=0
            serial = properties.get('pipewire-serial')
            if serial is not None:
                assert isinstance(serial,int) and 0<serial<2**64
            report['stream'] = {'node':node,'serialProvided':serial is not None, 'serial':serial,
                'size':properties.get('size'),'sourceType':properties.get('source_type')}
            assert properties.get('source_type') == (1 if args.source=='monitor' else 2), 'Backend returned a different source type'
            value, descriptors = bus.call_with_unix_fd_list_sync(destination,path,interface,
                'OpenPipeWireRemote',GLib.Variant('(oa{sv})',(session,{})),
                GLib.VariantType.new('(h)'),Gio.DBusCallFlags.NONE,10000,None,None)
            index, = value.unpack()
            descriptor = descriptors.get(index)
            report['status'] = 'reading-frames'
            save()
            consumer_env = dict(os.environ)
            if args.trace_maps:
                consumer_env['HICS_PIPEWIRE_MAPS'] = str(root/'consumer-maps.log')
            try:
                with (root/'frames.stderr.log').open('w') as log:
                    argv=[str(args.probe_binary),str(descriptor),str(node),str(serial) if serial else '-']
                    if args.consumer_active_at_exit:
                        consumer_env['HICS_CAPTURE_HOLD']='1'
                        consumer=subprocess.Popen(argv,pass_fds=(descriptor,),stdout=subprocess.PIPE,stderr=log,text=True,env=consumer_env)
                        try:
                            assert select.select([consumer.stdout],[],[],25)[0], 'Consumer did not report live frames'
                            report['frames']=json.loads(consumer.stdout.readline())
                            assert consumer.poll() is None, 'Consumer exited before backend teardown'
                            report['consumerAliveBeforeExit']=True
                            save()
                            assert serial and report['frames']['frames']>=12 and report['frames']['changingFrames']>0
                            assert (backend_process/'stat').read_text().rsplit(')',1)[1].split()[19]==backend_start
                            report['backendExitRequested']=True;save()
                            controller=Path(__file__).with_name('integration_portal_backend_exit.py')
                            with (root/'backend-exit-controller.log').open('w') as exit_log:
                                stopped=subprocess.run([sys.executable,str(controller),'--expected-executable',str(args.backend_exit_after_frames),
                                    '--output',str(root/'backend-exit.json'),'--disposable-cachyos-vm'],stdout=exit_log,stderr=subprocess.STDOUT,timeout=20)
                            assert stopped.returncode==0, 'Inspect backend exit controller evidence'
                            report['backendExit']=json.loads((root/'backend-exit.json').read_text())
                            assert report['backendExit']['status']=='exited-awaiting-sanitizer-review' and report['backendExit']['backendPid']==backend_pid
                            assert consumer.poll() is None, 'Consumer ended during backend teardown'
                            report['consumerAliveAfterExit']=True
                            until=time.monotonic()+5
                            while True:
                                graph=json.loads(subprocess.check_output(['pw-dump'],text=True,timeout=3))
                                present=any(item.get('type')=='PipeWire:Interface:Node' and str(item.get('info',{}).get('props',{}).get('object.serial'))==str(serial) for item in graph)
                                if not present:break
                                assert time.monotonic()<until, 'Producer node survived backend exit'
                                time.sleep(.1)
                            assert consumer.poll() is None, 'Consumer exited before producer removal was observed'
                            report['streamNodeRemovedWhileConsumerAlive']=True
                            consumer.send_signal(signal.SIGUSR1)
                            stdout,_=consumer.communicate(timeout=15)
                            report['consumerReturncode']=consumer.returncode
                            report['consumerAfterExit']=json.loads(stdout.strip())
                            assert report['consumerReturncode']==0 and not report['consumerAfterExit']['timeout'], 'Consumer did not stop cleanly'
                        finally:
                            if consumer.poll() is None:
                                consumer.terminate()
                                try: consumer.communicate(timeout=3)
                                except subprocess.TimeoutExpired:
                                    consumer.kill();consumer.communicate()
                    else:
                        run = subprocess.run(argv,pass_fds=(descriptor,),stdout=subprocess.PIPE,stderr=log,text=True,timeout=25,env=consumer_env)
            finally:
                os.close(descriptor)
            if not args.consumer_active_at_exit:
                report['consumerReturncode'] = run.returncode
                if run.stdout.strip().startswith('{'):
                    report['frames'] = json.loads(run.stdout)
            save()
            if not args.consumer_active_at_exit:
                assert run.returncode==0, 'PipeWire consumer failed; inspect result and stderr'
            assert report['frames']['frames']>=12 and report['frames']['changingFrames']>0
            if args.backend_exit_after_frames and not args.consumer_active_at_exit:
                assert serial, 'This diagnostic case requires stable stream identity'
                dump=subprocess.check_output(['pw-dump'],text=True,timeout=3);assert len(dump)<4*1024*1024
                assert any(str(item.get('info',{}).get('props',{}).get('object.serial'))==str(serial)
                           and item.get('type')=='PipeWire:Interface:Node' for item in json.loads(dump)), 'Sharing stream already disappeared'
                assert (backend_process/'stat').read_text().rsplit(')',1)[1].split()[19]==backend_start,'Backend changed before exit'
                report['streamPresentBeforeBackendExit']=True
                report['backendExitRequested']=True;save()
                controller=Path(__file__).with_name('integration_portal_backend_exit.py')
                with (root/'backend-exit-controller.log').open('w') as log:
                    stopped=subprocess.run([sys.executable,str(controller),'--expected-executable',str(args.backend_exit_after_frames),
                        '--output',str(root/'backend-exit.json'),'--disposable-cachyos-vm'],stdout=log,stderr=subprocess.STDOUT,timeout=20)
                assert stopped.returncode==0, 'Inspect backend exit controller evidence'
                report['backendExit']=json.loads((root/'backend-exit.json').read_text())
                assert report['backendExit']['status']=='exited-awaiting-sanitizer-review'
                assert report['backendExit']['backendPid']==backend_pid,'Exited a reactivated backend rather than the original producer'
                save()
        report['status'] = 'closing-session'
        save()
    except UserCancelled:
        pass
    except BaseException:
        report['failedPhase'] = report['status']
        report['status'] = 'failed'
        raise
    finally:
        # Cancel only requests created by this client; never restart the portal.
        for handle in pending:
            try:
                bus.call_sync(destination,handle,'org.freedesktop.portal.Request','Close',
                    None,None,Gio.DBusCallFlags.NONE,3000,None)
            except GLib.Error:
                pass
        if session and not report.get('backendExitRequested'):
            try:
                bus.call_sync(destination,session,'org.freedesktop.portal.Session','Close',
                    None,None,Gio.DBusCallFlags.NONE,5000,None)
                report['sessionCloseReturned'] = True
            except GLib.Error as error:
                # A cancelled request may already have destroyed its session.
                report['sessionCloseReturned'] = False
                report['closeErrorName'] = Gio.DBusError.get_remote_error(error)
        bus.signal_unsubscribe(subscription)
        save()
    try:
        if not report.get('cancelled') and not report.get('backendExitRequested'):
            assert report.get('sessionCloseReturned'), 'Successful sharing session did not close'
        if report.get('stream',{}).get('serial'):
            serial = report['stream']['serial']
            deadline = time.monotonic()+5
            while True:
                dump = subprocess.check_output(['pw-dump'],text=True,timeout=3)
                assert len(dump)<4*1024*1024, 'Unexpectedly large guest PipeWire graph'
                nodes = json.loads(dump)
                remaining = [node for node in nodes if node.get('type')=='PipeWire:Interface:Node'
                    and str(node.get('info',{}).get('props',{}).get('object.serial'))==str(serial)]
                if not remaining: break
                assert time.monotonic()<deadline, 'Portal stream survives Session.Close'
                time.sleep(.1)
            report['streamNodeRemovedAfterBackendExit' if report.get('backendExitRequested') else 'streamNodeRemovedAfterClose'] = True
    except BaseException:
        report['failedPhase'] = 'verify-session-cleanup'
        report['status'] = 'failed'
        save()
        raise
    report['status'] = 'backend-exited-awaiting-sanitizer-review' if report.get('backendExitRequested') else 'passed'
    save()
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
