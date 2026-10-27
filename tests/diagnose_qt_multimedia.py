#!/usr/bin/env python3
"""Audit audio-only Qt Multimedia initialization on private D-Bus/audio endpoints.

No hardware-backend disable variables or leak suppressions are used. Exit 2
means audio enumeration loaded a GPU driver; sanitizer failures remain failures.
This does not test real capture, video playback or prove long-term RSS stability.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

PROBE=r'''
#include <QCoreApplication>
#include <QMediaDevices>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <QAudioDevice>
int main(int argc,char **argv){
 QCoreApplication app(argc,argv);int inputs=0,outputs=0;
 for(int i=0;i<200;++i){inputs=QMediaDevices::audioInputs().size();outputs=QMediaDevices::audioOutputs().size();}
 QTimer::singleShot(200,&app,&QCoreApplication::quit);app.exec();
 QFile file("/proc/self/maps");if(!file.open(QIODevice::ReadOnly))return 3;
 const auto maps=file.readAll();QJsonObject result{{"audioInputs",inputs},{"audioOutputs",outputs},
  {"cudaLoaded",maps.contains("/libcuda.so")},{"vdpauLoaded",maps.contains("/libvdpau_")},
  {"ffmpegBackendLoaded",maps.contains("/libffmpegmediaplugin.so")}};
 const auto forbidden=qgetenv("HICS_QT_FORBID_MAPS");
 if(!forbidden.isEmpty()&&maps.contains(forbidden))return 4;
 const auto plugin=qgetenv("HICS_QT_MULTIMEDIA_REQUIRED_PLUGIN");
 if(!plugin.isEmpty()&&!maps.contains(plugin))return 5;
 QFile out;out.open(stdout,QIODevice::WriteOnly);out.write(QJsonDocument(result).toJson(QJsonDocument::Compact));out.write("\n");
 return 0;
}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--qt-overlay',type=Path)
    parser.add_argument('--asan',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--probe-binary',type=Path)
    parser.add_argument('--export-probe',type=Path)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh evidence path')
    with tempfile.TemporaryDirectory(prefix='hics-multimedia-audio-') as directory:
        base=Path(directory);source=base/'probe.cpp';source.write_text(PROBE)
        sanitizer=['-fsanitize=address','-fno-omit-frame-pointer','-g'] if args.asan else []
        if args.probe_binary:shutil.copy2(args.probe_binary,base/'probe')
        else:
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Multimedia'],text=True))
            subprocess.run(['c++','-std=c++20','-fPIC',*sanitizer,str(source),*flags,'-o',str(base/'probe')],check=True,capture_output=True,timeout=30)
        if args.export_probe:shutil.copy2(base/'probe',args.export_probe)
        config=base/'bus.conf';config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(base)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(config)],stdout=subprocess.PIPE,text=True)
        try:
            address=bus.stdout.readline().strip();assert address
            runtime=base/'run';runtime.mkdir(mode=0o700)
            env=dict(os.environ,HOME=str(base),XDG_RUNTIME_DIR=str(runtime),XDG_CONFIG_HOME=str(base/'config'),
                XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),
                DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address,PIPEWIRE_REMOTE='hics-audio-absent',
                PULSE_SERVER='unix:'+str(base/'absent-pulse'),QT_FORCE_STDERR_LOGGING='1',QT_LOGGING_RULES='qt.multimedia.ffmpeg.debug=false',
                LD_LIBRARY_PATH=str(args.runtime/'lib'),QT_PLUGIN_PATH=str(args.runtime/'lib/qt6/plugins'))
            env['HICS_QT_MULTIMEDIA_REQUIRED_PLUGIN']=str(args.runtime/'lib/qt6/plugins/multimedia/libffmpegmediaplugin.so')
            for name in ('QT_FFMPEG_DECODING_HW_DEVICE_TYPES','QT_FFMPEG_ENCODING_HW_DEVICE_TYPES','LSAN_OPTIONS'):
                env.pop(name,None)
            if args.asan:env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
            if args.qt_overlay:
                env['LD_LIBRARY_PATH']=str(args.qt_overlay/'lib')+':'+env['LD_LIBRARY_PATH']
                env['QT_PLUGIN_PATH']=str(args.qt_overlay/'plugins')+':'+env['QT_PLUGIN_PATH']
                env['HICS_QT_MULTIMEDIA_REQUIRED_PLUGIN']=str(args.qt_overlay/'plugins/multimedia/libffmpegmediaplugin.so')
            result=subprocess.run([str(base/'probe')],env=env,capture_output=True,text=True,timeout=30)
            report={'runtime':str(args.runtime),'overlay':str(args.qt_overlay) if args.qt_overlay else None,
                'sanitizers':args.asan,'returncode':result.returncode,'probeSha256':hashlib.sha256((base/'probe').read_bytes()).hexdigest(),
                'observed':json.loads(result.stdout) if result.stdout.strip().startswith('{') else None}
            args.output.with_suffix('.log').write_text(result.stderr)
            args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
            if result.returncode:return 1
            assert report['observed'] and report['observed']['ffmpegBackendLoaded'],'Expected real FFmpeg backend was not loaded'
            return 2 if report['observed']['cudaLoaded'] or report['observed']['vdpauLoaded'] else 0
        finally:
            bus.terminate();bus.wait(timeout=5);bus.stdout.close()

if __name__=='__main__':raise SystemExit(main())
