# CLAUDE.md — 项目上下文与约束

> Claude Code 每次会话自动读本文件。这里写的是项目的"灵魂"和不可违背的约束，
> 具体需求见 `SPEC.md`。

## 这是什么项目

语言口语演练 agent。用户母语中文，练英语和法语口语（诊所、面试等场景）。
Agent 做口语演练 + 演练后诊断，把结果导出给 Anki 插件 langhelper 复习。

## 当前进度

- **文字/语音闭环 + Pipecat 全双工迁移都已完成**：角色卡对话 → "结束" → Debrief →
  存 SQLite → 导出 langhelper 格式，全程验证过（真实 API，不是 mock）。
- **架构是两个本地进程**（2026-08 从"回合制 REST"迁移到 Pipecat 全双工后定型）：
  - `langpractice/app.py`（端口 8000）：只管页面、场景列表、导出、退出，**不再自己跑
    任何 LLM/STT/TTS**。`GET /` 直接 serve `web/index.html`；`/pipecat` 挂载
    `web/pipecat/`（前端构建产物）为静态文件。
  - `langpractice/voice_bot.py`（端口 7860，Pipecat runner）：真正的语音 pipeline——
    `transport.input() → GroqSTTService → user_aggregator → GroqLLMService (system
    prompt = personas.py 渲染的角色卡) → AzureTTSService → transport.output() →
    assistant_aggregator`，VAD 用 Silero，接在 `LLMContextAggregatorPair` 的
    `user_params` 里。学习者点"结束演练"时，前端发一个自定义 RTVI 消息
    `end_session`（`client.sendClientRequest('end_session', {})`），bot 端的
    `on_client_message` 处理器直接从 `context.get_messages()` 拼 transcript，调
    **原样复用**的 `debrief.run_debrief()` + `db.insert_expressions/words()`，
    再用 `rtvi.send_server_response()` 把诊断结果传回前端渲染——debrief/存库/导出
    完全没被 Pipecat 改动，只是现在从 bot 进程里调用，而不是从 app.py。
  - `run.bat` 现在起两个进程（各自独立命令行窗口，关窗口=停对应服务）。
- **前端**：`web/index.html` 的场景选择/对话气泡/Debrief 卡片/导出面板/退出按钮全部保留，
  只是录音播放那块换成了 `client/` 下的 Vite 项目构建出的 `web/pipecat/voice-client.js`
  （封装 `@pipecat-ai/client-js` + `@pipecat-ai/small-webrtc-transport`，暴露
  `window.LangPracticeVoice.VoiceSession`）。**构建产物直接提交进 git**（`client/node_modules/`
  才 gitignore），改了 `client/src/voice-client.js` 才需要在 `client/` 下 `npm run build`
  重新生成，日常跑 `run.bat` 不需要装 npm 依赖或跑构建。
- 用 claude-in-chrome 验证过：页面加载、`window.LangPracticeVoice.VoiceSession` 正确挂载、
  两个服务器的路由都能访问、`export`/`shutdown` 等非语音功能不受影响。**麦克风授权这一步
  卡在浏览器自动化里过不去**（见下面实现踩坑记录），实际的语音对话/打断/Debrief 触发
  需要你自己在真实浏览器里点一遍确认。
- **口语侧诱导（二期旗舰功能）+ 掌握度更新算法都已实现**：`langpractice/induction.py`。
  - `run_bot()` 开场前按 `card.language`（不限场景）查 `expressions`/`words` 两张表，按
    `(mastery, last_practiced)` 升序取最多 2 条旧表达/生词（`retrieve_induction_targets`，
    返回 `InductionTarget` 对象，带 id/kind/label），格式化后注入 `personas.py` 的
    `induction_block`（模板本来就留了这个槽位，一期没填）。
  - "结束演练"时，Debrief 之外**另一次独立的非流式复盘调用**
    （`review_induction_usage()`，prompt 见 `prompts/induction_review_prompt.md`）判断
    诱导目标有没有被用上：讲对了 `apply_mastery_updates()` 把 mastery +1，讲错了 -1
    （db.py 里 SQL `MAX(0, ...)` 卡下限），没用上/判断不出来就不动，同时刷新
    `last_practiced`（除了没动的情况）——这样"最久没碰"才会真的轮换，不会同一条卡死。
  - 都用真实 Groq API 验证过（插测试行 → 编两段 transcript，一段用对了一段完全没用 →
    确认 `used_correctly`/`not_used` 判断对了、mastery 真的从 0 变 1 → 删测试行）。
