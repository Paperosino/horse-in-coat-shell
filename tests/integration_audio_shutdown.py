#!/usr/bin/env python3
"""Stop a streaming collector while an isolated PipeWire server is frozen."""
import json,os,select,signal,subprocess,tempfile,time
from pathlib import Path
from test_audio_collector import build_probe
with tempfile.TemporaryDirectory(prefix='hics-pw-shutdown-') as directory:
 base=Path(directory);runtime=base/'runtime';runtime.mkdir(mode=0o700)
 binary=build_probe(base)
 config=base/'config/pipewire/pipewire.conf.d';config.mkdir(parents=True)
 (config/'test-source.conf').write_text('context.spa-libs = { audiotestsrc = audiotestsrc/libspa-audiotestsrc }\n')
 # Activate the synthetic capture without a session manager; production C++ is unchanged.
 for name in ('client.conf.d','client-rt.conf.d'):
  client=base/'config/pipewire'/name;client.mkdir(parents=True)
  (client/'test-stream.conf').write_text('stream.rules = [ { matches = [ { media.name = "hics-shell" } ] actions = { update-props = { node.passive = false } } } ]\n')
 env=dict(os.environ,HOME=str(base),XDG_RUNTIME_DIR=str(runtime),PIPEWIRE_RUNTIME_DIR=str(runtime),PIPEWIRE_REMOTE='pipewire-0',XDG_CONFIG_HOME=str(base/'config'),XDG_STATE_HOME=str(base/'state'),XDG_DATA_HOME=str(base/'data'))
 env.pop('PIPEWIRE_CONFIG_DIR',None);env.pop('PIPEWIRE_CONFIG_PREFIX',None)
 processes=[];server=None;collector=None;frozen=False
 def ctl(*args):return subprocess.check_output(args,env=env,text=True,stderr=subprocess.DEVNULL,timeout=3)
 def until(predicate,seconds=5):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   if predicate():return
   time.sleep(.04)
  raise AssertionError('Private PipeWire graph did not become ready')
 def line():
  if not select.select([collector.stdout],[],[],2)[0]:raise AssertionError('Audio collector did not stop promptly')
  return collector.stdout.readline().strip()
 try:
  log=(base/'pipewire.log').open('w');server=subprocess.Popen(['pipewire'],env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(server)
  until(lambda:(runtime/'pipewire-0').exists())
  ctl('pw-cli','create-node','adapter','{ factory.name = audiotestsrc node.name = hics-test-source media.class = Audio/Source audio.position = [ MONO ] node.driver = true node.always-process = true node.pause-on-idle = false object.linger = true }')
  collector=subprocess.Popen([str(binary)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(base/'collector.log').open('w'),text=True);processes.append(collector)
  assert line()=='started'
  nodes={}
  def find_nodes():
   for item in json.loads(ctl('pw-dump')):
    if item['type']!='PipeWire:Interface:Node':continue
    name=item.get('info',{}).get('props',{}).get('node.name')
    if name in ('hics-test-source','hics-shell'):nodes[name]=item['id']
   return len(nodes)==2
  until(find_nodes)
  # A private core has no WirePlumber. Negotiate the same DSP ports explicitly.
  for name,node in nodes.items():
   ctl('pw-cli','set-param',str(node),'PortConfig','{ direction = '+('Output' if name=='hics-test-source' else 'Input')+' mode = dsp monitor = false format = { mediaType = audio mediaSubtype = raw format = F32P rate = 48000 channels = 1 position = [ MONO ] } }')
  ports={}
  def find_ports():
   graph=json.loads(ctl('pw-dump'));names={item['id']:item.get('info',{}).get('props',{}).get('node.name','') for item in graph if item['type']=='PipeWire:Interface:Node'}
   for item in graph:
    if item['type']!='PipeWire:Interface:Port':continue
    props=item['info']['props'];name=names.get(props.get('node.id'),'')
    if name=='hics-test-source' and props.get('port.direction')=='out':ports['source']=str(item['id'])
    elif name!='hics-test-source' and props.get('port.direction')=='in':ports['target']=str(item['id'])
   return len(ports)==2
  until(find_ports)
  ctl('pw-cli','create-link',str(nodes['hics-test-source']),'0',str(nodes['hics-shell']),'0','{ link.passive = false object.linger = true }')
  def streaming():return any(item['type']=='PipeWire:Interface:Link' and item.get('info',{}).get('state')=='active' for item in json.loads(ctl('pw-dump')))
  until(streaming);time.sleep(.1)
  os.kill(server.pid,signal.SIGSTOP);frozen=True;time.sleep(.1)
  collector.stdin.write('stop\n');collector.stdin.flush();result=line();assert result.startswith('stopped '),result
  assert int(result.split()[1])<300,result
  os.kill(server.pid,signal.SIGCONT);frozen=False
  collector.stdin.write('quit\n');collector.stdin.flush();assert collector.wait(timeout=3)==0
  print('PASS: active PipeWire graph frozen; collector wakes and joins in '+result.split()[1]+' ms without receiving another audio buffer')
 except Exception:
  if server and server.poll() is None and not frozen:
   try:
    graph=json.loads(ctl('pw-dump'))
    print('Private graph:',json.dumps([{'id':x['id'],'type':x['type'],'state':x.get('info',{}).get('state'),'name':x.get('info',{}).get('props',{}).get('node.name')} for x in graph if x['type'] in ('PipeWire:Interface:Node','PipeWire:Interface:Link')]))
   except Exception:pass
  for path in base.glob('*.log'):print(path.name,path.read_text(errors='replace')[-3000:])
  raise
 finally:
  if frozen and server and server.poll() is None:os.kill(server.pid,signal.SIGCONT)
  for process in reversed(processes):
   if process.poll() is None:
    process.terminate()
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:process.kill();process.wait()
