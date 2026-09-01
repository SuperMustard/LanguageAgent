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
description, language)`——用户给一段自由中文描述，LLM 按 persona*template.md
  的字段结构填充生成 `PersonaCard`，`key` 自动生成 `custom*`前缀 + 短 uuid。`PersonaCard`挪到了`models.py`（原来在 `personas.py`，为了不让 `db.py`反过来
import`personas.py` 成环）。
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
- **专业应对话术推荐（模块 2.5）已全部实现，含导出**：学习素材的第三类，灵魂是"用专业方式
  处理难缠客户"（诊所/按摩环境）。完整规格见 SPEC 模块 2.5 + 核心约束 5/6。
  - **并入 Debrief 那一次调用产出**（没新增调用）：输出从 `{sentences, words}` 扩成
    `{sentences, words, pro_phrases}`，分别落三张表（`prompts/debrief_prompt.md`）。
  - **新表 `pro_phrases`**（db.py，操作同构于 expressions/words）：字段见「关键字段名」。
    按专业维度组织（同理承接/设立边界/降级冲突/重定向解决/vouvoiement），**锚定 transcript**
    （针对刚才真实应对的刁难给更专业说法，不凭空罗列）。
  - **复用现有诱导+掌握度引擎**：`induction.py::retrieve_induction_targets` 把 `pro_phrases`
    纳入第三来源，用保底+上限配比（`INDUCTION_MAX_TARGETS`/`INDUCTION_MIN_PHRASES`，
    config.py，`.env` 可覆盖）保证话术有配额、不被生词淹没；防重复因此白送（已掌握/最近
    推过的检索时自然排除），产出前再把已在库话术传进 prompt 做语义去重
    （`debrief.render_debrief_prompt` 的 `existing_phrases` 参数）。
  - **角色卡"难缠程度"字段**：`models.py` 的 `PersonaCard.hostility_level` + `scenarios`
    表存默认（`config.HOSTILITY_LEVELS` 四档，`DEFAULT_HOSTILITY_LEVEL`）+ 前端每次可选，
    经 `/start` 的 `body` 传入（`voice_bot.py::_resolve_hostility_level`）。红线写死在
    `prompts/persona_template.md` 铁律第 4 条，不受这个旋钮影响（对应约束 6）。
  - **导出：已实现**，走「表达块卡」——`export.py::pro_phrases_to_json` 把 `phrase`/`meaning`
    保留、`usage_note` 降级进 `note`，剥离 `dimension`/`scenario_type`/`mastery`/
    `last_practiced`，`GET /export/{language}` 一并写 `{lang}_phrases.json`；langhelper 那边
    的"Import phrases"入口和 `parse_phrases` 尚待对方实现，agent 侧的产出管道已经打通到位
    （对应约束 5，已更新）。
  - history 页 + `/records/{language}` 把 `pro_phrases` 纳入查看/删除。
  - 单元测试：`tests/test_export.py` 覆盖 `pro_phrases_to_json` 的字段裁剪/去重/空输入。
- 改动历史看 `git log`，这里不重复维护——已知的非显而易见的坑记在下面「实现踩坑记录」。

## 技术栈

- Python + FastAPI 后端（`langpractice/app.py`），**不再自己跑语音**
- SQLite 存储（唯一真相源）
- **语音编排是 Pipecat**（`langpractice/voice_bot.py`，独立进程）：全双工实时 pipeline，
  VAD 自动断句、支持打断。transport 用 `SmallWebRTCTransport`（本地、不依赖 Daily 云）。
- Groq Whisper (STT，Pipecat 里是 VAD 分段不是逐词流式) + Groq（LLM，见下方踩坑记录）
  - Azure Speech (TTS)——STT/TTS 现在是 Pipecat 自带的 `GroqSTTService`/`AzureTTSService`，
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

5. **专业话术（`pro_phrases`）导出走独立的「表达块卡」格式，不进病句卡/单词卡通道。**
   langhelper 只有病句卡/单词卡两种卡型时，整句话术塞进单词卡会错配（单词卡的例句/翻译
   诱导玩法对整句话术不合适）；`{lang}_phrases.json` 是第三种卡型专收整块表达，字段只有
   `phrase`/`meaning`/`note`（`usage_note` 降级进 `note`），`dimension`/`scenario_type`/
   `mastery`/`last_practiced` 等内部字段导出时剥离。实现见 `export.py::pro_phrases_to_json`。

6. **难缠红线是铁律，写死为常量，不做配置。** 即使选"极难缠"，角色也不能突破
   "仍可被专业方式化解"的边界（不无理取闹到对话崩溃、不人身攻击、始终留有专业应对空间）。
   这跟"难缠程度"那个可调档位是两回事：档位是旋钮，红线是墙，旋钮转到底也不能越墙。

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

表达块卡 langhelper 字段：`phrase` `meaning` `note`（导出唯一认这三个字段，见「导出格式契约」）

专业话术表 `pro_phrases`：`language` `scenario_type` `phrase` `meaning` `dimension`
（同理承接/设立边界/降级冲突/重定向解决/vouvoiement）`usage_note` `mastery` `last_practiced`
（导出成表达块卡：`phrase`/`meaning` 原样保留，`usage_note` 降级进 `note`；
`scenario_type`/`dimension`/`mastery`/`last_practiced` 是内部字段，导出时剥离）

agent 内部额外字段：`language` `mastery` `last_practiced`（导出病句/生词/话术时剥离，不进 langhelper 文件）

## 多平台演进路线（规划中，尚未动手）

> 这是"未来要做的方向和已想清楚的决策"，不是已完成的东西。动手前照这个顺序走，
> 别一步到位把风险藏到最后才暴露。

### 目标形态

- **客户端：Flutter**（Android 优先）。一套码覆盖 Android/iOS/桌面/Web，复用已有的 Flutter 经验。
  用 `pipecat_flutter` 包（0.2.x）连后端。
- **后端：上云**。理由是需要在非局域网环境（在外面、给身边人临时体验）使用，局域网连接满足不了。
  VPS 用 **Oracle Cloud Always Free ARM**（2026-06 砍半后是 2 OCPU / 12GB，对单人自用够用；免费）。
- **使用场景是单人自用 + 当面递手机给人体验**，不是网络分发。所以：**不做**用户系统、账号、
  登录、计费、每用户 key、数据隔离、自动扩缩容——这些都是"真决定做产品"才碰的。
- **key 策略**：就用运营者（你）自己的 Groq/Azure key，配在 VPS 上。单人量级，账单可控。
  "用户自带 key" 推迟到确认要做面向他人的产品之后再设计。

### 两个头号技术风险（比选 VPS 本身重要得多）

1. **手机↔云的 WebRTC NAT 穿透**：局域网内 WebRTC 好使是因为同网段直连；上云后手机在
   4G/5G 或别人 WiFi 后面、VPS 在数据中心，直连大概率打不通，标准解法是自架 TURN（coturn，
   可跑在同一台 VPS）。**但见下面「传输层」——换 WebSocket 可能直接绕开这个坑。**
2. **Pipecat 及其原生依赖（WebRTC、音频、Silero VAD 等）在 ARM 上能否顺利安装/运行**：
   Oracle 免费档是 ARM（Ampere A1）不是 x86。大部分 Python 没问题，但原生扩展要实测。
   x86 micro 免费实例只有 1GB RAM，跑不动语音管线，所以基本得让 ARM 这条路走通。
   **这个坑换传输/换框架都躲不掉（除非彻底重写），只能实测确认。**

### 框架与传输层的决策

- **框架：继续用 Pipecat，不换 LiveKit。** LiveKit 的强项是大规模生产级媒体（几百上千并发、
  自带成熟 WebRTC 媒体服务器），单人自用用不上；换过去要把已跑通验证过的整套 voice_bot.py
  推倒重写、还要运维更重的媒体服务器，不划算。OpenAI Realtime（锁死单厂商、STT/LLM/TTS 不能
  自由换，丢掉 Groq+Azure 组合）、Vapi 等托管平台（放弃自托管、按量付费）都和"自托管+免费+
  自由换模型"的方向相反，排除。

- **传输层：认真考虑把 `SmallWebRTCTransport` 换成 WebSocket 传输。** Pipecat 的传输是可插拔的
  （Daily / HTTP / WebSocket / 自定义都支持），换传输是改配置层，不用重写 debrief/诱导/场景等
  核心逻辑。WebSocket 走 VPS 公网 IP 直连，**不需要 NAT 打洞、不需要 TURN——直接绕开风险①**。
  代价是延迟比 WebRTC 略高，但本项目是回合制语言练习（你说完它答），不是实时电话，能接受。
  - **待验证**：`pipecat_flutter` 之前查到支持的是 Daily / SmallWebRTC 两种传输。后端若换 WebSocket，
    Flutter 客户端这边能不能直接用 pipecat_flutter、还是要在 Flutter 侧自己接 WebSocket 音频，
    **必须先确认**。这是换传输要付的、尚未验证的代价，不是白换。

### 上云验证顺序（关键：先拆最大风险，再堆功能）

1. **最小链路先行**：在 Oracle ARM VPS 上，只验证「Pipecat 后端能装能跑（拆 ARM 坑）
   - 用 WebSocket 传输让手机从 4G 连通一轮语音（拆穿透坑）」。**这一步先用现有的网页前端**，
     不要急着上 Flutter、不要搬 JSON API、不要搬场景管理。两个最大风险在投入最小时就试出来。
2. **第 1 步通过后**：Flutter Android 客户端 + `app.py` 非语音端点整理成干净 JSON API
   （Flutter 要 JSON 不要 HTML；现有 `/scenarios` `/export` `/records` 本就是 JSON 可复用，
   serve HTML 的 `GET /` / history.html / scenario-manager.html 要用 Dart 重写成界面）+ 全套搬上云。
3. **产品化（只有体验反馈证明有人真要用才走）**：用户系统、每用户 key、数据隔离、计费。

### Oracle 免费档特有注意

- ARM 架构（非 x86）；免费 ARM 容量在热门区域常被抢光（"out of host capacity"），
  注册开机可能要挑区域反复重试；**空闲实例可能被回收**（本项目"偶尔用一下"的模式正好踩这个，
  留意保活）；无 SLA；注册流程比一般 VPS 严（信用卡验证）。
- **安全**：key 会放在公网 VPS 上（比本地电脑暴露面大）。基本措施：key 放环境变量别进 git、
  防火墙只开必要端口、SSH 用密钥登录。

## 实现踩坑记录

> 下面前两条是**专业话术功能的预判坑**（还没写、还没踩，是设计时就知道要防的），
> 其余是已经真实踩过的坑。做话术功能时先看这两条。

- **【预判】三类诱导素材要设配比，否则话术会被淹没**：加了 `pro_phrases` 后诱导池变大
  （病句+生词+话术），如果不设保底，可能连续几次诱导都抽到生词、话术反而挑不到——而话术
  正是使用者最想练的。务必用 `INDUCTION_MIN_PHRASES` 给话术设保底配额，别让某一类挤掉其它。
- **【预判】难缠程度别调到"无法对话"**：强度设太高、角色纯粹无理取闹，学习者没法正常练应对、
  Debrief 也提取不出有效的"专业应对"素材可推荐。角色卡渲染时要给强度设上限（红线，写死为常量，
  见核心约束 6）：难缠但**仍是可以用专业方式化解的真实客户**，不是存心捣乱到对话崩溃。
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
