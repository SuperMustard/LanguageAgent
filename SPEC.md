# SPEC — 语言口语演练 Agent

## 一句话定位

一个语音口语演练 agent，负责**文字聊天做不到的活学场景**（实时应变、发音、语速），
把演练中萃取的病句和生词，导出成 Anki 插件 **langhelper** 吃得进的格式，由 Anki 侧负责抗遗忘和文字诱导。

分工原则：**Agent 负责口语活学演练 → langhelper 负责文字诱导复习 → Anki 负责抗遗忘。**

---

## 使用者背景

- 母语中文，练习目标语言：**英语 (en)** 和 **法语 (fr)**
- 典型场景：法语诊所应对情绪不佳的客人、英语工作面试等
- 法语需要细腻表达：vouvoiement（敬语）、诊所同理心话术

---

## 四大模块（收敛后）

原始设想有四个模块，但因为下游已有 langhelper，其中"文字侧诱导"和"造句"整块交给 langhelper，
agent 实际收敛为三件事 + 一个二期增量。

### 1. 真实情境模拟与对话（Simulation Mode）— agent 独有核心

- 多场景角色扮演：按给定情境精准扮演角色，保持真实人设多轮对话
- 语音对讲：STT/TTS，用口语对答，训练发音、语速、应变
- **全双工实时对话**（用 Pipecat 编排）：VAD 自动判断"说完了"，不用手动点录音按钮；
  支持打断（学习者插话时 AI 的语音回复可以被切断）——更接近真实对话的应变训练，
  也更沉浸（演练时不用分心操作 UI）
- **铁律：演练中 AI 绝不跳出角色纠错。** 纠错只在 Debrief 阶段发生。
  这条铁律跟全双工与否无关——全双工只改变"怎么把话传进传出"，不改变"演练时绝不纠错"

### 2. 对话总结与反馈诊断（Debrief & Feedback）— agent 核心

- 演练结束（显式信号）后，单独一次调用分析整场表现
- 产出病句四要素 + 中文题面（见 Debrief Schema）
- 产出需要记忆的生词
- **产出专业应对话术推荐**（见模块 2.5）——同一次 Debrief 调用一并产出，不额外多调一次
- **纠错部分纯文字**，不走语音

### 2.5 专业应对话术推荐（Professional Phrase Recommendation）— agent 核心

这是学习素材的**第三类**（并列于病句、生词），也是使用者最看重的能力：**用专业方式
处理难缠客户**（诊所/按摩治疗环境里情绪化、不满、不配合的客人）。

- **时机**：演练后，并入 Debrief 那一次调用产出（不新增调用）
- **不是散装客套话，而是有骨架的专业应对**。推荐按专业维度组织：
  - `同理承接`（先接住情绪，不急着辩解/解决）
  - `设立边界`（专业地坚持原则/流程/安全，不失礼也不一味顺从）
  - `降级冲突`（对方升温时往下缓和，而非对着来）
  - `重定向解决`（情绪接住后把对话引回"我们能怎么帮你"）
  - 法语额外维度：`vouvoiement 敬语`在冲突降级里的得体运用
- **锚定 transcript**：优先针对学习者在这场演练里**实际遇到的刁难、应对得不够专业**的地方，
  给更专业的说法——而不是凭空罗列场景话术。这也是为什么放在演练后：有真实应对可复盘。
- **防重复**：产出前把**已在库的话术清单**传进 prompt，要求避开（语义去重）；数据库层面
  另有字面去重（见下）。已掌握/最近推过的不再推。
- **进入现有诱导+掌握度循环**：推荐的话术存进新表 `pro_phrases`，初始 mastery=0，之后由
  `induction.py` 当隐藏目标注入未来演练，引导学习者自然用出专业应对；用对了 +1、用错 -1、
  掌握了不再推——**"防止重复推荐"因此几乎白送**，不必另写判重逻辑。
- **导出：已定义契约，走「表达块卡」。** 见"导出格式契约 → 表达块卡"。langhelper 早先只支持
  病句卡/单词卡，专业话术是整句、塞进单词卡会错配（单词卡的例句/翻译诱导玩法对整句话术不合适），
  当时因此暂缓。现在新增第三种卡型**「表达块卡」**专收整块搭配/整句表达，话术导出的错配前提消失，
  接一根导出管道即可。`pro_phrases` 表字段（`phrase` / `meaning` / `usage_note` / `language`）
  早已**为导出预留**，正好兑现"不用回头给老数据补字段"。
