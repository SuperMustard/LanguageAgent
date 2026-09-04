# 精听提炼分诊+提炼 Prompt

模块 4（精听提炼）第 2 步。只处理句表 CSV 里人工三选一标了"语言"的句子——即"有不熟的词或
搭配"的那些，不含"语音"（认识但没听出来，走 phonetic_notes）和"跳过"的句子。一次调用可
批量传入多句，按 `index` 对应回原句。已用真实 Groq API 验证（`openai/gpt-oss-120b`，
2026-09-02，两轮测试后质量达到自用标准，见 SPEC.md「精听分诊+提炼 Prompt」的验证记录）。

---

## 模板

```
你在做语言学习素材的精听提炼分诊（{{language_label}}，母语中文的学习者）。下面是若干句子，
每句都是学习者精听时"整句收藏"的——即这句里有他没跟上的东西（词或搭配）。对每一句判断里面
有没有：

1. 生词：学习者大概率不认识的词（不要挑基础常见词，比如 the/door/open/room 这类不算）。
2. 语块 / collocation：几个词组合起来的地道搭配或固定用法（词都认识但组合方式/用法未必知道）。
   只挑**通用、可迁移**的语块（换个句子还能用得上的那种），**不要**把这句话里临时的、
   句子特有的描述性短语（比如某个具体名词的修饰语）当成语块硬拎出来。

有些句子可能什么值得学的都没有（全是基础词、无地道搭配）——这种直接返回空数组，不要硬凑。

**两条硬性要求**：
1. **语块要写成词典原形**，不要照抄句子里的屈折形式。动词用原形/动词短语原形（如句子里是
   "curled up"，输出 "curl up"；句子里是 "put it off"，输出 "put off"，代词占位不要带进来；
   句子里是 "emphasized"，输出 "emphasize the importance of"）。句子特有的信息（时态、代词、
   具体宾语）放进 note 字段说明语境，phrase 字段本身要是"换个句子还能直接用"的可迁移形式。
2. **逐个动词短语/固定搭配检查一遍再收尾**，尤其一句话有多个独立语块时，不要找到一两个就停——
   把句子从头到尾过一遍，确认没有漏掉的再输出。

# 句子（按编号处理，输出也按这个编号）
{{sentences}}

# 输出格式
严格输出一个 JSON 对象，不要任何额外文字、不要 markdown 代码块围栏：

{
  "results": [
    {
      "index": 1,
      "words": [{"word": "...", "meaning": "中文"}],
      "collocations": [{"phrase": "...", "meaning": "中文", "note": "中文语境说明，简短，可空"}]
    }
  ]
}

results 数组长度必须等于句子数，index 从 1 开始按顺序对应。
```

---

## 落库说明（给实现参考）

拿到这个 JSON 后，agent 侧（`langpractice/mining.py::run_mining_triage`）：
- 按 `index` 把结果映射回 `mining_sentences` 表里对应的行 id
- 每条 `words` 记录补上 `language`，跟已有 `words.word`（同语言）大小写不敏感去重后插入
  `words` 表（`mastery=0`，`last_practiced=""`——尚未被口语诱导，走"最久没碰"排序天然靠前）
- 每条 `collocations` 记录补上 `language`、`source="mining"`，跟已有 `collocations.phrase`
  （同语言）大小写不敏感去重后插入 `collocations` 表（同样 `mastery=0`，`last_practiced=""`）
- 对应的 `mining_sentences` 行置 `status="done"`
- 单条 `index` 缺失或结果格式不对不影响其它行——那一行的 `mining_sentences.status` 保持
  `"queued"`，可以在下次批量处理时重新提交重试

## 已知残留小瑕疵（SPEC.md 验证记录已收录，不影响"够用"结论）

- 个别可分离短语动词保留了句中的代词（如 `put it off` 没简化成 `put off`），靠 note 区分即可
- 偶尔把语块里的核心名词也单独拆成一条生词（如 `take a toll on` 之外又给了 `toll`），
  跟 collocation 有轻微重复——这条重复入库风险字面去重可能覆盖不了（一个是词一个是短语，
  字面不同），建流水线时留意但不强求根治
- 少数固定被动搭配（如 "be made redundant"）模型倾向于只拆出核心词，边界判断偏保守
