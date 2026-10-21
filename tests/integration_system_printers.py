"""Privileged printer integration against an already running virtual IPP printer.
Run explicitly: sudo python tests/integration_system_printers.py ipp://localhost:8632/ipp/print
Creates only its own temporary queue and restores the previous default printer.
"""
import json,subprocess,time,re,os,sys
if os.geteuid()!=0:raise SystemExit('Run this integration test as root against a virtual IPP printer')
if len(sys.argv)!=2:raise SystemExit('Supply the virtual printer IPP URL')
name='hyprstack_native_test_'+str(os.getpid())
def status():return json.loads(subprocess.check_output(['hics-systemctl','status','printers'],text=True))
def apply(op,options):
 r=subprocess.run(['hics-systemctl','apply','printers',op],input=json.dumps(options),text=True,capture_output=True,timeout=35)
 result=json.loads(r.stdout);assert r.returncode==0,result;return result
before=status();original_default=next((p['name'] for p in before['printers'] if p['isDefault']),None);assert not any(p['name']==name for p in before['printers'])
try:
 state=apply('add',{'name':name,'uri':sys.argv[1],'description':'Hyprstack virtual printer test'})
 assert any(p['name']==name for p in state['printers']),state;print('PASS: add driverless IPP queue',flush=True)
 state=apply('pause',{'name':name});assert next(p for p in state['printers'] if p['name']==name)['state']==5,state;print('PASS: pause printer',flush=True)
 state=apply('resume',{'name':name});assert next(p for p in state['printers'] if p['name']==name)['state']==3,state;print('PASS: resume printer',flush=True)
 state=apply('default',{'name':name});assert next(p for p in state['printers'] if p['name']==name)['isDefault'],state;print('PASS: system default printer',flush=True)
 job_output=subprocess.check_output(['lp','-d',name,'-H','hold','/usr/share/cups/data/testprint'],text=True)
 job=int(re.search(re.escape(name)+r'-(\d+)',job_output)[1])
 rejected=subprocess.run(['runuser','-u','nobody','--','hics-systemctl','apply','printers','cancel-job'],input=json.dumps({'id':job}),text=True,capture_output=True,timeout=8)
 assert json.loads(rejected.stdout)['code']=='denied',rejected.stdout
 state=apply('cancel-job',{'id':job});assert not any(j['id']==job for j in state['jobs']),state
 print('PASS: own job cancellation and rejection of another user',flush=True)
finally:
 if any(p['name']==name for p in status()['printers']):apply('remove',{'name':name})
 if original_default:apply('default',{'name':original_default})
 assert {p['name'] for p in status()['printers']}=={p['name'] for p in before['printers']}
 print('PASS: test queue removed; original printer list restored',flush=True)
# A non-session user must not modify system settings via the root broker.
r=subprocess.run(['runuser','-u','nobody','--','hics-systemctl','apply','datetime','timezone'],input=json.dumps({'timezone':'UTC'}),text=True,capture_output=True,timeout=8)
reply=json.loads(r.stdout);assert r.returncode!=0 and reply['code']=='denied',reply
print('PASS: inactive unprivileged user cannot change system settings',flush=True)