- **抗遗忘由单轨变双轨**：话术原先只靠 agent 口语诱导（在真实对话语境里被引导用出来）——那是被
  langhelper 不支持话术卡**逼出来的妥协**，非主动选择（字段都预留了，本就想导出）。现在话术走
  **agent 口语诱导 + langhelper 文字刷卡**双轨，与生词/病句一致。两个 mastery（口语侧 agent 管、
  文字侧 Anki 管）沿用"一期不双向同步"原则，无需改动；只需知道话术现在也有**文字侧 mastery**，
  别把两个掌握度搞混。口语侧诱导仍是 langhelper 给不了的能力（文字插件无法在你张嘴说法语时埋钩子），
  双轨是互补而非替代。

### 3. 记忆与诱导（Memory & Induction）

- **文字侧诱导：整块交给 langhelper。** 不在 agent 里实现造句/翻译诱导
  - langhelper 的单词卡高阶 = 诱导你用目标词翻译
  - langhelper 的病句卡高阶 = 生成同类错误句针对练习
  - langhelper 的表达块卡高阶 = 语境召唤（情境应对召唤 / 搭配填空，见导出契约）
- **口语侧诱导（agent 独有，二期）：✅ 已实现（2026-08）** 新语音场景开始前，从 agent
  自己的 SQLite 检索 1~2 条旧表达，作为**隐藏目标**注入角色卡，让 AI 设计语境引导使用。
  见 `langpractice/induction.py` + `voice_bot.py` 的 `run_bot()`。
  - 检索条件：`语言 + 掌握度 + 最后练习时间`（按 mastery 升序、last_practiced 升序取前
    N 条）
  - **不限定场景**：只按语言检索，跟当前选的场景无关
  - **诱导素材有三个来源**：`expressions`（病句）、`words`（生词）、`pro_phrases`（专业话术，
    新增）。三类混合时用**保底 + 上限**配比（config，见"配置项"）：保证专业话术有配额、
    不被生词淹没，因为它是使用者最想练的。别让某一类挤掉其它类。
  - **注意与输入侧 collocation 的边界**：由外部输入侧管线（非 agent 演练）灌入的 collocation
    走「表达块卡」进 langhelper 文字侧复习，**一期不进 agent 的口语诱导循环**——它们没有口语
    mastery 历史，且量可能很大，直接混入会淹掉精心设计的 pro_phrases 配额。若二期要让其参与
    口语诱导，另立来源或单独配额，别塞进现有三来源的保底+上限里。
  - **掌握度更新算法：✅ 已实现（2026-08）**。演练结束时除了 Debrief，还有一次独立的
    非流式复盘调用（`induction.review_induction_usage()`，prompt 见
    `prompts/induction_review_prompt.md`），判断这场诱导目标有没有被用上：
    讲对了 mastery +1，讲错了 mastery -1（下限 0），没用上不动（保持"最久没碰"排前面，
    下次继续诱导）。用真实 Groq API 验证过：正确区分"用对了"和"完全没用到"两种情况。
  - 这是 langhelper 永远给不了的能力（文字插件无法在你张嘴说法语时埋钩子）

### 4. 导出（Anki Export）— 对齐 langhelper

- 按语言分文件导出（语言不写进内容，由 langhelper 导入对话框选择）
- 病句 → JSON 数组；生词 → 纯文本每行一词；表达块（话术 / collocation）→ JSON 数组
- 详见"导出格式契约"

---

## 分工总表

| 活学能力                         | 谁做                                                                         |
| -------------------------------- | ---------------------------------------------------------------------------- |
| 口语实时演练 + 应变              | **Agent 独有**                                                               |
| 演练中埋钩子诱导旧表达（口语）   | **Agent 独有**（二期，✅ 已实现）                                            |
| 萃取病句四要素 + 回推 zh 题面    | **Agent 的 Debrief**                                                         |
| 推荐专业应对话术（处理难缠客户） | **Agent 的 Debrief**（存 `pro_phrases`，进口语诱导循环，并导出「表达块卡」） |
| 病句低阶还原练习                 | langhelper（离线零成本）                                                     |
| 病句高阶同类错误诱导             | langhelper（sentence_high prompt）                                           |
| 生词认句 / 翻译诱导              | langhelper（word_gen / word_translate prompt）                               |
| 话术 / collocation 文字侧诱导    | langhelper（表达块卡：情境应对召唤 / 搭配填空）                              |
| 抗遗忘硬刷                       | Anki                                                                         |

