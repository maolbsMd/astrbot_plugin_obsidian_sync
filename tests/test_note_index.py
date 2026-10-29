"""note_index 单元测试：增量同步、FTS/LIKE 搜索与统计。"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from note_index import index_stats, search_index, sync_index


class NoteIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "vault"
        self.root.mkdir()
        self.db = Path(self._tmp.name) / "index.sqlite3"
        (self.root / "a.md").write_text("# 机器学习\n梯度下降与反向传播\n", encoding="utf-8")
        (self.root / "b.md").write_text("python notes about webdav\n", encoding="utf-8")
        (self.root / ".obsidian").mkdir()
        (self.root / ".obsidian" / "x.md").write_text("hidden machine", encoding="utf-8")

    def test_sync_and_stats(self):
        stats = sync_index(self.db, self.root, 1024 * 1024)
        self.assertEqual(stats["indexed"], 2)
        self.assertEqual(stats["added"], 2)
        self.assertIn(stats["tokenizer"], {"trigram", "unicode61", "none"})
        info = index_stats(self.db)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info["notes"], 2)

    def test_search_english(self):
        sync_index(self.db, self.root)
        results = search_index(self.db, "webdav")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["path"], "b.md")

    def test_search_chinese(self):
        sync_index(self.db, self.root)
        results = search_index(self.db, "机器学习")
        self.assertTrue(results)
        self.assertEqual(results[0]["path"], "a.md")

    def test_short_chinese_uses_like(self):
        sync_index(self.db, self.root)
        results = search_index(self.db, "机器")
        self.assertTrue(results)
        self.assertEqual(results[0]["path"], "a.md")

    def test_incremental_update(self):
        sync_index(self.db, self.root)
        path = self.root / "b.md"
        path.write_text("now mentions 机器学习 too", encoding="utf-8")
        stamp = time.time() + 5
        os.utime(path, (stamp, stamp))
        stats = sync_index(self.db, self.root)
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["added"], 0)
        self.assertEqual(len(search_index(self.db, "机器学习")), 2)

    def test_deleted_file_removed(self):
        sync_index(self.db, self.root)
        (self.root / "b.md").unlink()
        stats = sync_index(self.db, self.root)
        self.assertEqual(stats["removed"], 1)
        self.assertEqual(search_index(self.db, "webdav"), [])

    def test_hidden_not_indexed(self):
        sync_index(self.db, self.root)
        self.assertEqual(search_index(self.db, "hidden"), [])

    def test_missing_db_returns_empty(self):
        self.assertEqual(search_index(self.db, "anything"), [])

    def test_empty_keyword(self):
        sync_index(self.db, self.root)
        self.assertEqual(search_index(self.db, "   "), [])

    def test_index_stats_none_for_missing(self):
        self.assertIsNone(index_stats(self.db))


if __name__ == "__main__":
    unittest.main()
