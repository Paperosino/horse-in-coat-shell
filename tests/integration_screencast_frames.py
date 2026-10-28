#!/usr/bin/env python3
"""Actual ScreenCast permission UI and PipeWire frames in disposable CachyOS.

Run as the guest user; approve/cancel the real picker through the VM UI.
No host portal changes, permanent restore token, frame files or shell commands.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
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
    parser.add_argument('--disposable-cachyos-vm', required=True, action='store_true')
    args = parser.parse_args()
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
                    run = subprocess.run([str(args.probe_binary),str(descriptor),str(node),
                                          str(serial) if serial else '-'],
                        pass_fds=(descriptor,),stdout=subprocess.PIPE,stderr=log,text=True,timeout=25,env=consumer_env)
            finally:
                os.close(descriptor)
            report['consumerReturncode'] = run.returncode
            if run.stdout.strip().startswith('{'):
                report['frames'] = json.loads(run.stdout)
            save()
            assert run.returncode==0, 'PipeWire consumer failed; inspect result and stderr'
            assert report['frames']['frames']>=12 and report['frames']['changingFrames']>0
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
        if session:
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
        if not report.get('cancelled'):
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
            report['streamNodeRemovedAfterClose'] = True
    except BaseException:
        report['failedPhase'] = 'verify-session-cleanup'
        report['status'] = 'failed'
        save()
        raise
    report['status'] = 'passed'
    save()
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
