# 启动包 — 语言口语演练 Agent

这是一个可以直接喂给 **Claude Code** 的规格驱动启动包。以"先写规格、再垂直切片"的姿势开工。

## 文件清单

- `SPEC.md` — 完整规格：四模块、与 langhelper 的分工、Debrief schema、导出格式契约、分期计划
- `CLAUDE.md` — 项目上下文与不可违背的核心约束（Claude Code 每次会话自动读）
- `tasks/01-first-slice.md` — 第一个垂直切片任务：文字版核心闭环
- `prompts/persona_template.md` — 角色卡模板（含二期隐藏诱导槽位）+ 内置场景示例
- `prompts/debrief_prompt.md` — Debrief 结构化输出 prompt（对齐 langhelper 五字段 + zh）

## 怎么用

1. 把整个文件夹作为项目根目录，用 Claude Code 打开
2. `CLAUDE.md` 会被自动读取，锁定项目约束
3. 第一句别急着让它写代码，让它先读 `SPEC.md`，再按 `tasks/01-first-slice.md` 开场：
   先提 SQLite schema 和文件结构给你确认，确认后再实现
4. 每完成一刀，跑通 + 单元测试，再进下一刀

## 日常使用（不用命令行）

文字版闭环 + 语音层 + 最薄前端都已经跑通（见 CLAUDE.md「当前进度」）。日常练习不需要再碰命令行：

- 双击项目根目录的 `run.bat`，或桌面上的 "LanguageAgent" 快捷方式——会自动启动后端服务并
  打开浏览器到 `http://127.0.0.1:8000/`。
- 用完直接关掉那个跳出来的黑色命令行窗口即可停止服务（窗口标题是
  "LanguageAgent server (close this window to stop)"）。
- 前提：`.env` 里已经填好 `GROQ_API_KEY`（必需）和 `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`
  （没填也能跑，TTS 会退回占位提示音）。

## 开发顺序

1. **文字版核心闭环**（task 01）：对话 → 结束 → Debrief → 存库 → 导出
2. **加语音层**：Groq Whisper STT + Azure TTS，包在演练回合外
3. **加口语诱导**（二期）：检索旧表达注入角色卡隐藏目标

## 记住三条铁律

1. 演练中 AI 绝不跳出角色纠错
2. 口语诱导的旧表达作为隐藏目标注入，绝不明示
3. 不碰 Anki 数据库，只写自己的 SQLite，单向导出给 langhelper