---

## Debrief 输出 Schema（agent 内部存 SQLite）

每条病句记录：

```json
{
  "language": "fr", // 内部检索用（口语诱导），导出时剥离
  "zh": "...", // 中文原意/题面 —— Debrief 需回推学习者的表达意图
  "en_wrong": "...", // 学习者原句（通用槽位名，法语也用此字段，勿被 en 前缀误导）
  "en_correct": "...", // 地道修正
  "error_note": "...", // 思维错误分析（中文）
  "pattern": "...", // 错误类型标签
  "mastery": 0, // agent 自己的口语掌握度
  "last_practiced": "..." // ISO 时间，口语诱导检索用
}
```

每条生词记录：

```json
{
  "language": "fr",
  "word": "...", // 目标词（外语）
  "meaning": "...", // 中文词义（可空）
  "mastery": 0,
  "last_practiced": "..."
}
```

每条专业话术记录（新表 `pro_phrases`）：

```json
{
  "language": "fr",
  "scenario_type": "...", // 场景类别（诊所/面试…），专业话术常场景绑定；导出剥离
  "phrase": "...", // 话术本身（目标语）—— 导出的正面
  "meaning": "...", // 中文意思 —— 导出的背面
  "dimension": "...", // 专业维度：同理承接/设立边界/降级冲突/重定向解决/vouvoiement；导出剥离
  "usage_note": "...", // 何时用、为何专业（中文）—— 导出降级进 note
  "mastery": 0,
  "last_practiced": "..."
}
```

`phrase` / `meaning` / `usage_note` / `language` 字段用于**导出「表达块卡」**（见导出契约）。
`scenario_type` / `dimension` / `mastery` / `last_practiced` 是 agent 内部字段（诱导循环与检索用），
**导出时剥离**。

**Debrief 一次调用的完整输出**是 `{sentences: [...], words: [...], pro_phrases: [...]}`
三部分，分别落 `expressions` / `words` / `pro_phrases` 三张表。

**关键点 `zh` 的来源：** 语音演练里学习者说的是外语（可能说错），没有现成中文原句。
Debrief 必须**回推学习者想表达的意思，写成中文 zh**，否则 langhelper 病句卡低阶（显示 zh 让你还原外语）没有题面。

---

## 导出格式契约（langhelper 导入器已验证）

三种卡型：病句卡（JSON）、生词卡（txt）、表达块卡（JSON）。三者都按语言分文件、
language 不写进内容、导出时剥离所有内部字段、纯净输出不带代码围栏。

### 病句卡 → JSON（parse_sentences 首选路径）

按语言分文件，如 `fr_sentences.json` / `en_sentences.json`。
每份是一个数组，元素**只含这五个字段**（剥离 language / mastery / last_practiced）：

```json
[
  {
    "zh": "中文题面",
    "en_wrong": "原句",
    "en_correct": "地道修正",
    "error_note": "思维错误分析",
    "pattern": "错误类型"
  }
]
```

约束：

