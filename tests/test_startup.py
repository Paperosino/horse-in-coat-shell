"""Preflight preserves recovery ordering without serial subprocess waits."""
import importlib.util,sys,tempfile,types,unittest
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
  with patch.dict(sys.modules,appearance_themes=appearance,gtk_theme=theme),patch.object(runner.subprocess,'Popen',Child):runner.prepare_session()
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
  with patch.dict(sys.modules,appearance_themes=appearance,gtk_theme=theme),patch.object(runner.subprocess,'Popen',Child),patch.object(runner.os,'killpg') as kill:
   runner.prepare_session();self.assertEqual(kill.call_count,3)
 def test_unchanged_theme_file_keeps_inode_and_mtime(self):
  spec=importlib.util.spec_from_file_location('startup_theme',ROOT/'shell/assets/gtk_theme.py');theme=importlib.util.module_from_spec(spec);spec.loader.exec_module(theme)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'palette';theme.atomic_text(path,'dark');before=path.stat();theme.atomic_text(path,'dark');after=path.stat()
   self.assertEqual((before.st_ino,before.st_mtime_ns),(after.st_ino,after.st_mtime_ns))
   theme.atomic_text(path,'light');self.assertEqual(path.read_text(),'light')
