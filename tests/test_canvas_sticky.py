import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

@unittest.skipUnless(shutil.which("c++"), "C++ compiler is required")
class StickyWindowsTests(unittest.TestCase):
    def test_gap_hysteresis_release_and_removed_neighbour(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "sticky-test"
            subprocess.run(["c++", "-std=c++23", "-I" + str(root / "third_party/phantomat"),
                str(root / "tests/fixtures/sticky-windows.cpp"), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
