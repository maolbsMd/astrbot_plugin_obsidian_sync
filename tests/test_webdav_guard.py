"""DavGuard 单元测试：只读模式、越界请求与敏感写入拦截。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from webdav_guard import DavGuard


class _Recorder:
    def __init__(self) -> None:
        self.called = False

    def __call__(self, environ, start_response):
        self.called = True
        start_response("200 OK", [])
        return [b"ok"]


def call_guard(guard, path: str, method: str = "GET", destination: str | None = None):
    status: dict[str, str] = {}

    def start_response(status_line, _headers):
        status["line"] = status_line

    environ = {"PATH_INFO": path, "REQUEST_METHOD": method}
    if destination is not None:
        environ["HTTP_DESTINATION"] = destination
    body = b"".join(guard(environ, start_response))
    return status["line"], body


class DavGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "vault"
        self.root.mkdir()
        self.app = _Recorder()
        self.guard = DavGuard(self.app, self.root)

    def test_normal_get_passes(self):
        status, _ = call_guard(self.guard, "/notes/a.md")
        self.assertTrue(status.startswith("200"))
        self.assertTrue(self.app.called)

    def test_traversal_get_blocked(self):
        status, _ = call_guard(self.guard, "/../outside.md")
        self.assertTrue(status.startswith("403"))
        self.assertFalse(self.app.called)

    def test_encoded_traversal_blocked(self):
        status, _ = call_guard(self.guard, "/%2e%2e/outside.md")
        self.assertTrue(status.startswith("403"))

    def test_plugin_upload_blocked(self):
        status, _ = call_guard(self.guard, "/.obsidian/plugins/x/main.js", "PUT")
        self.assertTrue(status.startswith("403"))
        self.assertFalse(self.app.called)

    def test_community_plugins_blocked(self):
        status, _ = call_guard(self.guard, "/.obsidian/community-plugins.json", "PUT")
        self.assertTrue(status.startswith("403"))

    def test_normal_settings_write_allowed(self):
        status, _ = call_guard(self.guard, "/.obsidian/app.json", "PUT")
        self.assertTrue(status.startswith("200"))

    def test_move_into_plugins_blocked(self):
        status, _ = call_guard(
            self.guard,
            "/notes/a.md",
            "MOVE",
            destination="http://example.com/.obsidian/plugins/x/main.js",
        )
        self.assertTrue(status.startswith("403"))

    def test_read_only_blocks_write(self):
        guard = DavGuard(self.app, self.root, read_only=True)
        status, _ = call_guard(guard, "/notes/a.md", "PUT")
        self.assertTrue(status.startswith("403"))
        self.assertFalse(self.app.called)

    def test_read_only_allows_read(self):
        guard = DavGuard(self.app, self.root, read_only=True)
        status, _ = call_guard(guard, "/notes/a.md")
        self.assertTrue(status.startswith("200"))

    def test_normal_write_allowed(self):
        status, _ = call_guard(self.guard, "/notes/a.md", "PUT")
        self.assertTrue(status.startswith("200"))


if __name__ == "__main__":
    unittest.main()
