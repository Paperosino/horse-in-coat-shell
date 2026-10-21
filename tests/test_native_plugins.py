"""Reject incomplete, stale and ABI-incompatible plugin installation payloads."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "distribution"))
from native_plugins import PLUGINS, validate


class NativePayloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.payload, self.build = root / "payload", root / "build"
        for directory in (self.payload, self.build):
            directory.mkdir()
            (directory / "native-version.json").write_text(json.dumps({"abiHash": "current"}))
        for name, relative in PLUGINS.items():
            binary = b"\x7fELF" + name.encode().ljust(80, b"\0")
            compiled = self.build / relative
            compiled.parent.mkdir(parents=True, exist_ok=True)
            compiled.write_bytes(binary)
            (self.payload / name).write_bytes(binary)

    def test_complete_current_build(self):
        self.assertEqual(set(validate(self.payload, self.build, "current")), set(PLUGINS))

    def test_missing_canvas_is_rejected(self):
        (self.payload / "libspatialoverview.so").unlink()
        with self.assertRaises(FileNotFoundError):
            validate(self.payload, self.build)

    def test_stale_plugin_is_rejected_even_with_matching_abi(self):
        (self.payload / "hics-bars.so").write_bytes(b"\x7fELF" + b"old" * 30)
        with self.assertRaisesRegex(ValueError, "differs"):
            validate(self.payload, self.build)

    def test_incompatible_abi_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ABI"):
            validate(self.payload, self.build, "different")

    def test_truncated_or_non_elf_file_is_rejected(self):
        for content in (b"\x7fELF", b"not a library" * 10):
            with self.subTest(content=content):
                (self.payload / "hics-bars.so").write_bytes(content)
                with self.assertRaisesRegex(ValueError, "Invalid"):
                    validate(self.payload, self.build)
