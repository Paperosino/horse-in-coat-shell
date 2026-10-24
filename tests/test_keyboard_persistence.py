"""Repeated keyboard writes must replace atomically and reject empty payloads."""
import os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class KeyboardPersistence(unittest.TestCase):
 def test_repeated_writes_and_failed_input_preserve_last_complete_file(self):
  with tempfile.TemporaryDirectory() as directory:
   env=dict(os.environ,XDG_CONFIG_HOME=directory,PYTHONDONTWRITEBYTECODE='1')
   target=Path(directory)/'hics/keyboard.lua'
   for value in ['us','us,ru','de,us']:
    payload='-- User custom code is preserved\nhl.config({input={kb_layout="'+value+'"}})\n'
    run=subprocess.run(['python3',str(ROOT/'shell/assets/write_keyboard_config.py')],input=payload,capture_output=True,text=True,env=env)
    self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(target.read_text(),payload)
    self.assertEqual(target.stat().st_mode&0o777,0o600)
   before=target.read_bytes()
   for payload in ('','\0invalid'):
    run=subprocess.run(['python3',str(ROOT/'shell/assets/write_keyboard_config.py')],input=payload,capture_output=True,text=True,env=env)
    self.assertNotEqual(run.returncode,0);self.assertEqual(target.read_bytes(),before)
if __name__=='__main__':unittest.main()
