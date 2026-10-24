"""Resumable, optional first-run setup and a licensed wallpaper collection."""
import argparse,hashlib,json,os,shutil,subprocess,sys,time,urllib.request
from pathlib import Path
from feature_common import CONFIG,STATE,read_json,atomic_json,output
from application_environment import application_environment
PREFS=CONFIG/'onboarding.json';ASSETS=Path(__file__).resolve().parent
STEPS=('welcome','locale','keyboard','displays','windows','theme','wallpapers','storage','features','ready')

def pictures():
 p=subprocess.run(['xdg-user-dir','PICTURES'],env=application_environment(),capture_output=True,text=True,timeout=5)
 return Path(p.stdout.strip()) if p.returncode==0 and p.stdout.strip() else Path.home()/'Pictures'

def directory():
 value=read_json(CONFIG/'shell.json').get('paths',{}).get('wallpaperDir')
 return Path(value).expanduser()/'hics-collection' if value else pictures()/'Wallpapers/hics-collection'

def state():
 d={'version':1,'state':'new','step':0,'autoShow':True,'showDemos':True,'reducedMotion':False,'language':'',**read_json(PREFS)}
 if d['step'] not in range(len(STEPS)) or d['state'] not in ('new','in-progress','completed','skipped'):raise ValueError('Invalid first-run setup state')
 names=set(read_json(ASSETS/'feature_data/wallpaper-collection.json').get('images',[]))
 files=sorted(p for p in directory().glob('*.jpg') if p.stem in names) if directory().is_dir() else []
 return {'settings':d,'steps':list(STEPS),'wallpapers':[{'path':str(p),'name':p.stem.replace('-',' ')} for p in files], 'collection':read_json(ASSETS/'feature_data/wallpaper-collection.json')}

def download():
 manifest=read_json(ASSETS/'feature_data/wallpaper-collection.json');root=directory();originals=root/'.originals';originals.mkdir(parents=True,exist_ok=True)
 records=[]
 for name in manifest['images']:
  original=originals/(name+'.jxl');target=root/(name+'.jpg');url='https://raw.githubusercontent.com/GNOME/gnome-backgrounds/'+manifest['revision']+'/backgrounds/'+name+'.jxl'
  if not original.is_file():
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'hics-setup/1'}),timeout=25) as response:
    data=response.read(24*1024*1024+1)
   if len(data)>24*1024*1024:raise ValueError('Wallpaper download is too large')
   tmp=original.with_suffix('.part');tmp.write_bytes(data);os.replace(tmp,original)
  if not target.is_file():
   tmp=target.with_suffix('.part.jpg')
   try:
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(original),'-vf','scale=3840:2160:force_original_aspect_ratio=decrease','-frames:v','1','-q:v','2','-y',str(tmp)],env=application_environment(),capture_output=True,check=True,timeout=45)
    os.replace(tmp,target)
   finally:tmp.unlink(missing_ok=True)
  records.append({'name':name,'source':url,'sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'image':target.name,'original':str(original.relative_to(root))})
 atomic_json(root/'ATTRIBUTION.json',{**manifest,'downloaded':int(time.time()),'files':records})
 (root/'LICENSE.txt').write_text('GNOME Backgrounds · '+manifest['license']+'\n'+manifest['licenseUrl']+'\n'+manifest['credit']+'\nOriginal source images and embedded author metadata are retained in .originals. JPEG previews are format conversions.\n')
 return state()

def dispatch(op,p):
 if op=='status':return state()
 d=state()['settings']
 if op=='wallpapers':return download()
 if op=='open':d.update(state='in-progress',step=p.get('step',d['step']))
 elif op=='skip':d.update(state='skipped',autoShow=False)
 elif op=='finish':d.update(state='completed',autoShow=False,step=len(STEPS)-1)
 elif op=='configure':
  if not isinstance(p,dict) or set(p)-{'step','autoShow','showDemos','reducedMotion','language'}:raise ValueError('Unknown first-run setting')
  for key,value in p.items():
   if key=='step' and (isinstance(value,bool) or not isinstance(value,int) or not 0<=value<len(STEPS)):raise ValueError('Invalid setup step')
   if key in ('autoShow','showDemos','reducedMotion') and not isinstance(value,bool):raise ValueError('Expected a setup switch')
   if key=='language' and value not in ('','ru_RU','en_US'):raise ValueError('Unsupported shell language')
  d.update(p)
  if p.get('autoShow') and d['state'] in ('completed','skipped'):d.update(state='new',step=0)
 else:raise ValueError('Unknown first-run operation')
 atomic_json(PREFS,d,private=True);return state()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('operation');args=parser.parse_args()
 try:output(dispatch(args.operation,json.load(sys.stdin) if args.operation not in ('status','wallpapers') else {}));return 0
 except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':sys.exit(main())
