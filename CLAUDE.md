# CLAUDE.md — 项目上下文与约束

> Claude Code 每次会话自动读本文件。这里写的是项目的"灵魂"和不可违背的约束，
> 具体需求见 `SPEC.md`。

## 这是什么项目

语言口语演练 agent。用户母语中文，练英语和法语口语（诊所、面试等场景）。
Agent 做口语演练 + 演练后诊断，把结果导出给 Anki 插件 langhelper 复习。

## 当前进度

- **task 01（文字版闭环）已完成并跑通**：角色卡对话 → "结束" → Debrief → 存 SQLite →
  导出 langhelper 格式，用真实 Groq API 验证过（不只是 mock）。
- **语音层已接上**：录音 → Groq Whisper STT → 复用同一套 `session.turn()` 角色扮演逻辑
  （铁律不受影响）→ Azure TTS 念出回复。手动测试脚本见 `scripts/voice_test.py`。
- 代码结构见 `langpractice/`：`llm/` `stt/` `tts/` 三层都是 Protocol 接口 + 具体实现，
  没配对应 API key 时自动退回 Mock，不阻塞开发（`GROQ_API_KEY` 缺失时 LLM 退回
  `MockLLMClient`、STT 端点直接 503；`AZURE_SPEECH_KEY` 缺失时 TTS 退回占位提示音）。
- **最薄前端单页已做完**：`web/index.html`，FastAPI 在 `GET /` 直接serve（`langpractice/app.py`
  的 `index()`）。选场景 → 开始演练（自动放开场语音）→ 麦克风按钮录音/发送 → 对话气泡 +
  自动放 AI 语音回复 → 结束演练渲染 Debrief 卡片（病句 zh/错句删除线/正确版/error_note/pattern
  + 生词 chips）→ 导出面板（按语言调 `GET /export/{language}`，文本框 + 一键复制，产品闭环
  最后一块拼图——不用再回命令行拿导出文件）→ 退出按钮（调 `POST /shutdown`，`os._exit`
  关进程，本地单人工具不用优雅关闭）。
  用 claude-in-chrome 在真实浏览器里点过一遍，开场语音真实播放，debrief 正确渲染，导出面板
  能从库里读到之前多场演练累积的真实数据，无 console 报错，窄窗口下也验证过不横向溢出。
  麦克风录音需要真人声音，没在自动化里测；一键复制用的 Clipboard API 在自动化环境里会卡在
  权限弹窗（脚本模拟点击没有真实 user gesture），真人点击不受影响，没能在自动化里测通。
- **日常启动不用命令行**：双击 `run.bat`（或桌面 "LanguageAgent" 快捷方式）——起后端 + 自动开
  浏览器；关掉跳出来的命令行窗口就是停服务。细节见 README「日常使用」。
- 改动历史看 `git log`，这里不重复维护——已知的非显而易见的坑记在下面「实现踩坑记录」。

## 技术栈

- Python + FastAPI 后端
- SQLite 存储（唯一真相源）
- Groq Whisper (STT) + Groq（LLM，见下方踩坑记录）+ Azure Speech (TTS)
- 薄前端单页（录音/放音/对话/反馈）—— 已做，见 `web/index.html`；`/docs` 的 Swagger UI 还留着方便测接口

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

## 实现踩坑记录

- **Groq 的模型列表会变**：`llama-3.3-70b-versatile` 已经从当前账号的可用模型里下架，
  现在默认用 `openai/gpt-oss-120b`（注意：这是 OpenAI 开源的开放权重模型，Groq 自己
  托管在它的硬件上跑，走的是 `GROQ_API_KEY` 和 Groq 的 endpoint，**不是在调 OpenAI 的
  API**，命名里的 `openai/` 只是 Groq 标注权重来源的前缀，跟 Meta 的 `llama-*`、阿里的
  `qwen/*` 是一个套路）。以后再 404，先用 `client.models.list()` 查当前账号实际有什么，
  别死记模型名。默认值在 `config.py` 的 `GROQ_MODEL` / `GROQ_WHISPER_MODEL`，`.env` 可覆盖。
- **LLM 生成的 `*叹气*` 这类舞台指示不能直接喂给 TTS**：Azure 会把星号原样念出来
  （"Asterisk soupire Asterisk"），拿合成音频回灌 Whisper 验证时才发现。已经在
  `langpractice/tts_text.py::strip_for_speech()` 里处理——只影响送进 TTS 的文本，
  文字记录（debrief transcript、返回给前端的文字）不受影响，不要在别的地方重复处理。
- **Azure Speech F0（免费档）TTS 硬限制 20 次请求/60 秒，不可调**（微软官方文档，
  https://learn.microsoft.com/azure/ai-services/speech-service/speech-services-quotas-and-limits）。
  正常演练节奏（几句话一个来回）不太会碰到，但连续测试（尤其是我边测边你也在测）很容易
  在一分钟内攒够 20 次触发 429。已在 `AzureTTSClient.synthesize()` 里加了 429 重试退避
  （读 `Retry-After` header，没有就退避 5 秒，最多重试 3 次）。真要更高吞吐得升级到 S0
  付费档——不要误以为是代码 bug 去瞎排查。
- **Groq 免费档也会 429**：各模型有各自的 RPM/RPD/TPM 上限（比如目前默认的
  `openai/gpt-oss-120b` 是 30 RPM），实际数字会变，账号真实限额去
  `console.groq.com/settings/limits` 查，别死记数字。`groq` 这个 SDK 自带 429 重试
  （认 `Retry-After` header），但默认只重试 2 次——已经在 `GroqLLMClient` 和
  `GroqWhisperSTT` 的构造函数里把 `max_retries` 调到 5（见对应文件），跟 Azure 那个是
  同一类问题：正常演练节奏不太会碰，连续测试容易撞。

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