- 每条至少要有 `zh` 或 `en_wrong` 才会被 langhelper 收录 —— 稳妥起见两者都给
- 不要带 ```json 代码块围栏（langhelper 能容忍，但干净为好）
- language 字段不写进 JSON（langhelper 只认那五个字段，多余字段被忽略）

### 生词卡 → 纯文本（parse_words）

按语言分文件，如 `fr_words.txt` / `en_words.txt`。
每行一个词，格式 `词|中文义`，义可省略：

```
resilient|有韧性的
vouvoiement|敬语（用 vous 称呼）
empathie
```

约束：

- langhelper 会自动大小写不敏感去重
- 不是 JSON，就是纯文本

### 表达块卡 → JSON（parse_phrases）

按语言分文件，如 `fr_phrases.json` / `en_phrases.json`。
每份是一个数组，元素**只含这三个字段**（剥离 language / dimension / scenario_type /
mastery / last_practiced 等所有内部字段）：

```json
[
  {
    "phrase": "地道表达块本身（目标语）",
    "meaning": "中文意思",
    "note": "用法提示（中文，自由文本，可空）"
  }
]
```

**卡型语义**：装"一个地道的目标语表达块 + 中文意思 + 用法提示"。并列于病句卡（你说错了→怎么改）
和生词卡（这个词什么意思）之外的**第三种卡型**，专收**整块搭配 / 整句表达**——即病句卡的五字段
（需要 en_wrong）和生词卡的单词粒度都错配的那类对象。

**两类上游来源，共用此卡型（卡型共享，来源 schema 不共享）：**

- **专业应对话术**（agent `pro_phrases` 表）：`phrase` = 话术整句，`meaning` = 中文意思，
  `note` = 由 `usage_note` 降级而来的"何时用、为何专业"。`dimension`（同理承接/设立边界/
  降级冲突/重定向解决/vouvoiement）与 `scenario_type` **不进卡**，导出时剥离——它们只在
  agent 诱导循环里用。
- **别人的 collocation**（输入侧管线，非 agent 演练萃取）：`phrase` = 地道搭配，
  `meaning` = 中文意思，`note` = 语境说明（有 podcast/文章主题就带一句，是日常搭配就写日常
  用法，无则留空）。无 `dimension`、无 `scenario_type`、无口语 mastery。

场景/维度这类"有时有、有时没有"的信息**一律降级进自由文本 `note`**，不做结构化字段——
避免用一张 schema 硬套两种来源导致字段填不满。区分留在上游各自的表里（pro_phrases 要参与
agent 诱导、要按维度组织；collocation 不用），langhelper 导入器**不区分来源**，只看到一串
"表达块卡"。

**约束：**

- 每条至少要有 `phrase` 才会被 langhelper 收录 —— `phrase` 是卡片正面，不可空
- `meaning` 建议给（作背面）；`note` 可省略（自由文本槽，容纳"有时有场景、有时没有"的参差）
- language 字段不写进 JSON（langhelper 只认这三个字段，多余字段被忽略）
- 不要带 ```json 代码块围栏（沿用病句卡约束）
- langhelper 侧按 `phrase` 大小写不敏感去重（沿用生词卡去重惯例；话术与 collocation 若产出
  同一 `phrase`，字面去重即可，避免同块表达两条卡）

**诱导玩法（langhelper 侧，高阶）**：属"语境召唤"大类（优于翻译诱导、不适用造错句）。
因上游两类对象的最佳诱导略有分叉，做成同一诱导的两个变体，按 `note` 是否含场景信息切换：

- 含场景（多为话术）→ **情境应对召唤**：给使用场景/半句语境，诱导补出整句地道应对
- 无场景（多为 collocation）→ **搭配填空**：给句子挖空该搭配，诱导填出地道词组

玩法可迭代，先打通卡型与导出即可（参照 langhelper 现有 sentence_high / word_gen /
word_translate 分玩法先例）。

### 导入流程（人工步骤，记录备查）

1. Agent（或输入侧管线）生成分语言文件（`{lang}_sentences.json` / `{lang}_words.txt` /
   `{lang}_phrases.json`）
2. 在 Anki 里用 langhelper 的对应导入入口：
   - 病句 → "Import Chinglish sentences"
   - 生词 → "Batch add words"
   - 表达块 → "Import phrases"（待 langhelper 新增该入口）
3. 对话框里**选对应语言**（en / fr），粘贴对应文件内容
4. 选择/确认 deck，导入

---

## 技术栈

- **后端**：Python + FastAPI
- **语音编排**：Pipecat——把 STT/LLM/TTS 接成一条全双工实时 pipeline（VAD 断句、
  支持打断），transport 用 `SmallWebRTCTransport`（不依赖 Daily 云服务，适合本地单人场景）
- **LLM（角色扮演）**：Groq（当前用 `openai/gpt-oss-120b`，Groq 自己托管的开放权重模型，
  见 CLAUDE.md 实现踩坑记录）；**法语地道度务必持续关注**
  （vouvoiement、诊所同理心话术若撑不住，角色扮演层可换 Mistral/Claude/GPT，STT 仍留 Groq）
- **STT**：Groq Whisper（法语英语都强、快、便宜；Pipecat 的 `GroqSTTService` 是 VAD 分段，
  不是逐词流式，说完一段才转文字，符合 Whisper 本身的限制）
- **TTS**：Azure Speech（即 Edge-TTS 的正牌合规版，法语声音一致）
- **存储**：SQLite（agent 的唯一真相源）
- **前端**：最薄单页 —— 场景选择、Pipecat client（`@pipecat-ai/client-js` +
  `@pipecat-ai/small-webrtc-transport`）接管录音/放音、对话气泡、Debrief 卡片、
  导出面板、"结束"按钮

