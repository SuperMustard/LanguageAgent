# 任务 01 — 第一个垂直切片：文字版核心闭环

## 目标

交付一个**端到端能跑通的文字版**核心闭环，验证整个产品逻辑。**不含语音**（语音是下一刀）。

用户能在命令行或最简接口里：

1. 选一个场景，开始角色扮演对话（文字）
2. 多轮对话，AI 保持人设，**不跳出纠错**
3. 发"结束"信号，触发 Debrief
4. Debrief 产出病句记录（五字段 + zh）和生词，存进 SQLite
5. 一键导出成 langhelper 格式文件（病句 JSON / 生词 txt，按语言分文件）

## 范围（这一刀要做的）

- SQLite 数据库路径（**按下面"数据库路径要求"实现，别用相对路径**）
- SQLite schema 与读写：`expressions`（病句）、`words`（生词）两张表，含
  `language` / `mastery` / `last_practiced` 字段
- 场景角色卡加载（用 prompts/persona_template.md 的结构，先内置 1~2 个场景）
- 演练对话调用（Groq Llama 或先用任意可用 LLM 占位，接口要能换）
- "结束"信号触发 Debrief
- Debrief 调用（用 prompts/debrief_prompt.md），解析输出存库
- 导出函数：按 language 分组 → 病句吐 JSON 五字段数组、生词吐 `词|义` 纯文本
- 导出函数配**单元测试**（喂已知记录，断言输出格式逐字段正确、language 被剥离）

## 数据库路径要求（务必照做）

SQLite 文件是**唯一真相源**，路径处理必须稳，否则数据会散落或丢失。

- **绝对路径 + 环境变量**，绝不用相对路径（相对路径基于进程启动目录，从不同目录启动会
  产生多个散落的 db 文件）。
- 用环境变量 `LANGPRACTICE_DB` 指定，兜底一个持久目录默认值：

  ```python
  import os
  from pathlib import Path

  DB_PATH = Path(os.getenv(
      "LANGPRACTICE_DB",
      Path.home() / ".local/share/languageagent/agent.db"
  ))
  DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # 自动建目录
  ```

- **自动创建父目录**（如上 `mkdir(parents=True, exist_ok=True)`），首次运行不报错。
- **不进 git**：数据库文件和 `data/` 目录写进 `.gitignore`。练习数据是私人学习记录，
  且 SQLite 是二进制，不该进版本库。
- **不放 `/tmp`**（会被系统清空）。
- 若日后容器化部署：db 文件必须放挂载的**持久卷**上，否则重启丢数据。（一期不用管）

顺带：因为是唯一真相源，实现时可留一个简单的备份点（如导出时顺便 `cp` 一份 `.bak`），
但别放进会实时同步的云盘目录——同步工具可能在 SQLite 写入中途拷贝导致损坏。

## 不在这一刀（明确排除）

- 语音（STT/TTS）—— 下一刀
- 口语诱导（检索旧表达注入）—— 二期
- 前端网页 UI —— 先命令行或最简 FastAPI 接口验证即可
- 掌握度双向同步

## 验收标准

- 能完整走一遍：开始 → 多轮对话 → 结束 → Debrief → 存库 → 导出
- 演练过程中 AI 从不主动纠错（人工检查几轮对话确认）
- 导出的 `fr_sentences.json` 能被 langhelper 的 parse_sentences 正确解析
  （字段名、结构对得上；可写个小测试模拟 parse_sentences 的收录条件：
  每条至少有 zh 或 en_wrong）
- 导出的 `fr_words.txt` 每行 `词|义`，无重复
- 单元测试通过

## 给 Claude Code 的建议开场

先不要写代码。先读 SPEC.md 和 CLAUDE.md，然后：

1. 提出 SQLite schema 设计给我确认
2. 提出模块划分（文件结构）给我确认
3. 确认后再按垂直切片实现，先跑通再优化
