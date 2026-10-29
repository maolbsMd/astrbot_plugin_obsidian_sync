"""Vault 路径解析与只读检索工具。

本模块刻意不依赖 AstrBot，便于单元测试、复用与审阅。
所有对外路径都必须经过 ``resolve_note_path`` / ``resolve_dir_path``，
它们用 realpath + commonpath 做边界判断，而不是字符串前缀比较。
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

NOTE_SUFFIX = ".md"


class PathRejected(ValueError):
    """路径不合法（越界、绝对路径、隐藏目录等）。"""


def _normalize(rel: str) -> str:
    """统一分隔符、去掉开头的斜杠、折叠重复斜杠。"""
    text = str(rel or "").strip().replace("\\", "/")
    text = text.lstrip("/")
    while "//" in text:
        text = text.replace("//", "/")
    return text


def is_protected_dav_write(path: str) -> bool:
    """WebDAV 写入保护：拦截 Obsidian 插件目录与 git hooks。

    `.obsidian/plugins/` 与 `.obsidian/community-plugins.json` 可以让客户端
    在下一次启动 Obsidian 时自动加载任意 JS，因此必须禁止远程写入。
    """
    parts = [part for part in str(path or "").replace("\\", "/").split("/") if part]
    if not parts:
        return False
    lowered = [part.lower() for part in parts]
    if ".git" in lowered:
        return True
    if lowered[0] == ".obsidian":
        if len(lowered) >= 2 and lowered[1] == "plugins":
            return True
        if len(lowered) == 2 and lowered[1] == "community-plugins.json":
            return True
    return False


def clip_text(text: object, limit: int) -> str:
    """按字符数截断，超长时以省略号结尾。"""
    value = str(text or "")
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def is_within(root: Path, target: Path) -> bool:
    """判断 target 是否位于 root 内（解析符号链接与大小写）。"""
    try:
        root_real = os.path.normcase(os.path.realpath(root))
        target_real = os.path.normcase(os.path.realpath(target))
        return os.path.commonpath([root_real, target_real]) == root_real
    except ValueError:
        # 不同盘符、空路径等
        return False


def resolve_root(vault_root: Path, subdir: str = "") -> Path:
    """返回实际读写根目录。

    ``subdir`` 为空时，若 ``vault_root/obsidian_vault`` 已存在则使用它
    （兼容 Remotely Save 把库建在子目录的情况），否则使用 vault_root 本身。
    """
    root = Path(vault_root).expanduser().resolve()
    sub = _normalize(subdir)
    if sub:
        if Path(sub).is_absolute() or (len(sub) > 1 and sub[1] == ":"):
            raise PathRejected("vault_subdir 不接受绝对路径")
        if ".." in Path(sub).parts:
            raise PathRejected("vault_subdir 不允许包含 ..")
        candidate = (root / sub).resolve()
        if not is_within(root, candidate):
            raise PathRejected("vault_subdir 越界")
        return candidate
    nested = root / "obsidian_vault"
    if nested.is_dir():
        return nested.resolve()
    return root


def ensure_md(rel: str) -> str:
    """补齐 .md 后缀，并拒绝空路径与目录路径。"""
    text = _normalize(rel)
    if not text:
        raise PathRejected("笔记路径不能为空")
    if text.endswith("/"):
        raise PathRejected("笔记路径不能以 / 结尾")
    if not text.lower().endswith(NOTE_SUFFIX):
        text += NOTE_SUFFIX
    return text


def _reject_unsafe(rel: str, allow_hidden: bool) -> None:
    if Path(rel).is_absolute() or (len(rel) > 1 and rel[1] == ":"):
        raise PathRejected("不接受绝对路径")
    if ".." in Path(rel).parts:
        raise PathRejected("路径越界")
    if not allow_hidden:
        for part in Path(rel).parts:
            if part.startswith("."):
                raise PathRejected("禁止访问隐藏目录")


def resolve_note_path(root: Path, note_path: str, allow_hidden: bool = False) -> Path:
    """把相对路径解析成 root 内的绝对文件路径，越界即抛 PathRejected。"""
    rel = ensure_md(note_path)
    _reject_unsafe(rel, allow_hidden)
    target = Path(os.path.abspath(os.path.join(root, rel)))
    if not is_within(root, target):
        raise PathRejected("路径越界")
    return target


def resolve_dir_path(root: Path, subfolder: str = "", allow_hidden: bool = False) -> Path:
    """解析子目录路径；空字符串表示 root 本身。"""
    rel = _normalize(subfolder)
    if not rel:
        return Path(root)
    _reject_unsafe(rel, allow_hidden)
    target = Path(os.path.abspath(os.path.join(root, rel)))
    if not is_within(root, target):
        raise PathRejected("路径越界")
    return target


def relative_display(root: Path, path: Path) -> str:
    """返回相对 root 的 POSIX 风格路径，用于展示。"""
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return Path(path).name


def iter_note_files(root: Path, start: Path | None = None) -> Iterable[Path]:
    """遍历 Markdown 笔记，跳过隐藏目录与符号链接文件。"""
    base = Path(start) if start is not None else Path(root)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(name for name in dirnames if not name.startswith("."))
        for name in sorted(filenames):
            if name.startswith(".") or not name.lower().endswith(NOTE_SUFFIX):
                continue
            full = Path(dirpath) / name
            if full.is_symlink():
                continue
            yield full


def count_notes(root: Path) -> int:
    return sum(1 for _ in iter_note_files(root))


def search_notes(
    root: Path,
    keyword: str,
    limit: int = 5,
    max_file_bytes: int = 2 * 1024 * 1024,
    snippet_chars: int = 300,
    snippets_per_note: int = 2,
) -> list[dict]:
    """按关键词搜索笔记，返回 [{path, snippets}]。

    规则：
    - 关键词为空直接返回空列表（避免空串匹配全部笔记）；
    - 超过 ``max_file_bytes`` 的文件跳过，防止大文件拖垮内存；
    - 片段按行截取并截断到 ``snippet_chars``；
    - 先命中的文件先返回，最多 ``limit`` 条。
    """
    kw = str(keyword or "").strip().lower()
    if not kw:
        return []

    results: list[dict] = []
    for path in iter_note_files(root):
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rel = relative_display(root, path)
        text_low = text.lower()
        if kw not in rel.lower() and kw not in text_low:
            continue

        snippets: list[str] = []
        if kw in text_low:
            for line in text.splitlines():
                if kw in line.lower():
                    snippet = clip_text(line.strip(), snippet_chars)
                    if snippet and snippet not in snippets:
                        snippets.append(snippet)
                    if len(snippets) >= snippets_per_note:
                        break
        if not snippets:
            snippets = ["（文件名匹配）"]

        results.append({"path": rel, "snippets": snippets})
        if len(results) >= limit:
            break
    return results
