#!/usr/bin/env python3
"""Cancel our actual portal picker in a disposable CachyOS guest, without frames."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from gi.repository import Gio, GLib

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-executable',type=Path,required=True)
    parser.add_argument('--close',choices=('request','session'),required=True)
    parser.add_argument('--disposable-cachyos-vm',action='store_true',required=True)
    args=parser.parse_args()
    assert os.getuid()==1000 and Path('/etc/hostname').read_text().strip()=='hics-test'
    assert subprocess.check_output(['systemd-detect-virt'],text=True).strip() in ('kvm','qemu')
    assert not json.loads(subprocess.check_output(['hyprctl','-i','0','-j','locked'],text=True))['locked']
    assert not args.output.exists();os.umask(0o077);args.output.parent.mkdir(parents=True,exist_ok=True)
    bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);context=GLib.MainContext.default()
    frontend='org.freedesktop.portal.Desktop';backend='org.freedesktop.impl.portal.desktop.hyprland';path='/org/freedesktop/portal/desktop'
    def call(target,path,interface,method,signature=None,values=None,timeout=3000):
        return bus.call_sync(target,path,interface,method,GLib.Variant(signature,values) if signature else None,
                             None,Gio.DBusCallFlags.NONE,timeout,None).unpack()
    def responsive():return call(backend,path,'org.freedesktop.DBus.Properties','Get','(ss)',('org.freedesktop.impl.portal.ScreenCast','version'))
    responsive()
    owner,=call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner','(s)',(backend,))
    pid,=call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID','(s)',(owner,))
    process=Path('/proc')/str(pid);assert (process/'exe').resolve()==args.expected_executable.resolve()
    start=(process/'stat').read_text().rsplit(')',1)[1].split()[19]
    with args.expected_executable.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    report={'status':'running','backendPid':pid,'backendSha256':sha,'close':args.close,'framesRequested':False}
    def save():
        pending=args.output.with_suffix('.pending');pending.write_text(json.dumps(report,indent=2)+'\n');pending.replace(args.output)
    responses={}
    def response(connection,sender,path,interface,signal,values):responses[path]=values.unpack()
    subscription=bus.signal_subscribe(frontend,'org.freedesktop.portal.Request','Response',None,None,Gio.DBusSignalFlags.NONE,response)
    def pump():
        while context.pending():context.iteration(False)
    def until(check,timeout=5):
        end=time.monotonic()+timeout
        while not check():
            pump();assert time.monotonic()<end,'Condition deadline expired';time.sleep(.02)
    token='hics_'+uuid.uuid4().hex;session=None;request=None;childfd=None
    save()
    try:
        create,=call(frontend,path,'org.freedesktop.portal.ScreenCast','CreateSession','(a{sv})',
                     ({'handle_token':GLib.Variant('s',token),'session_handle_token':GLib.Variant('s',token+'_s')},))
        until(lambda:create in responses)
        code,result=responses.pop(create);assert code==0;session=result['session_handle']
        children=process/'task'/str(pid)/'children';assert not children.read_text().strip(),'Backend already has a picker: inspect first'
        request,=call(frontend,path,'org.freedesktop.portal.ScreenCast','SelectSources','(oa{sv})',
                     (session,{'handle_token':GLib.Variant('s',token+'_select'),'types':GLib.Variant('u',1),'persist_mode':GLib.Variant('u',0)}))
        until(lambda:bool(children.read_text().strip()),10)
        ids=children.read_text().split();assert len(ids)==1;child=int(ids[0]);childproc=Path('/proc')/str(child)
        childfd=os.pidfd_open(child);report['pickerPid']=child;save()
        def mapped():
            raw=subprocess.check_output(['hyprctl','-i','0','clients','-j'],text=True,timeout=3)
            assert len(raw)<4*1024*1024
            return any(window.get('pid')==child and window.get('mapped') is True for window in json.loads(raw))
        report['phase']='wait-picker-window';save()
        until(mapped,15);report['pickerWindowMapped']=True;save()
        # The backend must still dispatch D-Bus while its own child is alive.
        report['phase']='probe-responsive-with-picker';save()
        responsive();report['responsiveWithPickerOpen']=True
        report['phase']='cancel-picker';save()
        begin=time.monotonic()
        if args.close=='request':call(frontend,request,'org.freedesktop.portal.Request','Close')
        else:call(frontend,session,'org.freedesktop.portal.Session','Close');session=None
        report['closeReturned']=True
        responsive();report['responsiveAfterClose']=True
        assert select.select([childfd],[],[],3)[0],'Picker survives cancellation'
        until(lambda:not childproc.exists())
        report['pickerReaped']=True;report['cancelSeconds']=round(time.monotonic()-begin,3)
        if session:
            try:call(frontend,session,'org.freedesktop.portal.Session','Close')
            except GLib.Error as error:
                # Frontend cancellation may already destroy its own session.
                name=Gio.DBusError.get_remote_error(error)
                assert name in ('org.freedesktop.DBus.Error.UnknownObject','org.freedesktop.DBus.Error.UnknownMethod'),name
                report['frontendSessionAlreadyRemoved']=True
            session=None
        unique=bus.get_unique_name()[1:].replace('.','_')
        def count(kind):
            try:xml,=call(backend,path+'/'+kind+'/'+unique,'org.freedesktop.DBus.Introspectable','Introspect')
            except GLib.Error as error:
                if Gio.DBusError.get_remote_error(error) in ('org.freedesktop.DBus.Error.UnknownObject','org.freedesktop.DBus.Error.UnknownMethod'):return 0
                raise
            assert len(xml)<2*1024*1024;return len(ET.fromstring(xml).findall('node'))
        until(lambda:count('request')==0 and count('session')==0)
        assert (process/'stat').read_text().rsplit(')',1)[1].split()[19]==start
        report['retainedRequests']=count('request');report['retainedSessions']=count('session');report['status']='passed';report['phase']='complete'
    except BaseException as error:
        report['status']='failed';report['errorType']=type(error).__name__
        if isinstance(error,GLib.Error):report['remoteError']=Gio.DBusError.get_remote_error(error)
        save();raise
    finally:
        if childfd is not None:os.close(childfd)
        if session:
            try:call(frontend,session,'org.freedesktop.portal.Session','Close')
            except GLib.Error as error:report['cleanupError']=Gio.DBusError.get_remote_error(error)
        bus.signal_unsubscribe(subscription);save()
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
