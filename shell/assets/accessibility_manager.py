"""Screen-reader lifecycle and Orca's supported GSettings controls."""
import argparse,json,re,shutil,subprocess,sys
from feature_common import CONFIG,read_json,atomic_json,output
from application_environment import application_environment
PATH=CONFIG/'accessibility.json'
UNIT='hics-screen-reader.service'
FIELDS={
 'rate':('Voice','voice-sets/primary/default','rate','i',0,100),
 'pitch':('Voice','voice-sets/primary/default','pitch','d',0,10),
 'volume':('Voice','voice-sets/primary/default','volume','d',0,10),
 'speech':('Speech','speech','enable','b',None,None),
 'characterEcho':('TypingEcho','typing-echo','character-echo','b',None,None),
 'wordEcho':('TypingEcho','typing-echo','word-echo','b',None,None),
 'mouseReview':('MouseReview','mouse-review','enabled','b',None,None),
 'braille':('Braille','braille','enabled','b',None,None),
}

def run(args,check=True):
    p=subprocess.run(args,env=application_environment(),capture_output=True,text=True,timeout=15)
    if check and p.returncode:raise ValueError((p.stderr or p.stdout).strip())
    return p

def gi():
    from gi.repository import Gio,GLib
    return Gio,GLib

def settings(schema,path):
    Gio,_=gi();source=Gio.SettingsSchemaSource.get_default()
    if not source or not source.lookup(schema,True):return None
    return Gio.Settings.new_with_path(schema,path)

def snapshot():
    prefs={'enabled':False,'autostart':False,'profile':'default',**read_json(PATH)}
    if not re.fullmatch('[a-zA-Z0-9-]{1,64}',str(prefs['profile'])):raise ValueError('Invalid Orca profile')
    values={};supported=[]
    for key,(schema,suffix,name,kind,*_) in FIELDS.items():
        obj=settings('org.gnome.Orca.'+schema,'/org/gnome/orca/'+prefs['profile']+'/'+suffix+'/')
        if obj and name in obj.props.settings_schema.list_keys():supported.append(key);values[key]=obj.get_value(name).unpack()
    return {'available':bool(shutil.which('orca')),'running':run(['systemctl','--user','is-active','--quiet',UNIT],False).returncode==0,'settings':prefs,'values':values,'supported':supported}

def configure(values):
    Gio,GLib=gi();prefs={'enabled':False,'autostart':False,'profile':'default',**read_json(PATH)}
    if set(values)-set(FIELDS)-{'enabled','autostart','profile'}:raise ValueError('Unknown accessibility setting')
    if 'profile' in values:
        if not isinstance(values['profile'],str) or not re.fullmatch('[a-zA-Z0-9-]{1,64}',values['profile']):raise ValueError('Invalid Orca profile')
        prefs['profile']=values['profile']
    for key in ('enabled','autostart'):
        if key in values:
            if not isinstance(values[key],bool):raise ValueError('Expected accessibility switch')
            prefs[key]=values[key]
    for key,value in values.items():
        if key not in FIELDS:continue
        schema,suffix,name,kind,low,high=FIELDS[key]
        if kind=='b' and not isinstance(value,bool):raise ValueError('Expected accessibility switch')
        if kind!='b' and (isinstance(value,bool) or not isinstance(value,(int,float)) or not low<=value<=high or kind=='i' and int(value)!=value):raise ValueError('Speech setting is out of range')
        obj=settings('org.gnome.Orca.'+schema,'/org/gnome/orca/'+prefs['profile']+'/'+suffix+'/')
        if not obj or name not in obj.props.settings_schema.list_keys():raise ValueError('This Orca version requires its native preferences dialog')
        obj.set_value(name,GLib.Variant(kind,int(value) if kind=='i' else value));obj.apply()
        if schema=='Voice':obj.set_boolean('established',True)
    Gio.Settings.sync()
    if prefs['enabled'] and not shutil.which('orca'):raise ValueError('Orca is not installed')
    if 'enabled' in values:
        interface=settings('org.gnome.desktop.interface','/org/gnome/desktop/interface/')
        apps=settings('org.gnome.desktop.a11y.applications','/org/gnome/desktop/a11y/applications/')
        if prefs['enabled'] and interface:interface.set_boolean('toolkit-accessibility',True)
        if apps:apps.set_boolean('screen-reader-enabled',prefs['enabled'])
        Gio.Settings.sync()
        run(['systemctl','--user','start' if prefs['enabled'] else 'stop',UNIT])
    run(['systemctl','--user','enable' if prefs['autostart'] else 'disable',UNIT])
    atomic_json(PATH,prefs)
    return snapshot()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['status','configure','preferences','startup']);args=parser.parse_args()
    try:
        if args.operation=='startup':
            value=configure({'enabled':True}) if read_json(PATH).get('autostart',False) else {'ok':True}
        elif args.operation=='configure':value=configure(json.load(sys.stdin))
        elif args.operation=='preferences':
            subprocess.Popen(['orca','--setup'],env=application_environment(),start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);value={'ok':True}
        else:value=snapshot()
        output(value);return 0
    except Exception as e:output({'error':str(e)});return 1
if __name__=='__main__':sys.exit(main())
