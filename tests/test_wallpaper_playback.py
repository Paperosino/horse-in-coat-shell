"""Exercise the C++ player with a real short video, including EOF and a lost sink."""
import json
import os
from pathlib import Path
import shlex
import shutil
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
        sanitizers=['-fsanitize=address','-fno-omit-frame-pointer','-g'] if os.environ.get('HICS_TEST_ASAN')=='1' else []
        subprocess.run(['c++','-std=c++20','-fPIC',*sanitizers,str(ROOT/'tests/fixtures/wallpaper-playback-probe.cpp'),str(SERVICES/'wallpaperplayer.cpp'),str(cls.base/'moc.cpp'),'-I',str(SERVICES),*flags,'-o',str(cls.binary)],check=True)
        if os.environ.get('HICS_TEST_ARTIFACT_DIR'):
            target=Path(os.environ['HICS_TEST_ARTIFACT_DIR']);target.mkdir(parents=True,exist_ok=True)
            shutil.copy2(cls.binary,target/'wallpaper-probe');shutil.copy2(cls.movie,target/'wallpaper-loop.mp4')
        runtime=cls.base/'runtime';runtime.mkdir(mode=0o700)
        cls.env = dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='',QT_FORCE_STDERR_LOGGING='1',HOME=str(cls.base/'home'),XDG_RUNTIME_DIR=str(runtime),XDG_CONFIG_HOME=str(cls.base/'config'),XDG_STATE_HOME=str(cls.base/'state'),XDG_DATA_HOME=str(cls.base/'data'),XDG_CACHE_HOME=str(cls.base/'cache'),PIPEWIRE_REMOTE='hics-wallpaper-absent',PULSE_SERVER='unix:'+str(cls.base/'absent-pulse'))
        for name in ('QT_FFMPEG_DECODING_HW_DEVICE_TYPES','QT_FFMPEG_ENCODING_HW_DEVICE_TYPES','LSAN_OPTIONS'):cls.env.pop(name,None)
        if sanitizers:cls.env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1'
        cls.bus_config=cls.base/'bus.conf'
        cls.bus_config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(cls.base)+'</listen><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def probe(self, watchdog=False):
        bus=subprocess.Popen(['dbus-daemon','--nofork','--print-address=1','--config-file='+str(self.bus_config)],stdout=subprocess.PIPE,text=True)
        try:
            address=bus.stdout.readline().strip();assert address
            result=subprocess.run([str(self.binary),str(self.movie)]+(['watchdog'] if watchdog else []),env=dict(self.env,DBUS_SESSION_BUS_ADDRESS=address,DBUS_SYSTEM_BUS_ADDRESS=address),capture_output=True,text=True,timeout=45,check=True)
        except subprocess.TimeoutExpired as error:
            raise AssertionError(f"Player timed out: stdout={error.stdout!r}, stderr={error.stderr!r}") from error
        finally:bus.terminate();bus.wait(timeout=5);bus.stdout.close()
        return json.loads(result.stdout)
    def test_short_video_loops_pauses_resumes_and_restarts(self):
        data=self.probe()
        self.assertGreater(data['frames'],18,data)
        self.assertEqual(data['nativeFrames'], data['frames'], data)
        self.assertTrue(data['pausedStable'],data)
        self.assertEqual(data['recoveries'],0,data)
        self.assertEqual(data['error'],'',data)
        self.assertTrue(data['colorful'],data)
    def test_lost_frames_trigger_decoder_recovery(self):
        data=self.probe(True)
        self.assertGreater(data['frames'],0,data)
        self.assertGreaterEqual(data['recoveries'],1,data)
        self.assertLessEqual(data['recoveries'],2,data)
        self.assertTrue(data['colorful'],data)
        self.assertTrue(data['sinkDetached'],data)
if __name__=='__main__':unittest.main()
