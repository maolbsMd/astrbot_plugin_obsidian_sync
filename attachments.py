"""附件保存与 Obsidian 嵌入标记。

纯标准库实现，方便单测。只负责“把字节写进 attachments/ 并生成嵌入语法”，
不处理网络下载；聊天里的图片/文件由 AstrBot 的消息组件解析成临时文件。
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime
from pathlib import Path

try:  # 包方式
    from .vault_paths import is_within
except ImportError:  # pragma: no cover - 脚本方式
    from vault_paths import is_within  # type: ignore[no-redef]

IMAGE_SUFFIXES = {"png", "jpg", "jpeg", "gif", "webp"}
_SAFE_NAME = re.compile(r"[^\w.\- ]+", re.UNICODE)


class AttachmentError(ValueError):
    """附件不合法（格式、大小、路径等）。"""


def detect_image(data: bytes) -> str:
    """根据文件头识别常见图片格式，返回扩展名（不含点）；不是图片返回空串。"""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return ""


def sanitize_filename(name: str, fallback: str = "file") -> str:
    """只保留文件名本身，去掉路径、控制字符和可疑符号。"""
    base = Path(str(name or "")).name
    base = _SAFE_NAME.sub("_", base).strip(" .")
    if not base:
        base = fallback
    return base[:60]


def save_attachment(
    root: Path,
    directory: Path,
    data: bytes,
    filename: str,
    forced_ext: str = "",
) -> Path:
    """把附件写到 directory 下，返回实际路径。

    - ``forced_ext`` 非空时强制使用该扩展名（例如按文件头识别出的 png）；
    - 文件名加时间戳 + 随机后缀，避免重名覆盖；
    - 写入前校验目标仍在笔记库内。
    """
    root = Path(root)
    directory = Path(directory)
    if not is_within(root, directory):
        raise AttachmentError("附件目录越界")
    directory.mkdir(parents=True, exist_ok=True)

    safe = sanitize_filename(filename)
    stem = sanitize_filename(Path(safe).stem or "file")[:30]
    if forced_ext:
        suffix = "." + forced_ext.lower().lstrip(".")
    else:
        suffix = Path(safe).suffix or ".bin"

    unique = f"{stem}-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}{suffix}"
    target = directory / unique
    if not is_within(root, target):
        raise AttachmentError("附件路径越界")

    with open(target, "xb") as handle:
        handle.write(data)
    return target


def embed_markup(relative_path: str, is_image: bool, caption: str = "") -> str:
    """生成 Obsidian 嵌入/链接语法；图片用 ![[...]]，其它文件用 [[...]]。"""
    link = f"![[{relative_path}]]" if is_image else f"[[{relative_path}]]"
    text = str(caption or "").strip()
    if text:
        link += "\n\n" + text
    return link
