#!/usr/bin/env python3
"""Readonly CPU comparison for N GPU readings; not a whole-shell/FPS benchmark."""
import argparse,json,resource,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--samples',type=int,default=10);args=p.parse_args();assert 1<=args.samples<=30
helper=ROOT/'build/native/system/hics-gpu-monitor'
def cpu():
 r=resource.getrusage(resource.RUSAGE_CHILDREN);return r.ru_utime+r.ru_stime
result={};start=cpu();wall=time.monotonic()
for _ in range(args.samples):subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,check=True,timeout=3)
result['nvidia-smi']={'processes':args.samples,'childCpuSeconds':round(cpu()-start,6),'elapsedSeconds':round(time.monotonic()-wall,6)}
start=cpu();wall=time.monotonic();run=subprocess.run([str(helper)],input='sample\n'*args.samples,capture_output=True,text=True,check=True,timeout=5)
rows=[json.loads(line) for line in run.stdout.splitlines()];assert len(rows)==args.samples and all(row['available'] for row in rows)
result['native-helper']={'processes':1,'samples':len(rows),'childCpuSeconds':round(cpu()-start,6),'elapsedSeconds':round(time.monotonic()-wall,6)}
print(json.dumps(result,indent=2))
