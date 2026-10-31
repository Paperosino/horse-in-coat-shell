#!/usr/bin/env python3
"""Validated compositor layout options; configuration and runtime mode stay in sync."""
import json,math,sys,os
from pathlib import Path
from feature_common import CONFIG,atomic_json,read_json,run,lua,output
MODES=('tiling','scrolling','stacking','canvas')
DEFAULT={'mode':'scrolling','canvasZoom':0.72,'canvasMinZoom':0.1,'canvasMaxZoom':2.5,'canvasZoomStep':0.12,'canvasPanSpeed':1.0,'canvasGap':40,'canvasGrid':True,'canvasSnap':False,'canvasSnapSize':40,'canvasMinimap':True,'canvasRemember':True,'canvasHoverFocus':False,'canvasSticky':False,'overviewDragMs':35,'overviewMotionMs':320,'stackFocusMotion':'expressive'}
RANGES={'canvasZoom':(.1,2),'canvasMinZoom':(.05,1),'canvasMaxZoom':(1,5),'canvasZoomStep':(.01,.5),'canvasPanSpeed':(.1,5),'canvasGap':(0,300),'canvasSnapSize':(24,300),'overviewDragMs':(0,120),'overviewMotionMs':(120,700)}
BOOLS={'canvasSticky','canvasGrid','canvasSnap','canvasMinimap','canvasRemember','canvasHoverFocus'}
FILE=CONFIG/'layouts.json'
def config():
 c={**DEFAULT,**read_json(FILE)}
 c['canvasAvailable']=any((p/'native/libspatialoverview.so').is_file() for p in [Path(os.environ.get('HYPRSTACK_DATA_DIR','/usr/share/hics')),Path(__file__).resolve().parents[2]])
 return c

def validate(value):
 if not isinstance(value,dict):raise ValueError('Expected layout settings')
 result={k:v for k,v in config().items() if k!='canvasAvailable'}
 for k,v in value.items():
  if k == 'stackFocusMotion':
   if v not in ('off','expressive','standard','heavy','jelly'):raise ValueError('Unknown stacking animation')
  elif k in BOOLS:
   if not isinstance(v,bool):raise ValueError('Expected a switch value')
  elif k in RANGES:
   if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('Expected a finite number')
   if k in {'canvasGap','canvasSnapSize','overviewDragMs','overviewMotionMs'} and not isinstance(v,int):raise ValueError('Expected a whole number')
   if not RANGES[k][0]<=v<=RANGES[k][1]:raise ValueError('Setting is outside its supported range')
  else:raise ValueError('Unknown layout setting')
  result[k]=v
 if not result['canvasMinZoom']<=result['canvasZoom']<=result['canvasMaxZoom']:raise ValueError('Initial zoom must lie between the minimum and maximum')
 return result

def execute(code):
 text=run(['hyprctl','repl',code],timeout=15).strip()
 if text.startswith('error:'):raise ValueError(text.removeprefix('error:').strip())
 return text

def main():
 try:
  command=sys.argv[1] if len(sys.argv)>1 else 'config'
  if command=='config':result=config()
  elif command=='mode':
   mode=sys.argv[2]
   if mode not in MODES:raise ValueError('Unknown layout mode')
   execute('return hyprstack_layouts.set_mode('+lua(mode)+')');result=config()
  elif command=='save':
   value=validate(json.load(sys.stdin));execute('hyprstack_layouts.configure('+lua(value)+')');result=config()
  elif command=='action':
   action=' '.join(sys.argv[2:])
   if action not in ['fit','frame','arrange','undo','redo','zoom in','zoom out','zoom reset','pan left','pan right','pan up','pan down']:raise ValueError('Unknown canvas action')
   execute('hyprstack_layouts.canvas_action('+lua(action)+')');result=config()
  else:raise ValueError('Unknown layout operation')
  output(result);return 0
 except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':raise SystemExit(main())
