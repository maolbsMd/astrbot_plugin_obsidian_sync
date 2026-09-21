# AstrBot Obsidian Sync & LLM Vault 插件

将用户的 **Obsidian** 笔记库与 **AstrBot** 以及 **LLM (大语言模型)** 实现无缝双向连接！

## 核心特性

1. **一键内置 WebDAV 服务**：
   - 依赖纯 Python 的 `wsgidav` 与 `cheroot`，无需在服务器上额外部署 Nginx/Apache 或 Docker WebDAV 容器。
   - 默认监听端口可自定义（如 `6190`），内置基础身份认证。
   - 适配移动端及电脑端 Obsidian 经典同步插件 **Remotely Save**。

2. **防止 LLM 遗忘与长效知识库连接**：
   - 为 Bot 注入 4 个原生 `@llm_tool`：
     - `search_obsidian_notes`: 根据关键词搜索笔记。
     - `read_obsidian_note`: 读取指定 Markdown 笔记。
     - `write_obsidian_note`: 追加或覆盖写入笔记（沉淀长期记忆、每日复盘）。
     - `list_obsidian_notes`: 浏览笔记目录结构。
   - 你的个人日记、考研攻坚、高数推导，Bot 都能实时读写与记忆检索！

3. **合规数据持久化**：
   - 默认存储路径遵循官方规范，保存在 `data/plugin_data/astrbot_plugin_obsidian_sync/vault`。
   - 支持自定义外部路径挂载，便于与宿主机既有的 Obsidian 知识库直接联动。

## ⚠️ 安全与隐私说明（重要）

- **修改默认凭据**：本插件内置的 WebDAV 服务默认监听 `0.0.0.0`。为了您的笔记数据安全，**请在安装插件后第一时间前往 AstrBot 管理面板修改 WebDAV 用户名与密码**，切勿使用默认弱口令暴露于公网！
- **端口访问控制**：建议在云服务器防火墙/安全组中仅对常用访问 IP 开放对应的 WebDAV 端口，或通过反向代理配合 HTTPS 传输。

## Obsidian 端配置指南 (使用 Remotely Save)

1. 在 Obsidian 社区插件市场搜索并安装 **Remotely Save**。
2. 打开 Remotely Save 设置：
   - **同步方法 (Sync Method)**: 选 `WebDAV`
   - **服务器地址 (Server URL)**: `http://<你的服务器公网IP>:6190/`
   - **用户名 (Username)**: `<你在插件配置中设置的用户名>`
   - **密码 (Password)**: `<你在插件配置中设置的密码>`
3. 点击 **Check Connection (检查连接)**，提示成功后即可双向同步！
