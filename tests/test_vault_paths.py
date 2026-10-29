"""vault_paths 单元测试，重点覆盖路径越界回归（v1.0.x 的前缀绕过）。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vault_paths import (
    PathRejected,
    clip_text,
    count_notes,
    ensure_md,
    is_protected_dav_write,
    is_within,
    iter_note_files,
    relative_display,
    resolve_dir_path,
    resolve_note_path,
    resolve_root,
    search_notes,
)


class VaultPathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.root = self.base / "vault"
        self.root.mkdir()
        self.sibling = self.base / "vault_private"
        self.sibling.mkdir()
        (self.sibling / "secret.md").write_text("API_KEY=sk-test", encoding="utf-8")

    def test_normal_note_roundtrip(self):
        (self.root / "notes").mkdir()
        (self.root / "notes" / "a.md").write_text("hello", encoding="utf-8")
        target = resolve_note_path(self.root, "notes/a")
        self.assertEqual(target, self.root / "notes" / "a.md")
        self.assertEqual(relative_display(self.root, target), "notes/a.md")

    def test_prefix_sibling_is_not_within(self):
        self.assertFalse(is_within(self.root, self.sibling / "secret.md"))

    def test_prefix_sibling_escape_rejected(self):
        with self.assertRaises(PathRejected):
            resolve_note_path(self.root, "../vault_private/secret.md")

    def test_parent_traversal_rejected(self):
        with self.assertRaises(PathRejected):
            resolve_note_path(self.root, "a/../../escape.md")

    def test_windows_drive_path_rejected(self):
        with self.assertRaises(PathRejected):
            resolve_note_path(self.root, "C:/Windows/win.ini")

    def test_backslash_normalized(self):
        target = resolve_note_path(self.root, "notes\\sub\\b")
        self.assertEqual(target, self.root / "notes" / "sub" / "b.md")

    def test_hidden_directory_rejected(self):
        with self.assertRaises(PathRejected):
            resolve_note_path(self.root, ".obsidian/app")

    def test_empty_path_rejected(self):
        with self.assertRaises(PathRejected):
            ensure_md("   ")

    def test_ensure_md(self):
        self.assertEqual(ensure_md("a"), "a.md")
        self.assertEqual(ensure_md("a.MD"), "a.MD")
        with self.assertRaises(PathRejected):
            ensure_md("folder/")

    def test_root_nested_detection(self):
        nested = self.root / "obsidian_vault"
        nested.mkdir()
        self.assertEqual(resolve_root(self.root), nested.resolve())

    def test_root_explicit_subdir(self):
        sub = self.root / "notes"
        sub.mkdir()
        self.assertEqual(resolve_root(self.root, "notes"), sub.resolve())

    def test_root_subdir_escape_rejected(self):
        with self.assertRaises(PathRejected):
            resolve_root(self.root, "../outside")

    def test_dir_path_root(self):
        self.assertEqual(resolve_dir_path(self.root, ""), self.root)

    def test_dir_path_escape_rejected(self):
        with self.assertRaises(PathRejected):
            resolve_dir_path(self.root, "..")

    def test_iter_skips_hidden_and_non_md(self):
        (self.root / ".obsidian").mkdir()
        (self.root / ".obsidian" / "x.md").write_text("hidden", encoding="utf-8")
        (self.root / "keep.md").write_text("keep", encoding="utf-8")
        (self.root / "skip.txt").write_text("skip", encoding="utf-8")
        names = [path.name for path in iter_note_files(self.root)]
        self.assertEqual(names, ["keep.md"])

    def test_count_notes(self):
        for name in ("a.md", "b.md", "c.txt"):
            (self.root / name).write_text("x", encoding="utf-8")
        self.assertEqual(count_notes(self.root), 2)

    def test_symlink_escape_rejected(self):
        outside = self.base / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        link = self.root / "link.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("当前环境不允许创建符号链接")
        with self.assertRaises(PathRejected):
            resolve_note_path(self.root, "link.md")

    def test_search_empty_keyword(self):
        self.assertEqual(search_notes(self.root, "  "), [])

    def test_search_finds_and_limits(self):
        for index in range(3):
            (self.root / f"n{index}.md").write_text(f"keyword line {index}", encoding="utf-8")
        self.assertEqual(len(search_notes(self.root, "keyword", limit=2)), 2)

    def test_search_clips_snippet(self):
        (self.root / "long.md").write_text("x" * 100 + "keyword", encoding="utf-8")
        results = search_notes(self.root, "keyword", snippet_chars=10)
        self.assertEqual(len(results), 1)
        self.assertLessEqual(len(results[0]["snippets"][0]), 10)

    def test_search_skips_large_file(self):
        (self.root / "big.md").write_text("keyword" * 100, encoding="utf-8")
        self.assertEqual(search_notes(self.root, "keyword", max_file_bytes=10), [])

    def test_search_file_name_match(self):
        (self.root / "keyword-plan.md").write_text("nothing", encoding="utf-8")
        results = search_notes(self.root, "keyword")
        self.assertEqual(results[0]["snippets"], ["（文件名匹配）"])

    def test_clip_text(self):
        self.assertEqual(clip_text("abcdef", 4), "abc…")
        self.assertEqual(clip_text("abc", 0), "")

    def test_protected_dav_writes(self):
        self.assertTrue(is_protected_dav_write("/.obsidian/plugins/x/main.js"))
        self.assertTrue(is_protected_dav_write("/.obsidian/plugins"))
        self.assertTrue(is_protected_dav_write("/.obsidian/community-plugins.json"))
        self.assertTrue(is_protected_dav_write("/notes/.git/hooks/pre-commit"))
        self.assertTrue(is_protected_dav_write(".obsidian\\plugins\\x.js"))
        self.assertFalse(is_protected_dav_write("/.obsidian/app.json"))
        self.assertFalse(is_protected_dav_write("/notes/plugins/x.js"))


if __name__ == "__main__":
    unittest.main()
