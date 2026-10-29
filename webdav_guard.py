"""WebDAV WSGI 中间件。

在 WsgiDAV 之前做三件事：
1. 用 realpath 校验请求路径没有越出笔记库（防符号链接逃逸）；
2. 只读模式下拒绝所有写方法；
3. 拒绝写入 .obsidian/plugins、community-plugins.json 与 .git。
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:  # 包方式（AstrBot 正常加载方式）
    from .vault_paths import is_protected_dav_write, is_within
except ImportError:  # pragma: no cover - 兼容脚本方式加载
    from vault_paths import is_protected_dav_write, is_within  # type: ignore[no-redef]

MUTATING_METHODS = frozenset(
    {
        "PUT",
        "DELETE",
        "MKCOL",
        "MOVE",
        "COPY",
        "PROPPATCH",
        "LOCK",
        "UNLOCK",
    }
)


def _forbidden(start_response, reason: str):
    body = f"403 Forbidden: {reason}\n".encode()
    start_response(
        "403 Forbidden",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


class DavGuard:
    """路径越界、只读模式与危险写入保护。"""

    def __init__(self, app, root: Path, read_only: bool = False) -> None:
        self.app = app
        self.root = Path(root)
        self.read_only = read_only

    def __call__(self, environ, start_response):
        path = unquote(environ.get("PATH_INFO") or "/")
        if not is_within(self.root, os.path.join(str(self.root), path.lstrip("/"))):
            return _forbidden(start_response, "路径越界")

        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        if method in MUTATING_METHODS:
            if self.read_only:
                return _forbidden(start_response, "WebDAV 处于只读模式")
            targets = [path]
            destination = environ.get("HTTP_DESTINATION")
            if destination:
                targets.append(unquote(urlsplit(destination).path or "/"))
            for target in targets:
                if is_protected_dav_write(target):
                    return _forbidden(start_response, "禁止写入敏感目录")

        return self.app(environ, start_response)