- **历史记录管理页已做完**：`web/history.html`（`GET /history` serve），独立页面，
  跟主练习页不共享 JS，只共享 CSS 变量调色板。`GET /records/{language}` 返回带
  id/mastery/last_practiced 的完整记录（`/export/{language}` 那个是给 langhelper 吃的
  干净格式，特意保持不带这些字段，两个端点分工不同，别混）。删除按钮复用已有的
  `DELETE /expressions/{id}` `DELETE /words/{id}`。主页 h1 旁边加了个"历史记录管理 →"
  链接。用 claude-in-chrome 全链路验证过：插一条测试生词 → 页面上点删除 →
  确认按钮消失且 `/records/fr` 里真的查不到了（不是只有 UI 上看着删了）→ 切语言 tab
  也验证过读数正确。
- **场景卡自动生成已实现**（这个功能一直记在"已推迟的增量想法"里，现在做完了，
  那个小节整个删掉了）：`langpractice/scenario_gen.py::generate_persona_card(llm,
  description, language)`——用户给一段自由中文描述，LLM 按 persona_template.md
  的字段结构填充生成 `PersonaCard`，`key` 自动生成 `custom_` 前缀 + 短 uuid。
  `PersonaCard` 挪到了 `models.py`（原来在 `personas.py`，为了不让 `db.py` 反过来
  import `personas.py` 成环）。
- **场景模型后来又统一简化了一轮（同一天）：不再区分"内置"和"自动生成"**——原来
  `personas.py` 有个硬编码的 `BUILTIN_SCENARIOS` dict，跟 DB 里的自动生成场景是
  两套并行逻辑，`get_scenario()`/`list_all_scenario_descriptions()` 得两边分别查、
  合并结果。用户明确说不需要这个区分，于是：
  - 原来两个内置场景（`clinic_fr`/`interview_en`）变成 `seed_scenarios.py` 里的
    纯数据（`SEED_SCENARIOS: list[PersonaCard]`），`db.connect()` 在 `scenarios`
    表**首次为空**时插进去（`_seed_scenarios_if_empty()`），插完就是普通行——
    跟场景管理页里删/查其它场景没有任何区别，包括**能被删掉**（没有特殊保护，
    因为用户要的就是不做区分）。判断"首次为空"而不是常驻 `INSERT OR IGNORE`，
    是为了不让用户删掉种子场景后、下次启动又被复活。
  - `personas.py` 的 `BUILTIN_SCENARIOS` 整个删掉，`get_scenario()`/
    `list_all_scenario_descriptions()` 简化成直接查 `scenarios` 表，一条路径。
  - **场景管理页已做完**：`web/scenario-manager.html`（`GET /scenario-manager`
    serve），列出所有场景（种子的 + 自动生成的混在一起，没有来源标记），每条能删
    （`DELETE /scenarios/{key}`）。全字段的 `GET /scenarios/full` 是给这个页面用的，
    跟 `GET /scenarios`（下拉框用的 `{key: 描述}` 简化格式）分开，别混。主页头部
    加了"场景管理 →"链接（跟"历史记录管理 →"并排）。
  - `voice_bot.py` 的 `_resolve_scenario()` 改成接收 `conn` 参数而不是自己开连接
    ——之前自己开连接会导致单元测试意外打到真实生产数据库文件，改成外部传入后
    测试可以传 `:memory:`，跟项目里其它接 DB 的函数（`retrieve_induction_targets`
    等）保持同一个模式。
  - 全部用真实 Groq API + claude-in-chrome 在真实运行的 app 上验证过：生成场景、
    场景管理页正确列出（含种子场景，无来源标记）、删除一条种子场景级别的测试数据
    后确认真的从 `/scenarios/full` 里消失、主页场景下拉框仍能正常工作。
- 改动历史看 `git log`，这里不重复维护——已知的非显而易见的坑记在下面「实现踩坑记录」。

## 技术栈

- Python + FastAPI 后端（`langpractice/app.py`），**不再自己跑语音**
- SQLite 存储（唯一真相源）
- **语音编排是 Pipecat**（`langpractice/voice_bot.py`，独立进程）：全双工实时 pipeline，
  VAD 自动断句、支持打断。transport 用 `SmallWebRTCTransport`（本地、不依赖 Daily 云）。
