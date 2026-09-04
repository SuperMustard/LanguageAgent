"""一次性验证脚本（不进流水线，不写库）：测 Groq 在模块 4 第 2 步
（生词 vs 语块分诊 + 提炼）上的输出质量。SPEC 第 559 行：
"落地顺序：先验 Groq 提炼质量，再建流水线"——这就是那一步。

跑法：.venv/Scripts/python scratch_test_mining.py
读 test_sentences.txt 里的 10 句测试句 -> 一次批量调用 Groq -> 打印结构化结果，
供人工对照 test_sentences.txt 里每句的注释（期望语块/生词/陷阱）逐条判断质量。

跑完看输出决定：够用就把这个 prompt 挪进 prompts/mining_extraction_prompt.md 建正式流水线；
不够用就换 prompt 或按 SPEC 退路把这一步换 Haiku。
"""

import json
import re
from pathlib import Path

from langpractice import config
from langpractice.llm.base import Message
from langpractice.llm.groq_client import GroqLLMClient

SENTENCES_PATH = Path(__file__).resolve().parent / "test_sentences.txt"

PROMPT_TEMPLATE = """\
你在做语言学习素材的精听提炼分诊（英语，母语中文的学习者）。下面是若干句子，每句都是学习者
精听时"整句收藏"的——即这句里有他没跟上的东西（词或搭配）。对每一句判断里面有没有：

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
"""


def load_sentences() -> list[str]:
    text = SENTENCES_PATH.read_text(encoding="utf-8")
    # 每个测试句是一行形如: "some sentence text",
    return re.findall(r'^\s*"((?:[^"\\]|\\.)*)",?\s*$', text, re.MULTILINE)


def build_prompt(sentences: list[str]) -> str:
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, start=1))
    return PROMPT_TEMPLATE.replace("{{sentences}}", numbered)


def strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip()


def main() -> None:
    sentences = load_sentences()
    print(f"读到 {len(sentences)} 句测试句\n")
    for i, s in enumerate(sentences, start=1):
        print(f"  {i}. {s}")
    print()

    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY 未设置，检查 .env")

    llm = GroqLLMClient(api_key=config.GROQ_API_KEY, model=config.GROQ_MODEL)
    prompt = build_prompt(sentences)
    raw = llm.chat([Message(role="system", content=prompt)])

    print("=== 原始输出 ===")
    print(raw)
    print()

    payload = json.loads(strip_json_fence(raw))
    results = payload.get("results", [])

    print("=== 解析后结果 ===\n")
    for r in results:
        idx = r.get("index")
        sentence = sentences[idx - 1] if idx and 1 <= idx <= len(sentences) else "?"
        print(f"[{idx}] {sentence}")
        words = r.get("words", [])
        collocations = r.get("collocations", [])
        if not words and not collocations:
            print("    (空 —— 无值得学的内容)")
        for w in words:
            print(f"    生词: {w.get('word')} — {w.get('meaning')}")
        for c in collocations:
            note = c.get("note") or ""
            note_part = f"（{note}）" if note else ""
            print(f"    语块: {c.get('phrase')} — {c.get('meaning')} {note_part}")
        print()


if __name__ == "__main__":
    main()
