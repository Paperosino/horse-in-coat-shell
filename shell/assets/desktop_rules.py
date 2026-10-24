"""Validated application and input-device rules using Hyprland's native Lua API."""
import argparse,json,math,re,sys,uuid
from feature_common import CONFIG,read_json,atomic_json,run,lua,output
APP=CONFIG/'application-rules.json';DEVICE=CONFIG/'device-rules.json';GENERATED=CONFIG/'rules.lua'

def applications():
 return [dict(address=w['address'],application=w.get('initialClass') or w.get('class',''),title=w.get('title',''),workspace=w.get('workspace',{}).get('id',1),monitor=w.get('monitor'),x=w.get('at',[0,0])[0],y=w.get('at',[0,0])[1],width=w.get('size',[800,600])[0],height=w.get('size',[800,600])[1],floating=w.get('floating',False)) for w in json.loads(run(['hyprctl','-j','clients'])) if w.get('mapped')]
def devices():
 d=json.loads(run(['hyprctl','-j','devices']));rows=[]
 for group in ('keyboards','mice','touch','tablets'):
  for item in d.get(group,[]):
   if item.get('name'):rows.append({'name':item['name'],'kind':group,'description':item.get('name'),'layout':item.get('layout','')})
 return rows

def validate_rule(r):
 if not isinstance(r,dict) or set(r)-{'id','name','enabled','application','title','regex','floating','fullscreen','monitor','workspace','x','y','width','height','opacity','idleInhibit','center','pin','mode','titlebar','decorate','noBlur','noShadow','noAnim','keepAspectRatio','noInitialFocus','focusOnActivate','borderSize','rounding','matchXwayland','matchModal'}:raise ValueError('Unknown application rule field')
 if 'id' in r and (not isinstance(r['id'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',r['id'])):raise ValueError('Invalid rule identifier')
 for key in ('name','application','title','monitor'):
  val=r.get(key,'')
  if not isinstance(val,str) or len(val)>256 or any(ord(c)<32 for c in val):raise ValueError('Invalid application rule text')
 if not r.get('application'):raise ValueError('Select an application to match')
 for k in ('enabled','regex','floating','fullscreen','center','pin','decorate','noBlur','noShadow','noAnim','keepAspectRatio','noInitialFocus','focusOnActivate','matchXwayland','matchModal'):
  if k in r and not isinstance(r[k],bool):raise ValueError('Expected a rule switch')
 if r.get('mode','all') not in ('all','stacking','scrolling','tiling','canvas'):raise ValueError('Invalid window mode')
 if r.get('titlebar','auto') not in ('auto','show','hide'):raise ValueError('Invalid titlebar policy')
 if r.get('regex'):
  for k in ('application','title'):
   if r.get(k):
    try:re.compile(r[k])
    except re.error as e:raise ValueError('Invalid matching expression: '+str(e)) from e
 for k,lo,hi in (('workspace',1,1000000),('x',-100000,100000),('y',-100000,100000),('width',100,16384),('height',80,16384),('borderSize',0,10),('rounding',0,60)):
  if k in r and (isinstance(r[k],bool) or not isinstance(r[k],int) or not lo<=r[k]<=hi):raise ValueError('Invalid application rule '+k)
 if 'opacity' in r and (isinstance(r['opacity'],bool) or not isinstance(r['opacity'],(int,float)) or not math.isfinite(r['opacity']) or not .1<=r['opacity']<=1):raise ValueError('Invalid window opacity')
 if r.get('idleInhibit','none') not in ('none','always','focus','fullscreen'):raise ValueError('Invalid idle inhibition mode')
 return r

def rule_lua(r):
 match={k:(r[k] if r.get('regex') else '^'+re.escape(r[k])+'$') for k in ('application','title') if r.get(k)}
 match['class']=match.pop('application')
 for source,dest in (('matchXwayland','xwayland'),('matchModal','modal')):
  if source in r:match[dest]=r[source]
 effects={'name':'hics-rule-'+r['id'],'match':match}
 for source,dest in (('floating','float'),('fullscreen','fullscreen'),('center','center'),('pin','pin'),('monitor','monitor'),('decorate','decorate'),('noBlur','no_blur'),('noShadow','no_shadow'),('noAnim','no_anim'),('keepAspectRatio','keep_aspect_ratio'),('noInitialFocus','no_initial_focus'),('focusOnActivate','focus_on_activate'),('borderSize','border_size'),('rounding','rounding')):
  if source in r and r[source]!='':effects[dest]=r[source]
 if r.get('workspace'):effects['workspace']=str(r['workspace'])
 if r.get('width') and r.get('height'):effects['size']=str(r['width'])+' '+str(r['height'])
 if 'x' in r and 'y' in r:effects['move']=str(r['x'])+' '+str(r['y'])
 if 'opacity' in r:effects['opacity']=str(r['opacity'])+' override'
 if 'idleInhibit' in r:effects['idle_inhibit']=r['idleInhibit']
 if r.get('titlebar','auto')!='auto':effects['hyprbars:no_bar']=r['titlebar']=='hide'
 return 'hyprstack_layouts.application_rule('+lua(r.get('mode','all'))+','+lua(effects)+')'

DEVICE_FIELDS={'sensitivity':('number',-1,1),'accel_profile':('choice',['','flat','adaptive']),'left_handed':('bool',),'natural_scroll':('bool',),'scroll_factor':('number',.1,10),'repeat_rate':('int',1,100),'repeat_delay':('int',100,2000),'kb_layout':('text',),'kb_variant':('text',),'kb_options':('text',),'tap-to-click':('bool',),'disable_while_typing':('bool',)}
def validate_device(d):
 if not isinstance(d,dict) or not isinstance(d.get('name'),str) or not d['name'] or len(d['name'])>256 or any(ord(c)<32 for c in d['name']) or not isinstance(d.get('values'),dict):raise ValueError('Invalid input device rule')
 for k,v in d['values'].items():
  if k not in DEVICE_FIELDS:raise ValueError('Unsupported device option')
  s=DEVICE_FIELDS[k]
  if s[0]=='bool' and not isinstance(v,bool):raise ValueError('Expected a device switch')
  if s[0] in ('number','int') and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not s[1]<=v<=s[2] or s[0]=='int' and int(v)!=v):raise ValueError('Invalid device numeric value')
  if s[0]=='choice' and v not in s[1]:raise ValueError('Invalid acceleration profile')
  if s[0]=='text' and (not isinstance(v,str) or len(v)>256 or not re.fullmatch('[A-Za-z0-9_,:+.-]*',v)):raise ValueError('Invalid keyboard option')
 return d

def regenerate(apps,devs):
 lines=['-- Generated by hics application and device rules.']
 for r in apps:
  validate_rule(r)
  if r.get('enabled',True):lines.append(rule_lua(r))
 for d in devs:validate_device(d);lines.append('hl.device('+lua({'name':d['name'],**d['values']})+')')
 return '\n'.join(lines)+'\n'

def save(apps,devs):
 from configuration_manager import JOURNAL
 from display_profiles import paths
 if read_json(JOURNAL):raise ValueError('Confirm or revert the desktop preview before editing rules')
 try:folder,_=paths()
 except ValueError:folder=None
 if folder and read_json(folder/'pending.json'):raise ValueError('Confirm display changes before editing rules')
 if len(apps)>256 or len(devs)>128:raise ValueError('Too many desktop rules')
 text=regenerate(apps,devs);before={p:p.read_bytes() if p.exists() else None for p in (APP,DEVICE,GENERATED,CONFIG/'hypr-user.lua')}
 try:
  atomic_json(APP,{'version':1,'rules':apps},private=True);atomic_json(DEVICE,{'version':1,'devices':devs},private=True)
  from configuration_manager import write_text
  write_text(GENERATED,text)
  hook=CONFIG/'hypr-user.lua';source=hook.read_text() if hook.exists() else ''
  if 'rules.lua' not in source:write_text(hook,source+'\n-- hics application and device rules\nlocal p='+lua(str(GENERATED))+';local f=io.open(p);if f then f:close();dofile(p) end\n')
  run(['hyprctl','reload']);errors=run(['hyprctl','configerrors'])
  if errors not in ('','ok'):raise ValueError(errors)
 except Exception:
  for p,data in before.items():
   if data is None:p.unlink(missing_ok=True)
   else:p.write_bytes(data)
  try:run(['hyprctl','reload'])
  except Exception:pass
  raise

def controls():
 from gtk_theme import window_controls
 return window_controls(CONFIG.parent)

def save_controls(value):
 from gtk_theme import validate_window_controls, sync_window_controls
 value=validate_window_controls(value)
 path=CONFIG/'window-controls.json';previous=path.read_bytes() if path.exists() else None
 try:
  atomic_json(path,value,private=True)
  sync_window_controls(CONFIG.parent)
  run(['hyprctl','reload'])
  errors=run(['hyprctl','configerrors'])
  if errors not in ('','ok'):raise ValueError(errors)
 except Exception:
  if previous is None:path.unlink(missing_ok=True)
  else:path.write_bytes(previous)
  sync_window_controls(CONFIG.parent)
  try:run(['hyprctl','reload'])
  except Exception:pass
  raise

def state():
 return {'rules':read_json(APP).get('rules',[]),'controls':controls(), 'deviceRules':read_json(DEVICE).get('devices',[]),'windows':applications(),'devices':devices()}
def dispatch(op,p):
 apps=read_json(APP).get('rules',[]);devs=read_json(DEVICE).get('devices',[])
 if op=='save-rule':
  r=validate_rule(p);r['id']=r.get('id') or str(uuid.uuid4());apps=[r if a['id']==r['id'] else a for a in apps] if any(a['id']==r['id'] for a in apps) else apps+[r];save(apps,devs)
 elif op=='delete-rule':save([a for a in apps if a['id']!=p.get('id')],devs)
 elif op=='save-controls':save_controls(p)
 elif op=='move-rule':
  index=next((i for i,a in enumerate(apps) if a['id']==p.get('id')),None)
  if index is None or p.get('direction') not in (-1,1):raise ValueError('Invalid rule order')
  target=max(0,min(len(apps)-1,index+p['direction']));apps.insert(target,apps.pop(index));save(apps,devs)
 elif op=='save-device':
  d=validate_device(p);save(apps,[r for r in devs if r['name']!=d['name']]+([d] if d['values'] else []))
 elif op!='status':raise ValueError('Unknown desktop rule operation')
 return state()
def main():
 p=argparse.ArgumentParser();p.add_argument('operation');args=p.parse_args()
 try:output(dispatch(args.operation,json.load(sys.stdin) if args.operation!='status' else {}));return 0
 except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':sys.exit(main())
