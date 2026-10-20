import importlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shell/assets'))
import default_apps_helper as apps
class DefaultApplications(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.root/'config'),'XDG_CONFIG_DIRS':str(self.root/'etc'),'XDG_DATA_HOME':str(self.root/'data'),'XDG_DATA_DIRS':str(self.root/'system'),'XDG_CURRENT_DESKTOP':'Hyprland'});self.env.start()
  self.dir=self.root/'data/applications';self.dir.mkdir(parents=True)
  (self.dir/'viewer.desktop').write_text('[Desktop Entry]\nType=Application\nName=Viewer\nExec=viewer %U\nMimeType=application/pdf;image/png;\n')
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def test_browser_protocols_and_unrelated_defaults_preserved(self):
  conf=self.root/'config';conf.mkdir();(conf/'mimeapps.list').write_text('[Default Applications]\napplication/pdf=viewer.desktop;\n[Added Associations]\napplication/pdf=viewer.desktop;\n')
  result=apps.set_default('browser','viewer')
  self.assertEqual(result['defaults']['browser'],'viewer.desktop')
  c=apps.read_ini(conf/'mimeapps.list');self.assertEqual(c['Default Applications']['application/pdf'],'viewer.desktop;');self.assertIn('x-scheme-handler/http',c['Default Applications']);self.assertIn('Added Associations',c)
 def test_pdf_does_not_capture_ebooks_and_candidates_use_mime_types(self):
  data=apps.set_default('pdfViewer','viewer.desktop');self.assertEqual(data['defaults']['ebookReader'],'');self.assertIn('viewer',data['candidates']['pdfViewer']);self.assertNotIn('viewer',data['candidates']['browser'])
 def test_desktop_specific_override_updated(self):
  conf=self.root/'config';conf.mkdir();(conf/'hyprland-mimeapps.list').write_text('[Default Applications]\napplication/pdf=old.desktop;\n')
  apps.set_default('pdfViewer','viewer');self.assertEqual(apps.read_ini(conf/'hyprland-mimeapps.list')['Default Applications']['application/pdf'],'viewer.desktop;')
 def test_invalid_selection_cannot_change_associations(self):
  for category,app in [('unknown','viewer'),('browser','missing'),('browser','../viewer')]:
   with self.assertRaises(ValueError):apps.set_default(category,app)
  self.assertFalse((self.root/'config/mimeapps.list').exists())
if __name__=='__main__':unittest.main()
