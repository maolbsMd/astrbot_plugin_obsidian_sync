"""插件初始化与写入流程测试（用轻量 astrbot 桩，不需要真实 AstrBot）。"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))


class _DummyLogger:
    def debug(self, *args, **kwargs) -> None: ...

    def info(self, *args, **kwargs) -> None: ...

    def warning(self, *args, **kwargs) -> None: ...

    def error(self, *args, **kwargs) -> None: ...


def _install_astrbot_stubs():
    pkg = types.ModuleType("astrbot")
    pkg.__path__ = []  # type: ignore[attr-defined]

    api = types.ModuleType("astrbot.api")
    api.logger = _DummyLogger()
    api.llm_tool = lambda name=None: lambda fn: fn

    class _PermissionType:
        ADMIN = "admin"

    class _Filter:
        PermissionType = _PermissionType

        @staticmethod
        def command(*args, **kwargs):
            return lambda fn: fn

        @staticmethod
        def permission_type(*args, **kwargs):
            return lambda fn: fn

        @staticmethod
        def llm_tool(*args, **kwargs):
            return lambda fn: fn

    event = types.ModuleType("astrbot.api.event")
    event.filter = _Filter()
    event.AstrMessageEvent = object

    class Star:
        def __init__(self, context=None) -> None:
            self.context = context

    class Context: ...

    class StarTools:
        data_root: Path | None = None

        @staticmethod
        def get_data_dir(name: str | None = None) -> str:
            base = StarTools.data_root or Path(tempfile.gettempdir())
            return str(Path(base) / (name or ""))

    def register(*args, **kwargs):
        return lambda cls: cls

    star = types.ModuleType("astrbot.api.star")
    star.Star = Star
    star.Context = Context
    star.StarTools = StarTools
    star.register = register

    pkg.api = api
    sys.modules["astrbot"] = pkg
    sys.modules["astrbot.api"] = api
    sys.modules["astrbot.api.event"] = event
    sys.modules["astrbot.api.star"] = star
    return StarTools


StarTools = _install_astrbot_stubs()

import main as plugin_module  # noqa: E402


class _Event:
    def __init__(self, sender: str = "u1", group: str = "", admin: bool = False):
        self._sender = sender
        self._group = group
        self._admin = admin

    def get_sender_id(self) -> str:
        return self._sender

    def get_group_id(self) -> str:
        return self._group

    def is_admin(self) -> bool:
        return self._admin


class PluginInitTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        StarTools.data_root = Path(self._tmp.name) / "data"
        self.config = {
            "host": "127.0.0.1",
            "auto_start": False,
            "password": "s" * 20,
            "build_index_on_start": False,
        }
        self.plugin = plugin_module.ObsidianSyncPlugin(object(), self.config)

    def test_default_paths_live_under_data_dir(self):
        data_dir = StarTools.data_root / "astrbot_plugin_obsidian_sync"
        self.assertEqual(self.plugin.data_dir, data_dir)
        self.assertEqual(self.plugin.root, (data_dir / "vault").resolve())
        self.assertTrue(self.plugin.root.is_dir())

    def test_weak_password_is_replaced(self):
        config = dict(self.config, password="change_me_to_your_password")
        plugin = plugin_module.ObsidianSyncPlugin(object(), config)
        self.assertNotEqual(plugin.password, "change_me_to_your_password")
        self.assertGreaterEqual(len(plugin.password), 12)
        self.assertEqual(config["password"], plugin.password)
        self.assertTrue(plugin._password_generated)

    def test_strong_password_is_kept(self):
        self.assertEqual(self.plugin.password, "s" * 20)
        self.assertFalse(self.plugin._password_generated)

    def test_username_generated_when_empty(self):
        self.assertTrue(self.plugin.username.startswith("vault_"))
        self.assertTrue(self.plugin._username_generated)

    def test_legacy_username_migrated(self):
        config = dict(self.config, username="neko")
        plugin = plugin_module.ObsidianSyncPlugin(object(), config)
        self.assertNotEqual(plugin.username.lower(), "neko")
        self.assertTrue(plugin.username.startswith("vault_"))
        self.assertTrue(plugin._username_generated)
        self.assertEqual(config["username"], plugin.username)

    def test_custom_username_kept(self):
        config = dict(self.config, username="my_custom_user")
        plugin = plugin_module.ObsidianSyncPlugin(object(), config)
        self.assertEqual(plugin.username, "my_custom_user")
        self.assertFalse(plugin._username_generated)

    def test_public_bind_requires_opt_in(self):
        config = dict(self.config, host="0.0.0.0", port="not-a-port")
        plugin = plugin_module.ObsidianSyncPlugin(object(), config)
        self.assertEqual(plugin.host, "127.0.0.1")
        self.assertTrue(plugin._public_bind_blocked)
        self.assertEqual(plugin.port, 6190)

    def test_public_bind_allowed_when_enabled(self):
        config = dict(self.config, host="0.0.0.0", allow_public_bind=True)
        plugin = plugin_module.ObsidianSyncPlugin(object(), config)
        self.assertEqual(plugin.host, "0.0.0.0")
        self.assertFalse(plugin._public_bind_blocked)

    def test_private_only_blocks_group(self):
        self.plugin.private_only = True
        self.assertFalse(self.plugin._tool_allowed(_Event(group="g1")))
        self.assertTrue(self.plugin._tool_allowed(_Event()))

    def test_allowed_users_and_admin(self):
        self.plugin.allowed_users = {"u1"}
        self.assertTrue(self.plugin._tool_allowed(_Event(sender="u1")))
        self.assertFalse(self.plugin._tool_allowed(_Event(sender="u2")))
        self.assertTrue(self.plugin._tool_allowed(_Event(sender="u2", admin=True)))

    def test_append_then_overwrite_creates_backup(self):
        target = self.plugin.root / "notes" / "a.md"
        self.plugin._write_note_sync(target, "first", "append")
        self.plugin._write_note_sync(target, "second", "append")
        text = target.read_text(encoding="utf-8")
        self.assertIn("first", text)
        self.assertIn("second", text)

        self.plugin._write_note_sync(target, "replaced", "overwrite")
        self.assertEqual(target.read_text(encoding="utf-8").strip(), "replaced")

        backups = list((self.plugin.data_dir / "history").rglob("*.md"))
        self.assertTrue(backups)

    def test_backup_keep_prunes(self):
        self.plugin.backup_keep = 2
        target = self.plugin.root / "daily.md"
        for index in range(4):
            target.write_text(f"v{index}", encoding="utf-8")
            self.plugin._snapshot(target)
        backups = list((self.plugin.data_dir / "history").rglob("*.md"))
        self.assertEqual(len(backups), 2)

    def test_read_note_respects_limit(self):
        target = self.plugin.root / "lines.md"
        target.write_text("\n".join(str(i) for i in range(10)), encoding="utf-8")
        note = self.plugin._read_note_sync(target, 3)
        assert note is not None
        self.assertEqual(note["shown"], 3)
        self.assertEqual(note["total"], 10)

    def test_list_notes_skips_hidden(self):
        (self.plugin.root / ".obsidian").mkdir()
        (self.plugin.root / ".obsidian" / "x.md").write_text("x", encoding="utf-8")
        (self.plugin.root / "keep.md").write_text("x", encoding="utf-8")
        self.assertEqual(self.plugin._list_notes_sync(""), ["keep.md"])

    def test_write_tool_rejects_unknown_mode(self):
        result = asyncio.run(
            self.plugin.write_obsidian_note(_Event(), "a.md", "hello", mode="appnd")
        )
        self.assertIn("mode", result)
        self.assertFalse((self.plugin.root / "a.md").exists())

    def test_write_tool_disabled(self):
        self.plugin.write_enabled = False
        result = asyncio.run(self.plugin.write_obsidian_note(_Event(), "a.md", "hello", "append"))
        self.assertIn("write_enabled", result)

    def test_search_tool_marks_content_untrusted(self):
        (self.plugin.root / "note.md").write_text("keyword content", encoding="utf-8")
        result = asyncio.run(self.plugin.search_obsidian_notes(_Event(), "keyword"))
        self.assertIn("<obsidian_notes", result)
        self.assertIn("keyword content", result)

    def test_search_tool_requires_keyword(self):
        result = asyncio.run(self.plugin.search_obsidian_notes(_Event(), "   "))
        self.assertIn("关键词不能为空", result)

    def test_history_and_undo(self):
        target = self.plugin.root / "notes" / "a.md"
        self.plugin._write_note_sync(target, "first", "append")
        self.plugin._write_note_sync(target, "second", "append")
        self.plugin._write_note_sync(target, "third", "overwrite")
        self.assertIn("third", target.read_text(encoding="utf-8"))

        self.assertTrue(self.plugin._history_lines(target))
        restored = self.plugin._restore_latest_sync(target)
        self.assertIsNotNone(restored)
        content = target.read_text(encoding="utf-8")
        self.assertIn("second", content)
        self.assertNotIn("third", content)

    def test_undo_without_history(self):
        target = self.plugin.root / "fresh.md"
        target.write_text("only", encoding="utf-8")
        self.assertIsNone(self.plugin._restore_latest_sync(target))

    def test_audit_records_tool_call(self):
        (self.plugin.root / "n.md").write_text("keyword body", encoding="utf-8")
        asyncio.run(self.plugin.search_obsidian_notes(_Event(), "keyword"))
        entries = self.plugin._read_audit_sync(10)
        self.assertTrue(any("search" in line for line in entries))

    def test_doctor_report(self):
        report = self.plugin._doctor_sync()
        self.assertIn("WebDAV", report)
        self.assertIn("索引", report)

    def test_status_mentions_index(self):
        self.assertIn("索引", self.plugin._status_text())

    def test_search_uses_index_after_write(self):
        asyncio.run(self.plugin.write_obsidian_note(_Event(), "indexed.md", "独特关键词", "append"))
        result = asyncio.run(self.plugin.search_obsidian_notes(_Event(), "独特关键词"))
        self.assertIn("indexed.md", result)

    def test_soft_delete_and_restore(self):
        target = self.plugin.root / "notes" / "d.md"
        target.parent.mkdir(exist_ok=True)
        target.write_text("bye", encoding="utf-8")

        batch = self.plugin._soft_delete_sync(target)
        self.assertFalse(target.exists())
        self.assertTrue((self.plugin.trash_dir / batch).is_dir())
        self.assertIn("d.md", "\n".join(self.plugin._trash_lines()))

        restored = self.plugin._restore_sync(batch)
        self.assertEqual(restored, target)
        self.assertEqual(target.read_text(encoding="utf-8"), "bye")

    def test_restore_refuses_existing(self):
        target = self.plugin.root / "d.md"
        target.write_text("v1", encoding="utf-8")
        batch = self.plugin._soft_delete_sync(target)
        target.write_text("v2", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            self.plugin._restore_sync(batch)
        self.assertEqual(target.read_text(encoding="utf-8"), "v2")

    def test_restore_unknown_or_bad_id(self):
        with self.assertRaises(ValueError):
            self.plugin._restore_sync("does-not-exist")
        with self.assertRaises(ValueError):
            self.plugin._restore_sync("../escape")

    def test_delete_disabled_by_default(self):
        result = asyncio.run(self.plugin.delete_obsidian_note(_Event(), "a.md"))
        self.assertIn("未启用", result)

    def test_delete_tool_soft_deletes(self):
        self.plugin.delete_enabled = True
        target = self.plugin.root / "gone.md"
        target.write_text("x", encoding="utf-8")

        result = asyncio.run(self.plugin.delete_obsidian_note(_Event(), "gone.md"))
        self.assertIn("回收站", result)
        self.assertFalse(target.exists())
        entries = self.plugin._read_audit_sync(40)
        self.assertTrue(any("delete" in line for line in entries))

    def test_delete_then_search_excludes(self):
        self.plugin.delete_enabled = True
        asyncio.run(self.plugin.write_obsidian_note(_Event(), "tmp.md", "唯一词abc", "append"))
        asyncio.run(self.plugin.delete_obsidian_note(_Event(), "tmp.md"))
        result = asyncio.run(self.plugin.search_obsidian_notes(_Event(), "唯一词abc"))
        self.assertNotIn("tmp.md", result)

    def test_trash_prune_by_count(self):
        self.plugin.trash_max_items = 1
        for name in ("a.md", "b.md"):
            path = self.plugin.root / name
            path.write_text("x", encoding="utf-8")
            self.plugin._soft_delete_sync(path)
        self.assertEqual(len(self.plugin._trash_batches()), 1)


if __name__ == "__main__":
    unittest.main()
