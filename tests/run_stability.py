#!/usr/bin/env python3
"""Run each unit-test module in an isolated process with bounded resources/time.

This does not claim VM, UI or hardware coverage. Each result points to its
complete log; timeouts and missing dependencies remain visible as failures/skips.
"""
import argparse, datetime, hashlib, json, os, re, signal, subprocess, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def write_json(path,value):
    temporary=path.with_suffix('.pending')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--pattern',default='test_*.py')
    parser.add_argument('--timeout',type=int,default=300)
    args=parser.parse_args()
    os.umask(0o077)
    os.nice(5)
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    modules=sorted((ROOT/'tests').glob(args.pattern))
    if not modules:raise SystemExit('No test modules selected')
    results=[]
    manifest={'started':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
              'scope':'isolated unit modules; not a complete desktop/VM acceptance test',
              'planned':[p.name for p in modules],'results':results}
    dirty_files={}
    for raw in subprocess.check_output(['git','ls-files','-z','--modified','--others','--exclude-standard'],cwd=ROOT).split(b'\0'):
        if not raw:continue
        path=ROOT/os.fsdecode(raw)
        if path.is_file():
            with path.open('rb') as stream:dirty_files[os.fsdecode(raw)]=hashlib.file_digest(stream,'sha256').hexdigest()
    manifest['dirtyFilesSha256']=dirty_files
    write_json(out/'manifest.json',manifest)
    for index,module in enumerate(modules,1):
        started=time.monotonic();timed_out=False
        logfile=out/(module.stem+'.log')
        with tempfile.TemporaryDirectory(prefix='hics-test-') as temporary:
            base=Path(temporary);runtime=base/'runtime';runtime.mkdir(mode=0o700)
            env=dict(os.environ,HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'config'),
                     XDG_DATA_HOME=str(base/'data'),XDG_STATE_HOME=str(base/'state'),XDG_CACHE_HOME=str(base/'cache'),
                     XDG_RUNTIME_DIR=str(runtime),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(runtime/'absent-session'),
                     DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(runtime/'absent-system'),QT_QPA_PLATFORM='offscreen',
                     PYTHONPYCACHEPREFIX=str(base/'pycache'),HICS_CONFIG_NO_SYSTEMD='1',HICS_DISPLAY_NO_SYSTEMD='1')
            for key in ('HYPRLAND_INSTANCE_SIGNATURE','WAYLAND_DISPLAY','DISPLAY','HICS_SAFE_MODE','FONTCONFIG_FILE'):
                env.pop(key,None)
            Path(env['HOME']).mkdir()
            with logfile.open('wb') as log:
                child=subprocess.Popen([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p',module.name],
                                       cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=child.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    timed_out=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
                finally:
                    try:os.killpg(child.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
            with logfile.open('rb') as stream:
                stream.seek(-min(12000,logfile.stat().st_size),os.SEEK_END)
                tail=stream.read(12000).decode(errors='replace')
            count=re.search(r'Ran (\d+) tests?',tail)
            skipped=re.search(r'skipped=(\d+)',tail)
            row={'module':module.name,'status':'timeout' if timed_out else 'pass' if code==0 else 'fail',
                 'exitCode':code,'seconds':round(time.monotonic()-started,3),'tests':int(count[1]) if count else None,
                 'skipped':int(skipped[1]) if skipped else 0,'log':str(logfile)}
            results.append(row);write_json(out/'manifest.json',manifest)
            print(f'[{index}/{len(modules)}] {row["status"]}: {module.name} ({row["seconds"]}s)',flush=True)
    manifest['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_json(out/'manifest.json',manifest)
    return 1 if any(r['status']!='pass' for r in results) else 0


if __name__=='__main__':raise SystemExit(main())
