#!/usr/bin/env python3
"""Local-first assistant transport. Secrets arrive on stdin, never argv.

Ollama /api/chat is the default. A configurable chat-completions endpoint allows
local servers that expose that protocol. No commands or desktop data are sent
unless the user types them into the conversation.
"""
from __future__ import annotations
import argparse,json,os,sys,platform,urllib.request,urllib.error,urllib.parse
from feature_common import CONFIG,STATE,atomic_json,read_json,output,run
CONF=CONFIG/'assistant.json';HISTORY=STATE/'assistant/history.json'
DEFAULT={'provider':'ollama','endpoint':'http://127.0.0.1:11434','model':'','temperature':0.7,'maxTokens':2048,'systemPrompt':'Ты — помощник в Linux-оболочке Hyprstack. Отвечай на языке пользователя, кратко и точно. Ты не выполняешь команды самостоятельно.','rememberHistory':True,'includeSystemContext':False}

def config():
    d={**DEFAULT,**read_json(CONF)};d['hasKey']=bool(os.environ.get('HYPRSTACK_ASSISTANT_KEY') or read_json(CONFIG/'assistant-key.json').get('key'));return d

def save(value):
    d={**config(),**value};d.pop('hasKey',None);d.pop('apiKey',None)
    if d['provider'] not in ('ollama','compatible'):raise ValueError('Unknown provider')
    u=urllib.parse.urlparse(d['endpoint'])
    if u.scheme not in ('http','https') or not u.netloc or u.username or u.password:raise ValueError('Enter an HTTP(S) server URL without embedded credentials')
    d['endpoint']=d['endpoint'].rstrip('/');d['temperature']=max(0,min(2,float(d['temperature'])));d['maxTokens']=max(128,min(65536,int(d['maxTokens'])))
    if 'apiKey' in value and value['apiKey']:atomic_json(CONFIG/'assistant-key.json',{'key':str(value['apiKey'])},private=True)
    atomic_json(CONF,d,private=True);return config()

def request(path,payload=None):
    c=config();key=os.environ.get('HYPRSTACK_ASSISTANT_KEY') or read_json(CONFIG/'assistant-key.json').get('key','')
    headers={'Accept':'application/json','Content-Type':'application/json'}
    if key:headers['Authorization']='Bearer '+key
    req=urllib.request.Request(c['endpoint']+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
    return urllib.request.urlopen(req,timeout=120 if payload is not None else 8)

def models():
    c=config()
    with request('/api/tags' if c['provider']=='ollama' else '/models') as r: d=json.load(r)
    return {'models':[x['name'] for x in d.get('models',[])] if c['provider']=='ollama' else [x['id'] for x in d.get('data',[])]}

def history():return {'messages':read_json(HISTORY,[]) if config()['rememberHistory'] else []}

def chat(value):
    c=config();messages=value.get('messages',[])
    if not c['model']:raise ValueError('Choose or enter a model in assistant settings')
    if not isinstance(messages,list) or not messages:raise ValueError('Enter a message')
    messages=[{'role':m['role'],'content':str(m.get('content',''))[:100000]} for m in messages[-80:] if m.get('role') in ('user','assistant')]
    system=c['systemPrompt']
    if c.get('includeSystemContext'):
        context={'shell':'horse-in-coat-shell','system':platform.freedesktop_os_release().get('PRETTY_NAME',platform.system()),'settings':read_json(CONFIG/'system-controls.json')}
        try:
            monitors=json.loads(run(['hyprctl','-j','monitors'],timeout=3))
            context['monitors']=[{k:m.get(k) for k in ['name','width','height','scale','refreshRate']} for m in monitors]
        except Exception:context['monitors']=[]
        system+='\nDesktop context: '+json.dumps(context,ensure_ascii=False)
    wire=[{'role':'system','content':system},*messages]
    if c['provider']=='ollama':path='/api/chat';body={'model':c['model'],'messages':wire,'stream':True,'options':{'temperature':c['temperature'],'num_predict':c['maxTokens']}}
    else:path='/chat/completions';body={'model':c['model'],'messages':wire,'stream':True,'temperature':c['temperature'],'max_tokens':c['maxTokens']}
    answer=''
    with request(path,body) as response:
        for line in response:
            line=line.decode('utf-8').strip()
            if not line:continue
            if c['provider']=='compatible':
                if not line.startswith('data:'):continue
                line=line[5:].strip()
                if line=='[DONE]':break
            data=json.loads(line)
            if data.get('error'):raise ValueError(str(data['error']))
            delta=data.get('message',{}).get('content','') if c['provider']=='ollama' else (data.get('choices') or [{}])[0].get('delta',{}).get('content','')
            if delta:answer+=delta;output({'delta':delta})
            if data.get('done'):break
    if c['rememberHistory']:atomic_json(HISTORY,[*messages,{'role':'assistant','content':answer}],private=True)
    output({'done':True})

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['config','save','models','history','clear','forget-key','chat']);a=p.parse_args()
    try:
        if a.command=='chat':chat(json.load(sys.stdin));return 0
        if a.command=='config':d=config()
        elif a.command=='save':d=save(json.load(sys.stdin))
        elif a.command=='models':d=models()
        elif a.command=='history':d=history()
        elif a.command=='clear':atomic_json(HISTORY,[],private=True);d={'messages':[]}
        elif a.command=='forget-key':(CONFIG/'assistant-key.json').unlink(missing_ok=True);d=config()
        output(d);return 0
    except Exception as e:
        message='Assistant server is unavailable' if isinstance(e,(ConnectionError,urllib.error.URLError)) else str(e)
        if isinstance(e,urllib.error.HTTPError):message=f'Assistant server returned HTTP {e.code}'
        output({'error':message});return 1
if __name__=='__main__':raise SystemExit(main())
