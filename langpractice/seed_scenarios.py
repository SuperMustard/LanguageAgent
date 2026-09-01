"""原来的两个"内置场景"现在只是种子数据——db.connect() 在 scenarios 表首次为空时
把它们插进去，插完就是普通行，跟自动生成的场景没有任何区别（能改、能删，都走同一套
db.py 的 CRUD）。不放 personas.py 是因为 db.py 需要在 connect() 里用它做种子，
personas.py 反过来 import db.py，放 personas.py 会成环。
"""

from .models import PersonaCard

SEED_SCENARIOS: list[PersonaCard] = [
    PersonaCard(
        key="clinic_fr",
        language="fr",
        target_language="French",
        role_identity="一位来做按摩治疗的客人，今天诸事不顺",
        emotional_state="烦躁、有点不耐烦，但不至于无理取闹",
        speaking_style="简短、带情绪，偶尔叹气",
        hidden_motivation="其实想放松，但嘴上不饶人；被真诚对待后会慢慢软化",
        scenario_description="客人刚进诊所，迟到了又找不到车位，一肚子气。你（学习者）是治疗师，要安抚并顺利开始 treatment。",
        difficulty_level="中级，语速正常，用日常口语",
        hostility_level="中等",
    ),
    PersonaCard(
        key="interview_en",
        language="en",
        target_language="English",
        role_identity="一位招聘经理",
        emotional_state="专业、友好但有评估性",
        speaking_style="清晰、结构化，会追问细节",
        hidden_motivation="想判断候选人是否真的合适，会礼貌地深挖",
        scenario_description="一场30分钟的岗位面试，你（学习者）是候选人。",
        difficulty_level="中级偏上，会用一些职场惯用表达",
        hostility_level="温和",
    ),
]
