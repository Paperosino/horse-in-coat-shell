import contextlib,io,json,math,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shell/assets'))
import layout_controls as layouts
class LayoutSettings(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.file=Path(self.temp.name)/'layouts.json';self.file.write_text(json.dumps({'mode':'stacking','existing':'keep'}));self.scope=patch.object(layouts,'FILE',self.file);self.scope.start()
 def tearDown(self):self.scope.stop();self.temp.cleanup()
 def test_preserve_mode_and_settings_when_editing_camera(self):
  value=layouts.validate({'canvasZoom':1.25,'canvasGrid':False});self.assertEqual(value['mode'],'stacking');self.assertEqual(value['existing'],'keep');self.assertFalse(value['canvasGrid']);self.assertEqual(json.loads(self.file.read_text())['mode'],'stacking')
 def test_invalid_ranges_types_and_camera_bounds(self):
  for value in [{'canvasZoom':float('nan')},{'canvasZoom':2.1},{'canvasSnapSize':1},{'overviewDragMs':True},{'canvasGap':1.5},{'canvasGrid':'false'},{'canvasMinZoom':.9,'canvasZoom':.5},{'mode':'canvas'},{'command':'rm'}]:
   with self.assertRaises(ValueError,msg=str(value)):layouts.validate(value)
 def test_focus_motion_profiles_are_validated(self):
  for profile in ('off','expressive','standard','heavy','jelly'):
   self.assertEqual(layouts.validate({'stackFocusMotion':profile})['stackFocusMotion'],profile)
  for invalid in ('unknown',True,None):
   with self.assertRaises(ValueError):layouts.validate({'stackFocusMotion':invalid})
 def test_unknown_mode_never_reaches_compositor(self):
  with patch.object(sys,'argv',['layout_controls.py','mode','canvas;exit']),patch.object(layouts,'run') as run,contextlib.redirect_stdout(io.StringIO()):self.assertEqual(layouts.main(),1);run.assert_not_called()
 def test_sticky_setting_is_typed_and_preserves_spacing(self):
  value=layouts.validate({'canvasSticky':True,'canvasGap':24})
  self.assertTrue(value['canvasSticky']);self.assertEqual(value['canvasGap'],24)
  with self.assertRaises(ValueError):layouts.validate({'canvasSticky':'yes'})
 def test_compositor_error_is_reported(self):
  with patch.object(layouts,'run',return_value='error: rejected'):
   with self.assertRaisesRegex(ValueError,'rejected'):layouts.execute('return true')
if __name__=='__main__':unittest.main()
