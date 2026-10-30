# Changelog

## 1.4.0

### Added

- 新增 `insert_obsidian_attachment` 工具：把**当前消息**里的图片/文件保存到笔记库的 `attachments/`，并追加 `![[...]]`（图片）或 `[[...]]`（其它文件）到指定笔记。
- 图片按文件头识别 PNG/JPEG/GIF/WebP，重名自动加时间戳+随机后缀，不会覆盖已有附件。
- 支持可选 `caption` 说明文字，插在附件下方。
- 新配置：`attachment_dir`（默认 `attachments`）、`max_attachment_mb`（默认 10，1–50）。
- 附件插入后立即失效索引，笔记马上可以被搜索到。

### Notes

- 只读取当前消息里的附件，不接受模型传入的任意本地路径或 URL，避免被提示注入诱导读取服务器文件。
- 需要 `write_enabled: true`；附件大小超过上限会拒绝。

## 1.3.3

### Changed

- **移除默认用户名 `neko`**：`username` 留空或仍为旧默认值 `neko` 时，自动生成 `vault_xxxxxxxx` 并写回配置。
- 副作用：升级后 Remotely Save 的用户名需要同步更新，否则会收到 `401 Unauthorized`。
- 修正配置提示里"18 位密码"的旧文案（实际是 24 个字符）。

### Notes

- 这是本插件最后一个预置凭据：用户名和密码现在都由插件随机生成，代码/文档里不再有可直接登录的默认组合。

## 1.3.2

### Changed

- 作者字段改为 **`maolbsMd`**。
- 注意：`author` 同时是插件身份 `author/name` 的一部分，plugin_id 会随之变化。如果已经在市场发布过，需要在市场后台按新身份更新/重新提交一次。
- 功能无变化。

## 1.3.1

### Changed

- 市场展示名改为 **「Obsidian 第二大脑」**，短描述改为「手机电脑自动同步 Obsidian，AI 帮你搜索、整理并记住每一篇笔记。」
- 补充标签：`第二大脑`、`知识库`、`AI`。
- 功能与 1.3.0 完全一致；仅为插件市场展示优化。

## 1.3.0

### Added

- **软删除 / 回收站**：`/obsidian rm <笔记>` 与 `delete_obsidian_note` 工具只把笔记移动到插件数据目录的 `trash/<时间戳>/`，不会真正删除文件。
- `/obsidian trash` 查看最近删除（最多 10 项），`/obsidian restore <ID>` 恢复；恢复时若原路径已有文件会拒绝，避免覆盖。
- 回收站自动清理：`trash_keep_days`（默认 30 天，0 = 永久）、`trash_max_items`（默认 100，0 = 不限）。
- `delete_enabled` 配置（默认 **关闭**）：即使开启，LLM 也只能软删除；`write_enabled` 关闭时同样禁止删除。
- `doctor` 增加回收站条目与保留策略展示。

### Changed

- 笔记工具从 4 个增加到 5 个（新增 `delete_obsidian_note`，默认不可用）。
- 删除后立即失效索引，搜索不会返回已删除笔记。

## 1.2.0

### Added

- SQLite FTS5 全文索引：中文优先 `trigram`，不可用时退 `unicode61`，再不可用则用 LIKE；启动后台构建、按 `mtime/size` 增量同步，Bot 写入后立即刷新。新增 `build_index_on_start`、`index_refresh_seconds` 配置。
- `/obsidian reindex`：强制重建索引。
- `/obsidian history <笔记>`、`/obsidian undo <笔记>`：查看历史版本、回滚到最新备份（恢复前会再备份当前内容）。
- `/obsidian doctor`：检查监听地址、密码来源、`.obsidian/plugins`、索引、历史占用、端口连通性与磁盘剩余。
- 工具调用审计：写入 `audit.jsonl`（时间、工具、发送者、目标、耗时、成败，不含正文），超过 2MB 自动轮转；`/obsidian audit` 查看最近 20 条。
- `allow_weak_password` 配置项（默认关闭，仅本机调试用）。

### Changed

- 搜索从全盘扫描改为索引查询，索引查询失败时自动回退原有扫描逻辑。
- 文档修正：自动生成的密码是 `token_urlsafe(18)` 生成的 24 个字符（约 144 bit 熵），此前误写为"18 位"。
- 测试从 49 个增加到覆盖索引、历史/撤销、审计、自检。

## 1.1.0

安全版本。默认值有变化，升级前请阅读 README 的「从 v1.0.x 升级」。

### Security

- 路径校验改为 `realpath + commonpath`，修复 `vault` 与 `vault_private` 前缀相同导致的越界读写（含单测回归）。
- 默认监听地址改为 `127.0.0.1`；非回环监听需要显式开启 `allow_public_bind`。
- 默认/弱口令启动时自动生成 18 位随机密码并写回配置；新增 `allow_weak_password` 仅供本机调试。
- WebDAV 中间件拒绝写入 `.obsidian/plugins/**`、`.obsidian/community-plugins.json`、`.git/**`，阻断同步投递恶意 Obsidian 插件的链路；`MOVE` 的 `Destination` 同样校验。
- 只读模式 `read_only` 下所有写方法返回 403。
- LLM 工具增加会话范围控制：`private_only`、`allowed_users`（管理员始终允许）。
- 笔记内容以 `trust="untrusted"` 边界返回给模型，降低存储型提示注入风险。
- 插件管理指令 `/obsidian` 限制为 AstrBot 管理员。
- 密码字段在面板中标记 `secret` 遮罩显示。

### Fixed

- 新增 `terminate()`：插件停用/重载时释放 WebDAV 端口，避免旧口令服务残留。
- 启动顺序改为 `prepare()` 成功后才置为运行中，端口占用时不再误报"启动成功"。
- 所有文件 IO 改走 `asyncio.to_thread`，避免阻塞事件循环。
- 搜索：空关键词直接返回、跳过超大文件、限制结果条数与片段长度。
- 读取：`max_lines` 限制在 1–500，单篇超过 `max_note_mb` 拒绝读取。
- 写入：`mode` 只接受 `append`/`overwrite`，覆盖写使用临时文件 + `os.replace` 原子替换，写前备份到 `history/`。
- 配置健壮性：`port`/`max_note_mb` 等非法值回退默认，不再导致插件加载失败。
- `vault_path` 默认使用 `StarTools.get_data_dir()`，不再依赖进程工作目录；`vault_subdir` 非法时回退并记录日志。

### Changed

- 依赖加上上界：`wsgidav>=4.3,<5`、`cheroot>=11,<12`。
- 代码拆分：`vault_paths.py`（纯逻辑）、`webdav_guard.py`（WSGI 中间件），便于测试。
- 去掉 `from astrbot.api.all import *`，改为显式导入；工具 docstring 补 `Args:`。
- `metadata.yaml`：版本 `1.1.0`、补充 `short_desc`、图标改为 `logo.png`、去掉文档外的平台键。
- 新增 `tests/`（49 个用例，覆盖路径绕过回归、WSGI 守卫、初始化与写入流程）与 GitHub Actions CI（ruff + unittest + py_compile）。
