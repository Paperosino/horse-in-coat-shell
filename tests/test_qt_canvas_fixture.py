"""The Qt input fixture must actually paint the colours asserted by the harness."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 is not installed")
class QtCanvasFixtureTests(unittest.TestCase):
    def test_painted_halves_and_middle_button(self):
        fixture = Path(__file__).resolve().parent / "fixtures/canvas-qt-input-app.py"
        script = r'''
import runpy, sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
app = QApplication([])
def check():
    try:
        window = next(w for w in app.topLevelWidgets() if w.windowTitle() == "Canvas Qt input regression")
        image = window.grab().toImage()
        green = red = 0
        for y in range(0, image.height(), 8):
            for x in range(0, image.width(), 8):
                c = image.pixelColor(x, y)
                green += c.green() > 150 and c.red() < 80 and c.blue() < 80
                red += c.red() > 150 and c.green() < 80 and c.blue() < 80
        assert min(green, red) > image.width() * image.height() / 64 * .30, (green, red)
        source = next(w for w in app.allWidgets() if type(w).__name__ == "Source")
        QTest.mouseMove(source, source.rect().center())
        QTest.mouseClick(source, Qt.MiddleButton, pos=source.rect().center())
        print("PAINT_OK", flush=True)
        app.exit(0)
    except BaseException:
        import traceback
        traceback.print_exc()
        app.exit(1)
QTimer.singleShot(100, check)
runpy.run_path(sys.argv[1], run_name="__main__")
'''
        result = subprocess.run([sys.executable, "-c", script, str(fixture)],
            env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for marker in ("PAINT_OK", "MIDDLE_PRESSED", "MIDDLE_RELEASED"):
            self.assertIn(marker, result.stdout)
