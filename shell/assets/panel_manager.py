"""Additional horizontal panels; each has an independent typed config layer."""
import argparse,json,re,sys,uuid
from feature_common import CONFIG,read_json,atomic_json,output
PATH=CONFIG/'panels.json'
ID=re.compile(r'^[a-f0-9-]{36}$')

def state():
    value=json.loads(PATH.read_text()) if PATH.exists() else {}
    if not isinstance(value,dict) or not isinstance(value.get('panels',[]),list) or not isinstance(value.get('removed',[]),list):raise ValueError('Invalid panel registry')
    if len(value.get('panels',[]))>32 or len(value.get('removed',[]))>16:raise ValueError('Panel registry is too large')
    for panel in value.get('panels',[])+value.get('removed',[]):validate(panel)
    return {'panels':value.get('panels',[]),'removed':value.get('removed',[])}

def validate(panel):
    if not isinstance(panel,dict) or set(panel)-{'id','name','screen','edge','thickness','autoHide','hideDelay','order'}:raise ValueError('Invalid panel fields')
    if not ID.fullmatch(panel.get('id','')):raise ValueError('Invalid panel identifier')
    for key in ('name','screen'):
        if not isinstance(panel.get(key),str) or not panel[key].strip() or len(panel[key])>256:raise ValueError('Invalid panel '+key)
    if panel.get('edge') not in ('top','bottom'):raise ValueError('Invalid panel edge')
    if not isinstance(panel.get('autoHide'),bool):raise ValueError('Invalid panel visibility')
    for key,low,high in (('thickness',28,96),('hideDelay',100,3000),('order',0,31)):
        if isinstance(panel.get(key),bool) or not isinstance(panel.get(key),int) or not low<=panel[key]<=high:raise ValueError('Invalid panel '+key)
    return panel

def layer(panel):return CONFIG/'monitors'/('panel-'+panel['id'])/'shell.json'

def save(value):
    if len(value['panels'])>32:raise ValueError('At most 32 panels are supported')
    for panel in value['panels']:validate(panel)
    atomic_json(PATH,value)
    for panel in value['panels']:
        path=layer(panel);config=read_json(path);bar=config.setdefault('bar',{})
        bar['persistent']=not panel['autoHide'];bar['excludedScreens']=[]
        if 'entries' not in bar:bar['entries']=[{'id':i,'enabled':True} for i in ('logo','spacer','clock','spacer','statusIcons')]
        atomic_json(path,config)
    return state()

def apply(op,identifier='',payload=None):
    value=state()
    if op=='list':return value
    if op=='add':
        screen=(payload or {}).get('screen')
        panel=dict(id=str(uuid.uuid4()),name='Panel',screen=screen,edge='bottom',thickness=48,autoHide=False,hideDelay=500,order=len(value['panels']))
        value['panels'].append(validate(panel))
    else:
        if not ID.fullmatch(identifier):raise ValueError('Invalid panel identifier')
        found=next((p for p in value['panels'] if p['id']==identifier),None)
        if op=='update':
            if not found or not isinstance(payload,dict) or 'id' in payload:raise ValueError('Invalid panel update')
            found.update(payload);validate(found)
        elif op=='remove':
            if not found:raise ValueError('Panel not found')
            value['panels'].remove(found);value['removed']=(value['removed']+[found])[-16:]
        elif op=='restore':
            found=next((p for p in value['removed'] if p['id']==identifier),None)
            if not found or any(p['id']==identifier for p in value['panels']):raise ValueError('Panel cannot be restored')
            value['removed'].remove(found);value['panels'].append(found)
        else:raise ValueError('Unknown panel operation')
    return save(value)

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['list','add','update','remove','restore']);p.add_argument('id',nargs='?',default='');args=p.parse_args()
    try:output(apply(args.operation,args.id,json.load(sys.stdin) if args.operation in ('add','update') else None));return 0
    except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':sys.exit(main())
