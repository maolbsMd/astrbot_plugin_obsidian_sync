---
name: academic-note-workflow
description: 自动化整理考研与理工科学习笔记工作流。支持电路与信号系统矢量图绘制（多方案轻量渲染：rsvg-convert、ReportLab、无头浏览器兜底）、原生LaTeX防转义写入，以及多层级Obsidian Vault附件与笔记自动同步分发。
---

# 理工科考研笔记与矢量绘图自动化工作流 (Academic Note Workflow)

本 Skill 旨在解决理工科（特别是信号与系统、电路分析、通信原理）学习笔记整理中的高频痛点：
1. **多后端轻量矢量图渲染**：告别单一庞大浏览器内核依赖，提供超轻量级方案与多重兜底。
2. **公式防乱码写入机制**：杜绝 Shell 变量展开及转义符污染 LaTeX 公式（如 `$`、`\frac`、`\int`）。
3. **Obsidian Vault 路径智能适配**：解决多层嵌套目录与 attachments 相对路径错位问题。

---

## 渲染引擎方案对比 (Rendering Engines)

| 方案 | 核心工具 | 依赖大小 | 渲染速度 | 特点与适用场景 |
| :--- | :--- | :--- | :--- | :--- |
| **方案 A (首选推荐)** | `librsvg2-bin` (`rsvg-convert`) | ~3 MB | < 50ms | 极度轻量，无 X11/GUI 开销，高保真渲染 SVG 到高分 PNG |
| **方案 B (纯 Python)** | `reportlab` + `PIL` | 内置/极小 | < 100ms | 纯代码绘制基础几何图形/框图，零外部二进制依赖 |
| **方案 C (通用兜底)** | `chromium --headless` | ~200 MB | 1-2s | 终极兼容方案，支持任意复杂 CSS/Web 特性，内存占用较大 |

---

## 核心脚本指南

- **矢量转图调度器**：`scripts/render_svg.py`
  自动按优先级探测当前系统环境，依次尝试 `rsvg-convert` -> `chromium`，保证在任何 Linux 环境下均可无缝输出高清图像。
  ```bash
  python3 scripts/render_svg.py input.svg output.png [dpi=300]
  ```

- **Obsidian 笔记安全分发**：
  必须使用 Python `open(path, 'w', encoding='utf-8')` 或原生文件写入工具，禁止在含有 `$` 符号的内容上直接通过 bash 管道拼接。

---

## 目录分发规范

- Vault 根目录优先寻找：`/AstrBot/data/plugin_data/astrbot_plugin_obsidian_sync/vault/`
- 附件统一投放目录：`attachments/`（并在根目录与对应层级做双重镜像以防客户端解析差异）。
- 笔记内部图片统一采用 `![[filename.png]]` 短格式引用。
