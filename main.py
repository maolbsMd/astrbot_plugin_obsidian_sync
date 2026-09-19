import os
import re
import glob
import threading
import logging
from pathlib import Path
from astrbot.api.all import *
from astrbot.api.event import filter

logger = logging.getLogger("astrbot_plugin_obsidian_sync")

@register("astrbot_plugin_obsidian_sync", "Amadeus Kurisu & Neko", "Obsidian WebDAV 同步与 LLM 知识库连接插件", "1.0.0")
class ObsidianSyncPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        
        self.host = self.config.get("host", "0.0.0.0")
        self.port = int(self.config.get("port", 6190))
        self.username = self.config.get("username", "neko")
        self.password = self.config.get("password", "kurisu_loves_cat")
        self.vault_path = self.config.get("vault_path", "/AstrBot/data/obsidian_vault")
        self.auto_start = self.config.get("auto_start", True)
        
        # 确保 vault 目录存在
        os.makedirs(self.vault_path, exist_ok=True)
        
        self.server_thread = None
        self.server_instance = None
        self.is_running = False
        
        if self.auto_start:
            self._start_webdav_service()

    def _resolve_vault_path(self, note_path: str) -> tuple[str, str]:
        """
        智能解析并对齐真实 Vault 路径。
        若用户客户端在 WebDAV 根下同步到了子目录（如 obsidian_vault/），
        自动检测并统一寻址，防止跨级存储与多层嵌套。
        """
        base_vault = os.path.abspath(self.vault_path)
        # 检测是否存在同名内层 vault 目录（常见于 Remotely Save 指定了子目录）
        nested_vault = os.path.join(base_vault, "obsidian_vault")
        target_root = nested_vault if os.path.isdir(nested_vault) else base_vault

        clean_path = note_path.strip().lstrip("/\\")
        # 如果路径以 obsidian_vault/ 开头，根据 target_root 进行规范化
        if clean_path.startswith("obsidian_vault/"):
            sub_path = clean_path[len("obsidian_vault/"):]
            full_path = os.path.abspath(os.path.join(target_root, sub_path))
        else:
            full_path = os.path.abspath(os.path.join(target_root, clean_path))

        return target_root, full_path

    def _start_webdav_service(self):
        """在后台线程中启动 WsgiDAV 服务"""
        if self.is_running:
            return
            
        def run_server():
            try:
                from wsgidav.wsgidav_app import WsgiDAVApp
                from cheroot import wsgi
                
                dav_config = {
                    "host": self.host,
                    "port": self.port,
                    "provider_mapping": {
                        "/": self.vault_path
                    },
                    "simple_dc": {
                        "user_mapping": {
                            "*": {
                                self.username: {
                                    "password": self.password,
                                    "roles": ["admin"]
                                }
                            }
                        }
                    },
                    "verbose": 1,
                    "logging": {
                        "enable": False
                    }
                }
                
                app = WsgiDAVApp(dav_config)
                server = wsgi.Server((self.host, self.port), app)
                self.server_instance = server
                self.is_running = True
                logger.info(f"[ObsidianSync] WebDAV 服务启动成功: http://{self.host}:{self.port}，挂载目录: {self.vault_path}")
                server.start()
            except Exception as e:
                self.is_running = False
                logger.error(f"[ObsidianSync] WebDAV 服务启动失败: {e}")

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

    def _stop_webdav_service(self):
        """停止 WebDAV 服务"""
        if self.server_instance and self.is_running:
            try:
                self.server_instance.stop()
            except Exception:
                pass
            self.is_running = False
            logger.info("[ObsidianSync] WebDAV 服务已停止")

    # ================= 用户指令 =================
    @filter.command("obsidian")
    async def cmd_obsidian(self, event: AstrMessageEvent):
        """Obsidian 同步服务管理指令"""
        msg = event.message_str.strip().split()
        subcmd = msg[1] if len(msg) > 1 else "status"
        
        if subcmd == "status":
            status_text = "🟢 运行中" if self.is_running else "🔴 已停止"
            notes_count = len(glob.glob(os.path.join(self.vault_path, "**", "*.md"), recursive=True))
            yield event.plain_result(
                f"📝 Obsidian WebDAV 同步服务状态\n"
                f"--------------------------\n"
                f"服务状态: {status_text}\n"
                f"监听端口: {self.port}\n"
                f"挂载路径: {self.vault_path}\n"
                f"当前笔记数: {notes_count} 篇\n"
                f"认证用户: {self.username}"
            )
        elif subcmd == "restart":
            self._stop_webdav_service()
            self._start_webdav_service()
            yield event.plain_result(f"🔄 Obsidian WebDAV 服务正在重启至端口 {self.port}...")
        else:
            yield event.plain_result("用法:\n/obsidian status - 查看状态\n/obsidian restart - 重启服务")

    # ================= LLM 工具 (防止记忆遗忘 & 双向知识库连接) =================

    @llm_tool(name="search_obsidian_notes")
    async def search_obsidian_notes(self, event: AstrMessageEvent, keyword: str) -> str:
        """
        在用户的 Obsidian Vault 笔记库中根据关键词搜索相关的 Markdown 笔记。
        当需要回忆用户的备忘、学习笔记、考研进度、长期规划或特定知识时调用。
        """
        if not os.path.exists(self.vault_path):
            return "Obsidian 笔记库目录尚未创建。"
            
        md_files = glob.glob(os.path.join(self.vault_path, "**", "*.md"), recursive=True)
        if not md_files:
            return "当前 Obsidian 笔记库为空，尚未同步任何 Markdown 笔记。"
            
        matches = []
        kw_lower = keyword.lower()
        
        for file_path in md_files:
            rel_path = os.path.relpath(file_path, self.vault_path)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                # 检查文件名或内容是否匹配
                if kw_lower in rel_path.lower() or kw_lower in content.lower():
                    # 提取匹配片段
                    snippets = []
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        if kw_lower in line.lower():
                            start = max(0, idx - 1)
                            end = min(len(lines), idx + 2)
                            snippet = "\n".join(lines[start:end]).strip()
                            if snippet and snippet not in snippets:
                                snippets.append(snippet)
                            if len(snippets) >= 2:
                                break
                    preview = "\n---\n".join(snippets) if snippets else "（文件名匹配）"
                    matches.append(f"📄 笔记: {rel_path}\n{preview}")
            except Exception as e:
                continue
                
            if len(matches) >= 5:
                break
                
        if not matches:
            return f"在 Obsidian 笔记库中未检索到包含 '{keyword}' 的内容。"
            
        return f"🔍 Obsidian 检索结果 (关键词: '{keyword}'):\n\n" + "\n\n====================\n\n".join(matches)

    @llm_tool(name="read_obsidian_note")
    async def read_obsidian_note(self, event: AstrMessageEvent, note_path: str, max_lines: int = 200) -> str:
        """
        读取指定的 Obsidian 笔记全文或前部分内容。
        note_path: 相对 Vault 的路径，如 '考研/高数第二讲.md' 或 'Inbox/备忘录.md'。
        """
        # 兼容后缀
        if not note_path.endswith(".md"):
            note_path += ".md"
            
        full_path = os.path.abspath(os.path.join(self.vault_path, note_path))
        # 路径安全检查，防止越界访问
        if not full_path.startswith(os.path.abspath(self.vault_path)):
            return "访问拒绝：非法的笔记路径。"
            
        if not os.path.exists(full_path):
            return f"未找到指定的笔记文件: {note_path}"
            
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            content = "".join(lines[:max_lines])
            total_lines = len(lines)
            info = f"（共 {total_lines} 行，展示前 {len(lines[:max_lines])} 行）" if total_lines > max_lines else ""
            return f"📖 笔记内容 [{note_path}] {info}:\n\n{content}"
        except Exception as e:
            return f"读取笔记失败: {str(e)}"

    @llm_tool(name="write_obsidian_note")
    async def write_obsidian_note(self, event: AstrMessageEvent, note_path: str, content: str, mode: str = "append") -> str:
        """
        向用户的 Obsidian 笔记库中写入或追加内容，用于沉淀长期记忆、学习总结、每日复盘等。
        note_path: 相对 Vault 路径，例如 'Daily/2026-09-17.md' 或 '高数/知识点.md'。
        content: 要写入的 Markdown 内容。
        mode: 'append' (默认追加到末尾) 或 'overwrite' (覆盖写入)。
        """
        if not note_path.endswith(".md"):
            note_path += ".md"
            
        full_path = os.path.abspath(os.path.join(self.vault_path, note_path))
        if not full_path.startswith(os.path.abspath(self.vault_path)):
            return "访问拒绝：非法的笔记路径。"
            
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        try:
            write_mode = "a" if mode == "append" else "w"
            with open(full_path, write_mode, encoding="utf-8") as f:
                if write_mode == "a" and os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                    f.write("\n\n" + content.strip() + "\n")
                else:
                    f.write(content.strip() + "\n")
            return f"✅ 成功{'追加内容到' if mode == 'append' else '写入'}笔记: {note_path}"
        except Exception as e:
            return f"写入笔记失败: {str(e)}"

    @llm_tool(name="list_obsidian_notes")
    async def list_obsidian_notes(self, event: AstrMessageEvent, subfolder: str = "") -> str:
        """
        列出 Obsidian Vault 内的笔记和目录结构。
        subfolder: 可选子文件夹路径，留空为根目录。
        """
        target_dir = os.path.abspath(os.path.join(self.vault_path, subfolder))
        if not target_dir.startswith(os.path.abspath(self.vault_path)):
            return "访问拒绝：非法的目录路径。"
            
        if not os.path.exists(target_dir):
            return f"目录不存在: {subfolder}"
            
        items = []
        for root, dirs, files in os.walk(target_dir):
            rel_root = os.path.relpath(root, self.vault_path)
            prefix = "" if rel_root == "." else f"📁 {rel_root}/\n"
            for f in files:
                if f.endswith(".md"):
                    items.append(f"  📄 {os.path.join(rel_root, f) if rel_root != '.' else f}")
                    
        if not items:
            return f"目录 [{subfolder or '根目录'}] 下没有找到任何 Markdown 笔记。"
            
        return f"📂 Obsidian 笔记列表 (共 {len(items)} 篇):\n" + "\n".join(items[:50])
