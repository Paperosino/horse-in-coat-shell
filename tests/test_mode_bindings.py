import shutil
import subprocess
import unittest
from pathlib import Path

@unittest.skipUnless(shutil.which("lua"), "Lua is required")
class ModeBindingTests(unittest.TestCase):
    def test_callbacks_and_help_descriptions_follow_the_active_mode(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(["lua", str(root / "tests/fixtures/mode-bindings.lua"),
            str(root / "shell/assets/hyprland/layouts.lua")], check=True)
