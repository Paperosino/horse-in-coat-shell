"""Settings must use ligature names supported by the bundled symbol font."""
import re
import unittest
from pathlib import Path
try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None
ROOT = Path(__file__).resolve().parents[1]

@unittest.skipIf(TTFont is None, 'fontTools is required to inspect bundled font ligatures')
class SettingsIcons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        font=TTFont(ROOT/'shell/assets/material-symbols/MaterialSymbolsRounded.ttf')
        ascii_names={v:chr(k) for k,v in font.getBestCmap().items() if 32<=k<127}
        cls.names=set()
        for lookup in font['GSUB'].table.LookupList.Lookup:
            for table in lookup.SubTable:
                if lookup.LookupType==7:table=table.ExtSubTable
                for first,entries in getattr(table,'ligatures',{}).items():
                    for entry in entries:
                        try:cls.names.add(''.join(ascii_names[g] for g in [first]+entry.Component))
                        except KeyError:pass

    def test_font_contains_expected_touchpad_symbol(self):
        self.assertGreater(len(self.names),1000)
        self.assertIn('touchpad_mouse',self.names)
        self.assertNotIn('touchpad',self.names)

    def test_settings_icon_expressions_use_supported_names(self):
        errors=[]
        for path in (ROOT/'shell/modules/nexus').rglob('*.qml'):
            for number,line in enumerate(path.read_text().splitlines(),1):
                match=re.search(r'\b(?:icon|pageIcon|iconName|placeholderIcon|trailingIcon|fallbackIcon)\s*:\s*(.*)',line)
                if not match:continue
                expression=re.split(r',\s*category\s*:',match[1].split(';')[0],maxsplit=1)[0]
                # Only literal results, not comparison strings or backend IDs.
                for name in re.findall(r'(?:^\s*|[?:]\s*|\|\|\s*)"([a-z][a-z0-9_]+)"',expression):
                    if name not in self.names:errors.append(f'{path.relative_to(ROOT)}:{number}: {name}')
        self.assertEqual(errors,[])

    def test_primary_sidebar_destinations_are_not_repeated_as_page_links(self):
        forbidden={'KeyboardPage.qml':r'openPage\("(?:mouse|touchpad|shortcuts)"\)',
                   'PanelsPage.qml':r'openSubPage\(11\)',
                   'LanguageAndRegion.qml':r'openPage\("datetime"\)',
                   'AppsPage.qml':r'openPage\("(?:default-apps|autostart|plugins|assistant)"\)'}
        for name,pattern in forbidden.items():
            with self.subTest(page=name):self.assertNotRegex((ROOT/'shell/modules/nexus/pages'/name).read_text(),pattern)

if __name__=='__main__':unittest.main()