- Groq Whisper (STT，Pipecat 里是 VAD 分段不是逐词流式) + Groq（LLM，见下方踩坑记录）
  + Azure Speech (TTS)——STT/TTS 现在是 Pipecat 自带的 `GroqSTTService`/`AzureTTSService`，
  我们自己手写的 `stt/` `tts/` 包已经删掉；`llm/groq_client.py` 的 `GroqLLMClient` 还在用，
  但只用于 Debrief 那一次性非流式调用，跟 Pipecat 的语音 pipeline 是两条独立路径。
- 前端 `web/index.html` + `client/`（Vite，构建出 `web/pipecat/voice-client.js`）；
  `/docs` 的 Swagger UI 还留着方便测 `/scenarios` `/export` 这些非语音接口

## 核心约束（违背即破坏产品）

1. **演练中 AI 绝不跳出角色纠错。** 角色扮演和纠错是两个完全独立的调用/模式。
   演练时只演角色；纠错只在用户发出"结束"信号后的 Debrief 阶段发生。

2. **口语诱导的旧表达必须作为隐藏目标注入角色卡**，让 AI 设计语境自然引导用户说出来，
   **绝不能明着提示或考问**。明示会同时毁掉沉浸感和诱导效果。已实现，见
   `langpractice/induction.py`。

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

- **Pipecat runner 的 `/start` 接口，自定义数据必须包在 `"body"` 键里，不能跟
  `transport`/`createDailyRoom` 平级**：源码见 `pipecat/runner/run.py` 里
  `_setup_unified_start_route` 的 docstring 和 `active_sessions[session_id] =
  request_data.get("body", {})`——顶层塞别的字段会被直接丢弃，`runner_args.body`
  永远拿不到。真实症状：场景切换在 UI 上看着选了，但 bot 端 `_resolve_scenario()`
  永远落到默认值 `clinic_fr`，因为 `client/src/voice-client.js` 一开始把 `scenario`
  塞在 `requestData` 顶层。现在 `connect()` 里是 `requestData: {..., body: { scenario
  } }`。以后往 `/start` 塞任何自定义字段，记得套一层 `body`。
- **`GroqSTTService` 不传 `language` 会把法语"翻译"成英文，而不是转写原文**：真人测试
  时发现——说法语，回来的文字是英文，导致角色扮演里答非所问（被当成怪回答，不是被"纠错"，
  演练铁律没破，但体验很怪）。Whisper 系模型在没有语言提示、音频短/不确定时，有时会走
  "translate to English" 而不是"transcribe in source language"这条路，这是已知行为，
  不是我们代码的 bug，但必须显式传 `language=` 堵掉。已在 `voice_bot.py` 里按
  `card.language` 传 `pipecat.transcriptions.language.Language.FR`/`.EN`。
  以后加新场景语言，记得在 `_STT_LANGUAGE_BY_CODE` 里补一条，别指望自动检测。
- **Groq 的模型列表会变**：`llama-3.3-70b-versatile` 已经从当前账号的可用模型里下架，
  现在默认用 `openai/gpt-oss-120b`（注意：这是 OpenAI 开源的开放权重模型，Groq 自己
  托管在它的硬件上跑，走的是 `GROQ_API_KEY` 和 Groq 的 endpoint，**不是在调 OpenAI 的
  API**，命名里的 `openai/` 只是 Groq 标注权重来源的前缀，跟 Meta 的 `llama-*`、阿里的
  `qwen/*` 是一个套路）。以后再 404，先用 `client.models.list()` 查当前账号实际有什么，
  别死记模型名。默认值在 `config.py` 的 `GROQ_MODEL` / `GROQ_WHISPER_MODEL`，`.env` 可覆盖。
- **LLM 生成的 `*叹气*` 这类舞台指示不能直接喂给 TTS**：Azure 会把星号原样念出来
  （"Asterisk soupire Asterisk"）。旧的 REST 语音层是在 `tts_text.py::strip_for_speech()`
  里对完整文本做正则剥离，但 Pipecat 的 TTS 是流式接住 LLM 输出、没有"发去 TTS 前的完整
  文本"这个钩子——`tts_text.py` 已删除。现在的做法是在 `voice_bot.py` 的
  `GroqLLMService.Settings(system_instruction=...)` 后面拼一段 `_VOICE_ONLY_SUFFIX`，
  明确告诉模型"你的话会被朗读，别用星号舞台指示"。没在自动化里验证这个提示词是否总是
  管用（要真人测），如果发现还是漏，下一步是写个 FrameProcessor 插在 `llm` 和 `tts` 之间
  做文本过滤，不要退回手动整句处理的老路。
