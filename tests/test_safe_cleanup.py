"""Real native cleanup never follows symlinks and respects retention."""
import os,shlex,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SafeCleanup(unittest.TestCase):
 def test_symlinks_retention_and_bounded_scan(self):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);tree=base/'thumbs';tree.mkdir();outside=base/'outside';outside.mkdir();(outside/'keep').write_text('secret')
   (tree/'old').write_text('old');os.utime(tree/'old',(1,1));(tree/'recent').write_text('recent');(tree/'link').symlink_to(outside,target_is_directory=True);(tree/'file-link').symlink_to(outside/'keep');(base/'redirect').symlink_to(tree,target_is_directory=True)
   src=base/'probe.cpp';src.write_text('''#include "safecleanup.hpp"
#include <cassert>
int main(int argc,char**argv){auto root=QString::fromLocal8Bit(argv[1]);auto result=hics::cleanup::scan(root,true,QDateTime::currentSecsSinceEpoch()-86400);assert(result.bytes==9);assert(result.failed==0);assert(hics::cleanup::directory(root+"/link")==-1);assert(hics::cleanup::directory(root+"/../redirect")==-1);}
''')
   flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
   subprocess.run(['c++','-std=c++20','-fPIC',str(src),'-I'+str(ROOT/'shell/plugin/src/Hyprstack/Services'),*flags,'-o',str(base/'probe')],check=True)
   subprocess.run([str(base/'probe'),str(tree)],check=True)
   self.assertFalse((tree/'old').exists());self.assertTrue((tree/'recent').exists());self.assertEqual((outside/'keep').read_text(),'secret');self.assertTrue((tree/'file-link').is_symlink())
