"""Physical input model must be bounded and settle without oscillation or NaNs."""
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class DragInertiaTest(unittest.TestCase):
 def test_velocity_and_settling(self):
  with tempfile.TemporaryDirectory() as d:
   source = Path(d)/'test.cpp'; binary = Path(d)/'test'
   source.write_text(r'''#include "native/motion/drag-inertia.hpp"
#include <cassert>
#include <cmath>
int main() {
 hics::motion::DragInertia p; p.reset(0,0,0);
 for (int i=1;i<=60;i++) p.move(i*10,0,i/60.0);
 assert(p.tiltY()>0.01 && p.tiltY()<=.07 && std::abs(p.tiltX())<1e-9);
 double peak=p.tiltY();
 for(int i=0;i<240;i++) { p.settle(1.0/120); assert(std::isfinite(p.tiltY()) && p.tiltY()<=peak+.00001); }
 assert(p.settled());
 p.move(1e7,1e7,1.0+1.0/60); assert(std::abs(p.tiltY())<=.07);
 p.move(0,0,10); assert(p.settled());
}''')
   subprocess.run(['c++','-std=c++23','-I',str(ROOT),str(source),'-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True)
if __name__=='__main__':unittest.main()
