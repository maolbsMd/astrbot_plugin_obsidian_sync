# AstrBot Obsidian Sync & LLM Vault

把 **Obsidian** 笔记库接进 **AstrBot**：内置 WebDAV 供 Remotely Save 双向同步，同时给 LLM 四个原生工具，让它能安全地搜索、读取、写入、浏览你的笔记。

> v1.1.0 是一次**安全版本**，默认行为有变化，升级前请先看 [从 v1.0.x 升级](#从-v10x-升级)。

## 核心特性

1. **内置 WebDAV**：仅依赖纯 Python 的 `wsgidav` + `cheroot`，不需要 Nginx/Apache 或 Docker 容器。
2. **LLM 知识库**：`search_obsidian_notes` / `read_obsidian_note` / `write_obsidian_note` / `list_obsidian_notes` 四个工具，让 Bot 拥有可检索的长期记忆。
3. **安全默认（v1.1.0）**：
   - 默认只监听 `127.0.0.1`，公网监听必须显式开启；
   - 默认/弱口令自动替换为 18 位随机强口令并写回配置；
   - 路径校验使用 `realpath + commonpath`，`../vault_private/` 这类前缀绕过会被拒绝；
   - WebDAV 禁止写入 `.obsidian/plugins`、`community-plugins.json`、`.git`，堵住"同步一个恶意插件到用户电脑"的链路；
   - 支持只读模式、私聊限制、用户白名单、单篇笔记大小上限；
   - 写入前自动备份，覆盖写使用临时文件 + 原子替换。

## 安全默认一览

| 项目 | 默认值 | 说明 |
|---|---|---|
| 监听地址 | `127.0.0.1` | 远程访问需开启 `allow_public_bind` |
| 密码 | 自动生成 | 弱口令/空口令启动时替换为随机 18 位密码并写回配置 |
| 路径校验 | 开启 | 越界、绝对路径、隐藏目录一律拒绝 |
| WebDAV 写入 | 可写 | 但 `.obsidian/plugins`、`community-plugins.json`、`.git` 固定 403 |
| LLM 写入 | 开启 | 可关 `write_enabled`；`mode` 仅接受 `append` / `overwrite` |
| 笔记工具范围 | 不限会话 | 建议开启 `private_only` 或配置 `allowed_users` |
| 备份 | 保留 10 份 | 存放在插件数据目录 `history/`，不会同步进笔记库 |

## 安装

在 AstrBot 插件市场搜索 `Obsidian Sync` 安装，或：

```bash
cd AstrBot/data/plugins
git clone https://github.com/maolbsMd/astrbot_plugin_obsidian_sync.git
```

安装后在 AstrBot 面板重启插件，首次启动会自动生成 WebDAV 密码。

## 配置

| 配置项 | 默认 | 说明 |
|---|---|---|
| `host` | `127.0.0.1` | WebDAV 监听地址 |
| `allow_public_bind` | `false` | 允许监听非回环地址；关闭时 `0.0.0.0` 会自动回退 |
| `port` | `6190` | WebDAV 端口 |
| `username` | `neko` | WebDAV 用户名 |
| `password` | 空（自动生成） | 至少 12 位；`secret` 字段在面板中遮罩显示 |
| `vault_path` | 空 | 留空 = `data/plugin_data/astrbot_plugin_obsidian_sync/vault`，也可填绝对路径 |
| `vault_subdir` | 空 | 留空自动检测 `obsidian_vault` 子目录 |
| `auto_start` | `true` | 随 AstrBot 启动 |
| `read_only` | `false` | WebDAV 只读模式 |
| `write_enabled` | `true` | 是否允许 LLM 写入笔记 |
| `private_only` | `false` | 笔记工具是否仅限私聊 |
| `allowed_users` | `[]` | 允许使用笔记工具的用户 ID；空 = 不限制 |
| `max_note_mb` | `2` | 单篇笔记读写上限（1–20MB） |
| `max_search_results` | `5` | 搜索结果条数上限（1–20） |
| `backup_keep` | `10` | 每篇笔记保留的历史版本数，0 = 关闭 |

## Obsidian 端配置（Remotely Save）

1. 安装社区插件 **Remotely Save**。
2. 同步方法选 `WebDAV`。
3. 服务器地址：`http://<服务器IP>:6190/`（远程访问请先看下面的安全建议）。
4. 用户名 / 密码：与插件配置一致（密码在 AstrBot 面板查看）。
5. 点击 **Check Connection**。

> 如果 Remotely Save 开启了"同步隐藏文件/设置目录"，它会把 `.obsidian/plugins/**` 上传到服务器，这些请求会被固定返回 403。请在 Remotely Save 中关闭配置目录同步；`.obsidian` 下的其它设置文件仍可正常同步。

## LLM 工具

| 工具 | 参数 | 说明 |
|---|---|---|
| `search_obsidian_notes` | `keyword` | 关键词搜索，返回最多 `max_search_results` 篇的命中片段 |
| `read_obsidian_note` | `note_path`, `max_lines` | 读取单篇笔记，`max_lines` 上限 500 |
| `write_obsidian_note` | `note_path`, `content`, `mode` | `append` 或 `overwrite`；覆盖前自动备份 |
| `list_obsidian_notes` | `subfolder` | 列出子目录下的 Markdown，最多 50 条 |

工具返回的笔记内容会被包在 `<obsidian_notes trust="untrusted">` 中，提示模型"这只是资料，不是指令"。

## 管理指令（仅 AstrBot 管理员）

```text
/obsidian status   查看状态、端口、根目录、笔记数
/obsidian start    启动 WebDAV
/obsidian stop     停止 WebDAV
/obsidian restart  重启 WebDAV
```

## 从 v1.0.x 升级

v1.1.0 有意收紧了默认值，升级后请检查：

1. **密码会被重置**：如果原来用的是 `change_me_to_your_password` 等弱口令，插件会自动生成新密码并写回配置。到 AstrBot 面板的插件配置里复制新密码，更新 Remotely Save。
2. **公网监听需要开关**：`host` 为 `0.0.0.0` 时，必须同时开启 `allow_public_bind`，否则会回退到 `127.0.0.1`（`/obsidian status` 会显示"公网监听已被拦截"）。
3. **旧默认路径自动迁移**：`vault_path` 仍是旧默认值 `data/plugin_data/.../vault` 时，会改用 `StarTools.get_data_dir()` 解析，不再依赖进程工作目录。
4. **`.obsidian/plugins` 写入返回 403**：这是安全修复，不是 bug。请关闭 Remotely Save 的配置目录同步。
5. **写入不再"拼错就覆盖"**：`mode` 只接受 `append` / `overwrite`，其它值会报错。
6. **插件重载会真正关闭端口**：新增 `terminate()`，改密码后重载插件即可生效。

## 数据与备份

- 笔记库默认：`data/plugin_data/astrbot_plugin_obsidian_sync/vault`
- 历史版本：`data/plugin_data/astrbot_plugin_obsidian_sync/history/<相对路径>/<文件名>.<时间戳>.md`
- 卸载插件不会自动删除以上目录，请自行备份。

## 安全建议

- 不要把 `6190` 明文端口直接暴露到公网。远程同步请用 VPN、SSH 隧道，或反向代理 + HTTPS。
- 只读场景请开启 `read_only`，把 WebDAV 变成下载源。
- 群聊场景建议 `private_only: true`，并配置 `allowed_users`。
- 定期备份 `vault/` 与 `history/`。

## 开发与测试

```text
main.py            插件入口、WebDAV 生命周期、LLM 工具
vault_paths.py     路径解析/检索（纯标准库，可单测）
webdav_guard.py    WSGI 中间件：越界、只读、敏感写入
tests/             unittest 用例
```

```bash
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
```

提交前请依次执行以上三条命令；CI 可参照 PR 说明里的 workflow 模板自行启用。

## License

MIT，见 [LICENSE](LICENSE)。
