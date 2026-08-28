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
- **纠错部分纯文字**，不走语音

### 3. 记忆与诱导（Memory & Induction）

- **文字侧诱导：整块交给 langhelper。** 不在 agent 里实现造句/翻译诱导
  - langhelper 的单词卡高阶 = 诱导你用目标词翻译
  - langhelper 的病句卡高阶 = 生成同类错误句针对练习
- **口语侧诱导（agent 独有，二期）：** 新语音场景开始前，从 agent 自己的 SQLite 检索
  1~2 条旧表达，作为**隐藏目标**注入角色卡，让 AI 设计语境引导使用。
  - 检索条件放宽：**不限定场景**，只按 `语言 + 掌握度 + 最后练习时间`
  - 这是 langhelper 永远给不了的能力（文字插件无法在你张嘴说法语时埋钩子）

### 4. 导出（Anki Export）— 对齐 langhelper

- 按语言分文件导出（语言不写进内容，由 langhelper 导入对话框选择）
- 病句 → JSON 数组；生词 → 纯文本每行一词
- 详见"导出格式契约"

---

## 分工总表

| 活学能力 | 谁做 |
|---------|------|
| 口语实时演练 + 应变 | **Agent 独有** |
| 演练中埋钩子诱导旧表达（口语） | **Agent 独有**（二期） |
| 萃取病句四要素 + 回推 zh 题面 | **Agent 的 Debrief** |
| 病句低阶还原练习 | langhelper（离线零成本） |
| 病句高阶同类错误诱导 | langhelper（sentence_high prompt） |
| 生词认句 / 翻译诱导 | langhelper（word_gen / word_translate prompt） |
| 抗遗忘硬刷 | Anki |

---

## Debrief 输出 Schema（agent 内部存 SQLite）

每条病句记录：

```json
{
  "language": "fr",         // 内部检索用（口语诱导），导出时剥离
  "zh": "...",              // 中文原意/题面 —— Debrief 需回推学习者的表达意图
  "en_wrong": "...",        // 学习者原句（通用槽位名，法语也用此字段，勿被 en 前缀误导）
  "en_correct": "...",      // 地道修正
  "error_note": "...",      // 思维错误分析（中文）
  "pattern": "...",         // 错误类型标签
  "mastery": 0,             // agent 自己的口语掌握度
  "last_practiced": "..."   // ISO 时间，口语诱导检索用
}
```

每条生词记录：

```json
{
  "language": "fr",
  "word": "...",            // 目标词（外语）
  "meaning": "...",         // 中文词义（可空）
  "mastery": 0,
  "last_practiced": "..."
}
```

**关键点 `zh` 的来源：** 语音演练里学习者说的是外语（可能说错），没有现成中文原句。
Debrief 必须**回推学习者想表达的意思，写成中文 zh**，否则 langhelper 病句卡低阶（显示 zh 让你还原外语）没有题面。

---

## 导出格式契约（langhelper 导入器已验证）

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

### 导入流程（人工步骤，记录备查）

1. Agent 生成分语言文件
2. 在 Anki 里用 langhelper 的"Import Chinglish sentences" / "Batch add words"
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

---

## 分期计划

**一期（使用优先，先跑通）**
- 文字版核心闭环：角色卡对话 → "结束" → Debrief → 存 SQLite → 导出 langhelper 格式
- 语音层：Pipecat 全双工实时语音（Groq STT/LLM + Azure TTS，VAD 自动断句、可打断）
- 演练/Debrief 双模式严格分离——全双工只变语音怎么传，纠错时机铁律不受影响

**二期**
- 口语侧诱导：新场景前检索旧表达注入角色卡隐藏目标
- 掌握度双向同步（若需要，AnkiConnect）
- 更多场景角色卡

## 非目标（明确不做）

- 不实现文字侧造句/翻译诱导（langhelper 已有）
- 不实现病句同类错误生成（langhelper sentence_high 已有）
- 不直接操作 Anki 数据库
