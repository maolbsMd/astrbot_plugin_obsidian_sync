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

## Obsidian 端配置指南 (使用 Remotely Save)

1. 在 Obsidian 社区插件市场搜索并安装 **Remotely Save**。
2. 打开 Remotely Save 设置：
   - **同步方法 (Sync Method)**: 选 `WebDAV`
   - **服务器地址 (Server URL)**: `http://<你的服务器公网IP>:6190/`
   - **用户名 (Username)**: `neko`
   - **密码 (Password)**: `kurisu_loves_cat`
3. 点击 **Check Connection (检查连接)**，提示成功后即可双向同步！