## 存储架构原则

- **Agent 的 SQLite 是唯一真相源**，Anki 是下游消费者
- **不直接读写 Anki 的 collection.anki2**（schema 不稳、有并发锁、数据散在卡片字段里）
- 数据流单向：agent SQLite → 导出文件 → langhelper 导入 → Anki
- **掌握度一期不双向同步**：口语掌握度 agent 自己管，文字掌握度 Anki 自己管
  （两种能力本就不同，分开 track 反而合理）。真要同步，二期用 AnkiConnect，不碰底层文件
- **话术双轨提醒**：`pro_phrases` 现在有两个 mastery——口语侧（agent 诱导循环）与文字侧
  （导出成表达块卡后由 Anki 管）。沿用"一期不双向同步"，两者各管各的，别混。

---

## 难缠客户练习与配置分层

专业话术推荐（模块 2.5）要有素材，前提是**演练里角色真的会难缠**。难缠相关的参数按
**变化频率**分三层，别压成一个笼统 config：

- **本次难缠程度**（每场演练临场选）：温和 / 中等 / 难缠 / 极难缠。前端每次开练时选，
  通过 Pipecat `/start` 的 `body`（见 CLAUDE.md 踩坑记录：自定义字段必须套 `body`）传给 bot。
- **场景默认难缠程度**（每个场景一个默认）：存 `scenarios` 表，前端不选就用它。
- **难缠红线（满级上限）**：**写死为常量**，不做配置。它是产品铁律不是旋钮——
  即使选"极难缠"，角色也不能突破"仍可被专业方式化解"的边界（不无理取闹到对话崩溃、
  不人身攻击、始终留有专业应对的空间）。红线和旋钮是两回事：旋钮转到底也不能越过这堵墙。

### 配置项（`config.py`，可被 `.env` 覆盖，沿用 GROQ_MODEL 那套）

- `INDUCTION_MAX_TARGETS`：一次诱导注入的目标总数上限（现有 N 条的那个值）
- `INDUCTION_MIN_PHRASES`：其中**保底**来自 `pro_phrases` 的条数（若库里有未掌握的话术）。
  这保证专业话术不被病句/生词淹没。先用简单的"保底 + 上限"，不够再细化按类权重。

---

## 分期计划

**一期（使用优先，先跑通）**

- 文字版核心闭环：角色卡对话 → "结束" → Debrief → 存 SQLite → 导出 langhelper 格式
- 语音层：Pipecat 全双工实时语音（Groq STT/LLM + Azure TTS，VAD 自动断句、可打断）
- 演练/Debrief 双模式严格分离——全双工只变语音怎么传，纠错时机铁律不受影响

**二期**

- 口语侧诱导：新场景前检索旧表达注入角色卡隐藏目标 ✅ 已实现
- 掌握度更新算法：演练结束后复盘诱导目标有没有用上，更新 mastery ✅ 已实现
- 专业应对话术推荐（模块 2.5）：Debrief 产出 → `pro_phrases` 表 → 进口语诱导循环；
  配套"难缠程度"角色卡维度
- **表达块卡导出（新增）**：langhelper 新增第三种卡型「表达块卡」+ "Import phrases" 入口；
  接通 `pro_phrases` → `{lang}_phrases.json` 导出管道；输入侧 collocation 复用同一卡型格式
- 掌握度双向同步（若需要，AnkiConnect）
- 更多场景角色卡

**输入侧管线（并行，非本 agent 内建）**

- 独立的英语输入侧管线（LingQ/podcast/文章 → 提取 collocation → 导出表达块卡 → langhelper）
  与本 agent 是**两条并行管线，共享 langhelper/Anki 终点与「表达块卡」格式**，不在 agent 内实现。
  一期两条独立跑；collocation 是否进 agent 口语诱导循环留待二期评估（见模块 3 边界说明）。

## 非目标（明确不做）

- 不实现文字侧造句/翻译诱导（langhelper 已有）
- 不实现病句同类错误生成（langhelper sentence_high 已有）
- 不直接操作 Anki 数据库
- 不在 agent 内实现输入侧 collocation 采集管线（那是并行的独立管线，只共享导出格式与 Anki 终点）
- 一期不让外部 collocation 进 agent 口语诱导循环（无口语 mastery 历史、量大易淹没 pro_phrases 配额）
