"""Preflight preserves recovery ordering without serial subprocess waits."""
import importlib.util,itertools,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('startup_runner',ROOT/'shell/assets/session_runner.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class StartupTests(unittest.TestCase):
 def test_preparation_starts_all_jobs_before_waiting_and_theme_stays_before_shell(self):
  events=[]
  class Child:
   pid=123
   def __init__(self,argv,**kwargs):self.label=Path(argv[1]).name;events.append(('start',self.label))
   def wait(self,**kwargs):events.append(('wait',self.label));return 0
   def poll(self):return 0
  appearance=types.SimpleNamespace(STATE=types.SimpleNamespace(is_file=lambda:True),session_environment=lambda:{})
  theme=types.SimpleNamespace(restore=lambda:events.append(('theme',None)))
  with patch.dict(sys.modules,appearance_themes=appearance,gtk_theme=theme),patch.object(runner.subprocess,'Popen',Child),patch.object(runner,'wait_preflight',side_effect=lambda child,timeout:child.wait(timeout=timeout)),patch.object(runner.os,'killpg'):runner.prepare_session()
  starts=[i for i,e in enumerate(events) if e[0]=='start'];waits=[i for i,e in enumerate(events) if e[0]=='wait']
  self.assertEqual(len(starts),4);self.assertLess(max(starts),min(waits));self.assertLess(events.index(('theme',None)),min(waits))
 def test_timeout_kills_and_reaps_unfinished_helper(self):
  class Child:
   pid=321
   def __init__(self,*args,**kwargs):self.stopped=False
   def poll(self):return 0 if self.stopped else None
   def wait(self,**kwargs):
    if kwargs:raise runner.subprocess.TimeoutExpired('fixture',.01)
    self.stopped=True;return -9
  appearance=types.SimpleNamespace(STATE=types.SimpleNamespace(is_file=lambda:False),session_environment=lambda:{})
  theme=types.SimpleNamespace(restore=lambda:None)
  with patch.dict(sys.modules,appearance_themes=appearance,gtk_theme=theme),patch.object(runner.subprocess,'Popen',Child),patch.object(runner,'wait_preflight',side_effect=lambda child,timeout:child.wait(timeout=timeout)),patch.object(runner.os,'killpg') as kill,patch.object(runner.time,'monotonic',side_effect=itertools.count(step=10).__next__):
   runner.prepare_session();self.assertEqual(kill.call_count,3)
 def test_stop_during_preparation_cancels_and_reaps_all_started_jobs(self):
  stopping=False;children=[]
  class Child:
   pid=321
   def __init__(self,*args,**kwargs):self.reaped=False;children.append(self)
   def poll(self):return None
   def wait(self,**kwargs):
    nonlocal stopping
    if kwargs:
     self.timeout=kwargs['timeout'];stopping=True
     raise runner.subprocess.TimeoutExpired('fixture',self.timeout)
    self.reaped=True;return -9
  appearance=types.SimpleNamespace(STATE=types.SimpleNamespace(is_file=lambda:False),session_environment=lambda:{})
  theme=types.SimpleNamespace(restore=lambda:None)
  with patch.dict(sys.modules,appearance_themes=appearance,gtk_theme=theme),patch.object(runner.subprocess,'Popen',Child),patch.object(runner,'wait_preflight',side_effect=lambda child,timeout:child.wait(timeout=timeout)),patch.object(runner.os,'killpg') as kill:
   self.assertFalse(runner.prepare_session(lambda:stopping))
  self.assertEqual(len(children),3);self.assertEqual(kill.call_count,3)
  self.assertTrue(all(c.reaped for c in children));self.assertLessEqual(children[0].timeout,.25)
 def test_unchanged_theme_file_keeps_inode_and_mtime(self):
  spec=importlib.util.spec_from_file_location('startup_theme',ROOT/'shell/assets/gtk_theme.py');theme=importlib.util.module_from_spec(spec);spec.loader.exec_module(theme)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'palette';theme.atomic_text(path,'dark');before=path.stat();theme.atomic_text(path,'dark');after=path.stat()
   self.assertEqual((before.st_ino,before.st_mtime_ns),(after.st_ino,after.st_mtime_ns))
   theme.atomic_text(path,'light');self.assertEqual(path.read_text(),'light')
 def test_cancellation_reaps_real_preflight_children(self):
  import subprocess,time
  children=[];start=time.monotonic();deadline=start+.3
  popen=subprocess.Popen
  def spawn(argv,**kwargs):
   child=popen([sys.executable,'-c','import time;time.sleep(60)'],**kwargs)
   children.append(child);return child
  appearance=types.SimpleNamespace(STATE=types.SimpleNamespace(is_file=lambda:False),session_environment=lambda:{})
  theme=types.SimpleNamespace(restore=lambda:None)
  try:
   with patch.dict(sys.modules,appearance_themes=appearance,gtk_theme=theme),patch.object(runner.subprocess,'Popen',side_effect=spawn):
    self.assertFalse(runner.prepare_session(lambda:time.monotonic()>=deadline))
   self.assertEqual(len(children),3)
   self.assertTrue(all(c.poll() is not None for c in children))
   self.assertLess(time.monotonic()-start,3)
  finally:
   for child in children:
    if child.poll() is None:child.kill()
    child.wait()
 def test_finished_helper_cannot_leave_running_descendants(self):
  import json,os,signal,subprocess,time
  children=[];descendants=[];popen=subprocess.Popen
  with tempfile.TemporaryDirectory() as directory:
   def spawn(argv,**kwargs):
    marker=Path(directory)/str(len(children))
    script='import subprocess,pathlib,json; p=subprocess.Popen(["sleep","60"]); d=subprocess.Popen(["sleep","60"],start_new_session=True);pathlib.Path('+repr(str(marker))+').write_text(json.dumps({"managed":p.pid,"detached":d.pid}))'
    child=popen([sys.executable,'-c',script],**kwargs);children.append(child);return child
   appearance=types.SimpleNamespace(STATE=types.SimpleNamespace(is_file=lambda:False),session_environment=lambda:{})
   theme=types.SimpleNamespace(restore=lambda:None)
   try:
    with patch.dict(sys.modules,appearance_themes=appearance,gtk_theme=theme),patch.object(runner.subprocess,'Popen',side_effect=spawn):
     self.assertTrue(runner.prepare_session())
    records=[json.loads(p.read_text()) for p in Path(directory).iterdir()]
    descendants=[r['managed'] for r in records]
    self.assertEqual(len(descendants),3)
    def active(pid):
     try:return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
     except (FileNotFoundError,ProcessLookupError):return False
    deadline=time.monotonic()+2
    while any(active(p) for p in descendants) and time.monotonic()<deadline:time.sleep(.01)
    self.assertFalse(any(active(p) for p in descendants),'Completed preflight leaked a running grandchild')
    self.assertTrue(all(active(r['detached']) for r in records),'Independent service group was terminated')
   finally:
    for p in Path(directory).iterdir():
     for pid in json.loads(p.read_text()).values():
      try:os.kill(pid,signal.SIGKILL)
      except ProcessLookupError:pass
    for child in children:child.wait()
