"""Read-only diagnostics and explicit, redacted local issue reports."""
import argparse,json,os,re,subprocess,sys,time
from pathlib import Path
from diagnostics import checks
from configuration_manager import write_text
from feature_common import output
UNITS=('hic-session.service','hics-displays.service','hics-configuration.service','hics-screen-reader.service')
def capture(argv):
 try:
  p=subprocess.run(argv,capture_output=True,text=True,timeout=12);return (p.stdout or p.stderr).strip()[:40000]
 except (OSError,subprocess.SubprocessError) as e:return str(e)
def redact(text):
 text=text.replace(str(Path.home()),'~');text=re.sub(r'(?i)(password|passwd|token|secret|api[_-]?key)([=: ]+)[^\s,;]+',r'\1\2[redacted]',text)
 text=re.sub(r'(?i)(https?://)[^/@\s]+:[^/@\s]+@',r'\1[redacted]@',text)
 return text

def report(logs=False):
 units=[]
 for name in UNITS:
  raw=capture(['systemctl','--user','show',name,'-p','LoadState','-p','ActiveState','-p','SubState','-p','Result','-p','NRestarts','-p','MemoryCurrent'])
  values=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
  units.append({'id':name,**values})
 result={'version':1,'created':int(time.time()),'checks':checks(),'units':units,'hyprlandErrors':capture(['hyprctl','configerrors']),'plugins':[]}
 try:
  from plugin_manager import scan
  data=scan();result['plugins']=[{'id':p['id'],'enabled':p['enabled'],'compatible':p['compatible'],'issues':p['issues']} for p in data['plugins']];result['extensionRecovery']=data.get('recoveryMode',False)
 except Exception as e:result['pluginError']=str(e)
 if logs:result['logs']=redact(capture(['journalctl','--user',*[arg for unit in UNITS for arg in ('-u',unit)],'--lines=160','--no-pager','-o','short-iso']))
 def scrub(value):
  if isinstance(value,str):return redact(value)
  if isinstance(value,list):return [scrub(v) for v in value]
  if isinstance(value,dict):return {k:scrub(v) for k,v in value.items()}
  return value
 return scrub(result)
def main():
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['status','report','export','restart']);args=p.parse_args()
 try:
  value=json.load(sys.stdin) if args.operation!='status' else {}
  if args.operation=='restart':
   name=value.get('unit')
   if name not in UNITS:raise ValueError('Unsupported desktop service')
   subprocess.run(['systemctl','--user','restart',name],check=True,capture_output=True,text=True,timeout=25)
  data=report(bool(value.get('logs',False)))
  if args.operation=='export':
   path=Path(value['path']).expanduser()
   if not path.is_absolute():raise ValueError('Choose a local report destination')
   write_text(path,json.dumps(data,ensure_ascii=False,indent=2))
  output(data);return 0
 except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':sys.exit(main())
