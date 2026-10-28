"""Session inhibitors retain ownership and never leak stale blocks."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('logout_inhibitors',ROOT/'shell/assets/logout_inhibitors.py')
module=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=module
spec.loader.exec_module(module)

class Inhibitors(unittest.TestCase):
    def setUp(self):
        self.registry=module.InhibitorRegistry(limit=2)
        self.first='/org/freedesktop/portal/desktop/request/1_1/first'
        self.second='/org/freedesktop/portal/desktop/request/1_2/second'

    def test_unrelated_peer_cannot_release_an_inhibitor(self):
        self.registry.add(self.first,':1.1','editor','Unsaved document',module.LOGOUT)
        before=self.registry.generation
        self.assertFalse(self.registry.close(self.first,':1.2'))
        self.assertEqual(self.registry.generation,before)
        self.assertEqual(self.registry.matching(module.LOGOUT)[0].reason,'Unsaved document')
        self.assertTrue(self.registry.close(self.first,':1.1'))
        self.assertEqual(self.registry.matching(module.LOGOUT),())

    def test_owner_disconnect_clears_only_its_requests(self):
        self.registry.add(self.first,':1.1','editor','saving',module.LOGOUT|module.IDLE)
        self.registry.add(self.second,':1.2','backup','busy',module.LOGOUT)
        self.assertEqual(self.registry.owner_lost(':1.1'),1)
        self.assertEqual([i.app_id for i in self.registry.matching(module.LOGOUT)],['backup'])
        self.assertEqual(self.registry.matching(module.IDLE),())

    def test_limits_and_reuse_do_not_replace_live_inhibitors(self):
        self.registry.add(self.first,':1.1','one','',module.LOGOUT)
        with self.assertRaises(ValueError):self.registry.add(self.first,':1.2','two','',module.LOGOUT)
        self.registry.add(self.second,':1.2','two','',module.SUSPEND)
        with self.assertRaises(OverflowError):self.registry.add(self.second+'x',':1.3','three','',module.LOGOUT)
        self.assertTrue(self.registry.close(self.first,':1.1'))
        self.registry.add(self.first,':1.3','three','',module.IDLE)
        self.assertFalse(self.registry.close(self.first,':1.1'))
        self.assertEqual(self.registry.matching(module.IDLE)[0].owner,':1.3')

    def test_invalid_flags_and_unowned_clients_are_rejected(self):
        for flags in (0,16,True,-1):
            with self.subTest(flags=flags),self.assertRaises(ValueError):
                self.registry.add(self.first,':1.1','editor','',flags)
        with self.assertRaises(ValueError):self.registry.add(self.first,'org.example.Editor','editor','',module.LOGOUT)
        self.assertEqual(self.registry.matching(module.LOGOUT),())

if __name__=='__main__':unittest.main()
