# CLAUDE.md — 项目上下文与约束

> Claude Code 每次会话自动读本文件。这里写的是项目的"灵魂"和不可违背的约束，
> 具体需求见 `SPEC.md`。

## 这是什么项目

语言口语演练 agent。用户母语中文，练英语和法语口语（诊所、面试等场景）。
Agent 做口语演练 + 演练后诊断，把结果导出给 Anki 插件 langhelper 复习。

## 技术栈

- Python + FastAPI 后端
- SQLite 存储（唯一真相源）
- Groq Whisper (STT) + Groq Llama (LLM) + Azure Speech (TTS)
- 薄前端单页（录音/放音/对话/反馈）

## 核心约束（违背即破坏产品）

1. **演练中 AI 绝不跳出角色纠错。** 角色扮演和纠错是两个完全独立的调用/模式。
   演练时只演角色；纠错只在用户发出"结束"信号后的 Debrief 阶段发生。

2. **口语诱导的旧表达必须作为隐藏目标注入角色卡**，让 AI 设计语境自然引导用户说出来，
   **绝不能明着提示或考问**。明示会同时毁掉沉浸感和诱导效果。（二期功能）

3. **不直接读写 Anki 的数据库**（collection.anki2）。agent 只写自己的 SQLite，
   通过导出文件单向喂给 langhelper。

4. **导出格式必须严格匹配 langhelper 导入器**（见 SPEC 导出格式契约）。
   病句是 JSON 五字段数组，生词是纯文本 `词|义`。字段名照抄，不自创。

## 编码偏好

- 垂直切片交付：每次交付一个端到端能跑的完整闭环，不按技术分层堆砌。
  第一刀 = 文字版 `角色卡对话 → 结束 → Debrief → 存 SQLite → 导出`，必须能跑通。
- 纯逻辑模块（掌握度更新、检索、Anki 格式化）**必须配单元测试**——它们有明确输入输出，
  是 debug 时最不想手动验的部分。
- 语音层和 LLM 对话难自动测，先把可测的逻辑测好。
- 优先用标准库和成熟依赖，别过度工程。SQLite 一条 WHERE 能解决的别上向量库。
- **SQLite 路径**：绝对路径 + 环境变量 `LANGPRACTICE_DB`，兜底持久目录默认值，自动建父目录。
  绝不用相对路径，db 文件和 `data/` 进 `.gitignore`。详见 tasks/01。

## 关键字段名（照抄，勿改）

病句卡 langhelper 字段：`zh` `en_wrong` `en_correct` `error_note` `pattern`
（`en_wrong`/`en_correct` 是通用槽位名，法语也用，别因 en 前缀改名）

生词卡：`word` `meaning`

agent 内部额外字段：`language` `mastery` `last_practiced`（导出病句/生词时剥离，不进 langhelper 文件）

## 已推迟的增量想法（别忘）

- **场景卡自动生成**：用户给一段自由描述，LLM 按 persona_template.md 的字段
  （role_identity / emotional_state / speaking_style / hidden_motivation /
  scenario_description / difficulty_level / target_language）自动填充生成新场景卡，
  免得每个场景都要手写。技术上是一次新的结构化 LLM 调用（跟 debrief 同套路），
  但需要落地存储（`scenarios` 表或 JSON 文件）才能复用，超出一期最小范围。
  一期先用内置场景把闭环跑通，但 `personas.py` 要设计成"加场景 = 加一条结构化数据"，
  为这个功能预留口子，不要写死 if/else。

## 开发流程约定

- 动手写代码前，先确认改动符合 SPEC 和本文件约束。
- 涉及导出格式的改动，对照 SPEC"导出格式契约"逐字段核对。
- 不确定时先问，不要自作主张扩大范围。
