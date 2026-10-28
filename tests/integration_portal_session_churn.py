#!/usr/bin/env python3
"""Exercise real ScreenCast session cleanup without opening a picker/device.

Disposable CachyOS only. A red cleanup baseline is retained with counts and
memory samples; optional baseline mode never declares the leak fixed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from gi.repository import Gio, GLib


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations',type=int,default=500)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-executable',type=Path,required=True)
    parser.add_argument('--expect-retained-requests',action='store_true')
    parser.add_argument('--external-inhibitor',action='store_true',help='Verify a root systemd-inhibit ancestor instead of prompting for permission')
    parser.add_argument('--disposable-cachyos-vm',action='store_true',required=True)
    args=parser.parse_args()
    assert os.getuid()==1000 and Path('/etc/hostname').read_text().strip()=='hics-test'
    assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
    if not 1<=args.iterations<=3000:parser.error('Use 1..3000 sessions')
    if args.output.exists():parser.error('Use fresh evidence')
    os.umask(0o077);args.output.parent.mkdir(parents=True,exist_ok=True)
    system=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
    if args.external_inhibitor:
        exercise(args,external_inhibitor(system))
    else:
        value,descriptors=system.call_with_unix_fd_list_sync(
            'org.freedesktop.login1','/org/freedesktop/login1','org.freedesktop.login1.Manager','Inhibit',
            GLib.Variant('(ssss)',('idle:sleep','hics-tests','portal-session-churn','block')),
            GLib.VariantType.new('(h)'),Gio.DBusCallFlags.NONE,10000,None,None)
        index,=value.unpack();inhibitor=descriptors.get(index)
        try:exercise(args,{'source':'owned-fd','mode':'block','what':'idle:sleep'})
        finally:os.close(inhibitor)


def external_inhibitor(system):
    ancestors=set();pid=os.getppid()
    while pid>1 and pid not in ancestors:
        ancestors.add(pid)
        status=(Path('/proc')/str(pid)/'status').read_text()
        pid=int(next(line.split()[1] for line in status.splitlines() if line.startswith('PPid:')))
    result=system.call_sync('org.freedesktop.login1','/org/freedesktop/login1',
        'org.freedesktop.login1.Manager','ListInhibitors',None,GLib.VariantType.new('(a(ssssuu))'),
        Gio.DBusCallFlags.NONE,10000,None).unpack()[0]
    matches=[row for row in result if row[1]=='hics-tests' and row[2]=='portal-session-churn'
             and row[3]=='block' and row[4]==0 and row[5] in ancestors
             and {'idle','sleep'}.issubset(set(row[0].split(':')))]
    assert len(matches)==1,'Run under the dedicated root systemd-inhibit wrapper'
    row=matches[0]
    return {'source':'verified-root-ancestor','what':row[0],'mode':row[3],'pid':row[5]}


def exercise(args,inhibitor):
    bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
    destination='org.freedesktop.portal.Desktop';path='/org/freedesktop/portal/desktop'
    backend='org.freedesktop.impl.portal.desktop.hyprland'
    def invoke(target,object_path,interface,method,parameters,reply,timeout=10000):
        return bus.call_sync(target,object_path,interface,method,parameters,
                             GLib.VariantType.new(reply) if reply else None,
                             Gio.DBusCallFlags.NONE,timeout,None).unpack()
    # Resolve the service first, then pin its process identity throughout the run.
    invoke(backend,path,'org.freedesktop.DBus.Properties','Get',
           GLib.Variant('(ss)',('org.freedesktop.impl.portal.ScreenCast','version')),'(v)')
    owner,=invoke('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus',
                  'GetNameOwner',GLib.Variant('(s)',(backend,)),'(s)')
    pid,=invoke('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus',
                'GetConnectionUnixProcessID',GLib.Variant('(s)',(owner,)),'(u)')
    process=Path('/proc')/str(pid)
    assert (process/'exe').resolve()==args.expected_executable.resolve()
    start_ticks=(process/'stat').read_text().rsplit(')',1)[1].split()[19]
    with args.expected_executable.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    report={'status':'running','backendPid':pid,'backendSha256':sha,'iterations':args.iterations,
            'completed':0,'samples':[],'pickerRequested':False,'framesRequested':False,
            'expectedRedBaseline':args.expect_retained_requests,'logindIdleSleepInhibitor':inhibitor}
    def save():
        pending=args.output.with_suffix('.pending');pending.write_text(json.dumps(report,indent=2)+'\n');pending.replace(args.output)
    def sample():
        values={}
        for line in (process/'smaps_rollup').read_text().splitlines():
            if ':' in line:
                key,value=line.split(':',1)
                if key in ('Rss','Pss','Private_Dirty'):values[key]=int(value.split()[0])
        return {'cycle':report['completed'],'memoryKiB':values,'fds':len(list((process/'fd').iterdir())),
                'threads':len(list((process/'task').iterdir()))}
    def children(object_path):
        try:
            xml,=invoke(backend,object_path,'org.freedesktop.DBus.Introspectable','Introspect',None,'(s)')
        except GLib.Error as error:
            name=Gio.DBusError.get_remote_error(error)
            if name in ('org.freedesktop.DBus.Error.UnknownObject','org.freedesktop.DBus.Error.UnknownMethod'):return 0
            raise
        assert len(xml)<2*1024*1024,'Unexpected introspection size'
        return len(ET.fromstring(xml).findall('node'))
    responses={};waiting={'handle':None,'loop':None};session=None
    def response(connection,sender,object_path,interface,signal,parameters):
        responses[object_path]=parameters.unpack()
        if object_path==waiting['handle'] and waiting['loop']:waiting['loop'].quit()
    subscription=bus.signal_subscribe(destination,'org.freedesktop.portal.Request','Response',None,None,
                                      Gio.DBusSignalFlags.NONE,response)
    def create():
        token='hics_churn_'+uuid.uuid4().hex
        handle,=invoke(destination,path,'org.freedesktop.portal.ScreenCast','CreateSession',
                       GLib.Variant('(a{sv})',({'handle_token':GLib.Variant('s',token),
                                                'session_handle_token':GLib.Variant('s',token+'_session')},)),'(o)')
        loop=GLib.MainLoop();waiting.update(handle=handle,loop=loop);expired=False
        def deadline():
            nonlocal expired
            expired=True;loop.quit();return GLib.SOURCE_REMOVE
        timer=GLib.timeout_add(10000,deadline)
        try:
            if handle not in responses:loop.run()
            assert not expired,'CreateSession response timed out'
            code,result=responses.pop(handle);assert code==0,('CreateSession response',code)
            return handle,result['session_handle']
        finally:
            if not expired:GLib.source_remove(timer)
            waiting.update(handle=None,loop=None)
    save()
    try:
        report['samples'].append(sample());request_parent=session_parent=None
        for i in range(args.iterations):
            request,session=create()
            request_parent=request.rsplit('/',1)[0];session_parent=session.rsplit('/',1)[0]
            invoke(destination,session,'org.freedesktop.portal.Session','Close',None,'()')
            session=None
            report['completed']=i+1
            if (i+1)%100==0:report['samples'].append(sample());save()
        # An asynchronous roundtrip lets the backend finish its deferred close;
        # no arbitrary sleep is used as proof of resource destruction.
        loop=GLib.MainLoop();result={}
        def barrier(connection,reply):
            try:result['reply']=connection.call_finish(reply)
            except GLib.Error as error:result['error']=str(error)
            loop.quit()
        bus.call(backend,path,'org.freedesktop.DBus.Properties','Get',
                 GLib.Variant('(ss)',('org.freedesktop.impl.portal.ScreenCast','version')),
                 GLib.VariantType.new('(v)'),Gio.DBusCallFlags.NONE,10000,None,barrier)
        loop.run();assert 'error' not in result,result
        report['retainedRequests']=children(request_parent)
        report['retainedSessions']=children(session_parent)
        report['samples'].append(sample())
        assert (process/'stat').read_text().rsplit(')',1)[1].split()[19]==start_ticks,'Backend restarted'
        assert report['retainedSessions']==0,'Closed session objects remain registered'
        if args.expect_retained_requests:
            assert report['retainedRequests']>=args.iterations,'Expected cleanup defect was not reproduced'
            report['status']='red-baseline-reproduced'
        else:
            assert report['retainedRequests']==0,'Completed request objects remain registered'
            report['status']='passed'
    except BaseException:
        report['status']='failed';raise
    finally:
        if session:
            try:invoke(destination,session,'org.freedesktop.portal.Session','Close',None,'()')
            except GLib.Error:pass
        bus.signal_unsubscribe(subscription);save()
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