- **Azure Speech F0（免费档）TTS 硬限制 20 次请求/60 秒，不可调**（微软官方文档，
  https://learn.microsoft.com/azure/ai-services/speech-service/speech-services-quotas-and-limits）。
  这个限制本身没变，但我们自己手写的 429 重试代码（`AzureTTSClient`）已经随旧 REST 语音层
  删掉了——现在 TTS 走的是 Pipecat 的 `AzureTTSService`，429 出现时得看 Pipecat 自己的重试/
  错误处理行为，还没专门验证过。真撞上了先查 Pipecat 这块的行为，别凭空猜。
- **Groq 免费档也会 429**：各模型有各自的 RPM/RPD/TPM 上限，实际数字会变，账号真实限额去
  `console.groq.com/settings/limits` 查，别死记数字。`langpractice/llm/groq_client.py`
  的 `GroqLLMClient`（Debrief 用）构造函数里把 SDK 默认的 `max_retries` 从 2 调到了 5；
  Pipecat 的 `GroqSTTService`/`GroqLLMService`（语音 pipeline 用）走的是 Pipecat 自己的
  重试逻辑，没有额外调过参数。
- **Pipecat 版本快、API 会变，遇到不确定的用法别凭记忆猜，用 `pipecat init` 现场生成一个
  参考项目**：`pipecat.exe init --name ref -t smallwebrtc -m cascade --stt groq_stt
  --llm groq_llm --tts azure_tts --client-framework vanilla --client-server vite
  --no-deploy-to-cloud`（跑在装了 `pipecat-ai[cli]` 的 venv 里）。这次就是靠这个才搞清楚
  `PipelineWorker`/`WorkerRunner`（不是 doc 里较老的 `PipelineTask`/`PipelineRunner`）、
  VAD 挂在 `LLMContextAggregatorPair` 的 `user_params` 而不是单独的 processor、
  `GroqLLMService.Settings(system_instruction=...)` 而不是塞 context 消息、以及
  `client.sendClientRequest(type, data)` ↔ 服务端 `on_client_message` +
  `rtvi.send_server_response()` 这套自定义消息往返的确切用法。CLI 在 Windows 控制台下
  first-run 会因为 GBK 编码画勾字符崩掉，加 `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` 前缀
  就好——这跟本文件其它地方提过的 Windows 控制台编码问题是同一类坑。
- **Pipecat 的 bot runner 是它自己的独立 FastAPI 服务器**（默认端口 7860，`pipecat.runner.
  run.main()` 起的），不会自动并进你现有的 FastAPI app。这个项目就是两个进程
  （`app.py` 端口 8000 管页面，`voice_bot.py` 端口 7860 管语音），`run.bat` 分别起。
  别想着"想办法揉成一个进程"去折腾，这是框架的标准形态。
- **Pipecat 客户端（`@pipecat-ai/client-js` + `@pipecat-ai/small-webrtc-transport`）
  没有免构建的 CDN 用法**，官方文档也没给，实测确认必须过 npm + Vite 构建
  （`client/` 下 `npm install && npm run build`，`vite.config.js` 用 `build.lib`
  配置输出成单个固定文件名 `web/pipecat/voice-client.js`，不然默认会输出带 hash 的
  多个 chunk 文件不好引用）。构建产物直接提交进 git，用户日常跑 `run.bat` 不需要装 Node。
- **浏览器自动化（claude-in-chrome）过不了麦克风权限弹窗，也过不了 Clipboard
  写入权限弹窗**：脚本触发的 `getUserMedia()`/`navigator.clipboard.writeText()`
  没有真实 user gesture，Chrome 会弹原生权限对话框卡住整个自动化会话（截图/JS 执行
  全部超时），没有人能点"允许"。表现是卡在某个中间状态不再前进（比如"Initializing
  devices..."之后没日志了），服务端日志里完全没收到后续请求——这是判断"卡在权限弹窗"
  还是"代码真的有 bug"的关键区分方法：查对应服务的日志有没有收到预期请求。遇到这类
  功能，验证到"页面加载正常、JS 挂载正常、非权限部分的接口都能调通"就是自动化能做到的
  上限，语音/剪贴板这类需要真实用户手势的部分交给用户自己点一下确认，不要在自动化里
  反复重试。

## 开发流程约定

- 动手写代码前，先确认改动符合 SPEC 和本文件约束。
- 涉及导出格式的改动，对照 SPEC"导出格式契约"逐字段核对。
- 不确定时先问，不要自作主张扩大范围。
