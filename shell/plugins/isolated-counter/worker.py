"""The worker receives only JSON actions and can write only its private /data."""
import json,sys
from pathlib import Path
path=Path.home()/'counter.json'
try:count=int(json.loads(path.read_text())['count'])
except (OSError,ValueError,KeyError,TypeError):count=0

def publish():
    row={'type':'button','text':str(count),'icon':'add','id':'increment'}
    print(json.dumps({'slots':{'barWidget':[row],'desktopWidget':[{'type':'heading','text':'Counter'},row],'panel':[row]}}),flush=True)
for line in sys.stdin:
    message=json.loads(line)
    if message.get('type')=='action' and message.get('id')=='increment':
        count+=1;path.write_text(json.dumps({'count':count}))
    publish()
