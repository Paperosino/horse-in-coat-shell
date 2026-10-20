#!/usr/bin/env python3
"""XDG defaults without executing desktop entries or changing unrelated formats."""
import configparser,json,os,re,sys,subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
MIME_CATEGORIES = {
 'browser':['x-scheme-handler/https','x-scheme-handler/http','text/html','application/xhtml+xml'],
 'fileManager':['inode/directory'],
 'textEditor':['text/plain','text/markdown','application/json','text/x-python','application/x-shellscript','application/yaml','text/yaml','application/xml'],
 'imageViewer':['image/png','image/jpeg','image/webp','image/gif','image/svg+xml','image/bmp','image/tiff','image/avif'],
 'videoPlayer':['video/mp4','video/webm','video/x-matroska','video/quicktime','video/x-msvideo','video/mpeg'],
 'audioPlayer':['audio/mpeg','audio/flac','audio/ogg','audio/x-wav','audio/aac','audio/mp4','audio/opus'],
 'pdfViewer':['application/pdf'], 'ebookReader':['application/epub+zip','application/x-mobipocket-ebook'],
 'archiveManager':['application/zip','application/x-7z-compressed','application/x-rar','application/vnd.rar','application/x-tar','application/gzip','application/x-xz','application/x-bzip2'],
 'wordProcessor':['application/vnd.oasis.opendocument.text','application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/rtf'],
 'spreadsheet':['application/vnd.oasis.opendocument.spreadsheet','application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','text/csv'],
 'presentation':['application/vnd.oasis.opendocument.presentation','application/vnd.ms-powerpoint','application/vnd.openxmlformats-officedocument.presentationml.presentation'],
 'mailClient':['x-scheme-handler/mailto','message/rfc822'],
 'torrentClient':['application/x-bittorrent','x-scheme-handler/magnet']}

def config_home():return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))
def app_dirs():return [Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'applications',*[Path(x)/'applications' for x in os.environ.get('XDG_DATA_DIRS','/usr/local/share:/usr/share').split(':') if x]]
def desktop_files():
 result={}
 for root in app_dirs():
  if root.is_dir():
   for p in root.rglob('*.desktop'):result.setdefault(str(p.relative_to(root)).replace('/','-'),p)
 return result

def read_ini(path):
 c=configparser.ConfigParser(interpolation=None,strict=False);c.optionxform=str
 if path.exists():
  with path.open(encoding='utf-8') as f:c.read_file(f)
 return c

def mime_paths():
 names=[x.lower()+'-mimeapps.list' for x in os.environ.get('XDG_CURRENT_DESKTOP','').split(':') if re.fullmatch(r'[\w-]+',x)]+['mimeapps.list']
 dirs=[config_home(),*[Path(x) for x in os.environ.get('XDG_CONFIG_DIRS','/etc/xdg').split(':') if x],*app_dirs()]
 return [d/n for d in dirs for n in names]

def query_all():
 files=desktop_files();associations={}
 for path in mime_paths():
  try:c=read_ini(path)
  except (OSError,configparser.Error):continue
  if c.has_section('Default Applications'):
   for mime,value in c['Default Applications'].items():
    if mime not in associations:
     app=next((x for x in value.split(';') if x in files),'')
     if app:associations[mime]=app
 defaults={key:next((associations[m] for m in mimes if associations.get(m)),'') for key,mimes in MIME_CATEGORIES.items()}
 def fallback(item):
  key,mimes=item
  if defaults[key]:return key,defaults[key]
  try:
   result=subprocess.run(['xdg-mime','query','default',mimes[0]],capture_output=True,text=True,timeout=3)
   app=result.stdout.strip()
   return key,app if result.returncode==0 and app in files else ''
  except (OSError,subprocess.TimeoutExpired):return key,''
 with ThreadPoolExecutor(max_workers=6) as pool:defaults.update(pool.map(fallback,MIME_CATEGORIES.items()))
 candidates={key:[] for key in MIME_CATEGORIES}
 for app,path in files.items():
  try:
   c=read_ini(path);entry=c['Desktop Entry'];types=set(entry.get('MimeType','').split(';'))
   if entry.get('Hidden','false').lower()=='true':continue
   for key,mimes in MIME_CATEGORIES.items():
    if types.intersection(mimes):candidates[key].append(app.removesuffix('.desktop'))
  except (OSError,configparser.Error,KeyError):continue
 return {'defaults':defaults,'candidates':candidates,'formats':MIME_CATEGORIES}

def set_default(category,desktop_id):
 if category not in MIME_CATEGORIES:raise ValueError('Unknown file category')
 if not desktop_id.endswith('.desktop'):desktop_id+='.desktop'
 if '/' in desktop_id or desktop_id not in desktop_files():raise ValueError('Application is no longer installed')
 # Desktop-specific overrides have precedence over the generic file. Preserve
 # them and update the same formats there if that user file already exists.
 paths=[config_home()/'mimeapps.list']
 for desktop in os.environ.get('XDG_CURRENT_DESKTOP','').split(':'):
  if re.fullmatch(r'[\w-]+',desktop):
   p=config_home()/(desktop.lower()+'-mimeapps.list')
   if p.exists():paths.append(p)
 staged=[]
 import io,tempfile
 for p in paths:
  c=read_ini(p)
  if not c.has_section('Default Applications'):c.add_section('Default Applications')
  for mime in MIME_CATEGORIES[category]:c['Default Applications'][mime]=desktop_id+';'
  out=io.StringIO();c.write(out,space_around_delimiters=False);staged.append((p,out.getvalue()))
 for p,text in staged:
  p.parent.mkdir(parents=True,exist_ok=True)
  fd,name=tempfile.mkstemp(dir=p.parent,prefix='.mimeapps-')
  try:
   with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(text)
   os.replace(name,p)
  finally:Path(name).unlink(missing_ok=True)
 return query_all()

def main():
 try:
  if len(sys.argv)>1:
   if len(sys.argv)!=4 or sys.argv[1]!='set':raise ValueError('Expected set CATEGORY DESKTOP_ID')
   result=set_default(sys.argv[2],sys.argv[3])
  else:result=query_all()
  print(json.dumps(result));return 0
 except Exception as e:print(json.dumps({'error':str(e)}));return 1
if __name__=='__main__':raise SystemExit(main())
