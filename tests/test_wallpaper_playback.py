"""Exercise the C++ player with a real short video, including EOF and a lost sink."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT/'shell/plugin/src/Hyprstack/Services'
class WallpaperPlayback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='hics-video-test-')
        cls.base = Path(cls.temp.name)
        cls.movie = cls.base/'loop.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=10','-t','0.6','-c:v','mpeg4','-an',str(cls.movie)],check=True)
        cls.binary = cls.base/'playback'
        flags = shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Qml','Qt6Multimedia'],text=True))
        moc = Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
        subprocess.run([str(moc),str(SERVICES/'wallpaperplayer.hpp'),'-o',str(cls.base/'moc.cpp'),*shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6Qml','Qt6Multimedia'],text=True))],check=True)
        subprocess.run(['c++','-std=c++20','-fPIC',str(ROOT/'tests/fixtures/wallpaper-playback-probe.cpp'),str(SERVICES/'wallpaperplayer.cpp'),str(cls.base/'moc.cpp'),'-I',str(SERVICES),*flags,'-o',str(cls.binary)],check=True)
        cls.env = dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='',XDG_CONFIG_HOME=str(cls.base/'config'),XDG_CACHE_HOME=str(cls.base/'cache'))
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def probe(self, watchdog=False):
        try:
            result=subprocess.run(['dbus-run-session','--',str(self.binary),str(self.movie)]+(['watchdog'] if watchdog else []),env=self.env,capture_output=True,text=True,timeout=45,check=True)
        except subprocess.TimeoutExpired as error:
            raise AssertionError(f"Player timed out: stdout={error.stdout!r}, stderr={error.stderr!r}") from error
        return json.loads(result.stdout)
    def test_short_video_loops_pauses_resumes_and_restarts(self):
        data=self.probe()
        self.assertGreater(data['frames'],18,data)
        self.assertEqual(data['nativeFrames'], data['frames'], data)
        self.assertTrue(data['pausedStable'],data)
        self.assertEqual(data['recoveries'],0,data)
        self.assertEqual(data['error'],'',data)
    def test_lost_frames_trigger_decoder_recovery(self):
        data=self.probe(True)
        self.assertGreater(data['frames'],0,data)
        self.assertGreaterEqual(data['recoveries'],1,data)
        self.assertLessEqual(data['recoveries'],2,data)
if __name__=='__main__':unittest.main()
