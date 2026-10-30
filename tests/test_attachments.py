"""attachments 单元测试：格式识别、文件名清洗、保存与嵌入语法。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from attachments import (
    AttachmentError,
    detect_image,
    embed_markup,
    sanitize_filename,
    save_attachment,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8
JPG = b"\xff\xd8\xff\xe0" + b"0" * 8
GIF = b"GIF89a" + b"0" * 8
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"0" * 8


class AttachmentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "vault"
        self.root.mkdir()

    def test_detect_image(self):
        self.assertEqual(detect_image(PNG), "png")
        self.assertEqual(detect_image(JPG), "jpg")
        self.assertEqual(detect_image(GIF), "gif")
        self.assertEqual(detect_image(WEBP), "webp")
        self.assertEqual(detect_image(b"hello"), "")

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("../evil.png"), "evil.png")
        self.assertEqual(sanitize_filename(""), "file")
        self.assertNotIn("/", sanitize_filename("a/b:c.png"))

    def test_save_attachment_unique(self):
        directory = self.root / "attachments"
        first = save_attachment(self.root, directory, PNG, "a.png", "png")
        second = save_attachment(self.root, directory, PNG, "a.png", "png")
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_file())
        self.assertEqual(first.read_bytes(), PNG)
        self.assertEqual(first.suffix, ".png")

    def test_save_attachment_rejects_outside_dir(self):
        outside = Path(self._tmp.name) / "outside"
        with self.assertRaises(AttachmentError):
            save_attachment(self.root, outside, PNG, "a.png", "png")

    def test_embed_markup(self):
        self.assertEqual(embed_markup("attachments/a.png", True), "![[attachments/a.png]]")
        self.assertEqual(embed_markup("attachments/a.pdf", False), "[[attachments/a.pdf]]")
        self.assertIn("说明", embed_markup("attachments/a.png", True, "说明"))


if __name__ == "__main__":
    unittest.main()
