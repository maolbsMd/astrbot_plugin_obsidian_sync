# Changelog

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
