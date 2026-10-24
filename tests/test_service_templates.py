"""Generated service paths honor a non-system installation prefix."""
import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ServiceTemplates(unittest.TestCase):
 def test_all_shell_services_expand_custom_bin_directory(self):
  templates=[ROOT/'distribution/systemd/user'/f'{n}.service.in' for n in ('hic-session','hics-displays','hics-configuration')]
  templates += [ROOT/'distribution/systemd/system'/f'{n}.service.in' for n in ('hics-system','hics-memory')]
  templates += [ROOT/'distribution/dbus/org.hics.System1.service.in']
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory)
   for index,path in enumerate(templates):
    out=base/f'{index}.service';script=base/'configure.cmake';script.write_text(f'set(HICS_BIN_DIR "/opt/hics/custom-bin")\nconfigure_file("{path}" "{out}" @ONLY)\n')
    subprocess.run(['cmake','-P',str(script)],check=True,capture_output=True)
    value=out.read_text();self.assertIn('/opt/hics/custom-bin/hics-',value);self.assertNotIn('/usr/bin/hics-',value);self.assertNotIn('@HICS_BIN_DIR@',value)
