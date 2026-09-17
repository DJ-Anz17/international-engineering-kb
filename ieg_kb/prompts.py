from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


MODE_LABELS = {
    "grounded_qa": "依据资料问答",
    "bid_review": "投标报价复核",
    "technical_review": "技术方案审查",
    "productivity": "工效与资源测算",
    "risk_register": "风险登记册",
    "contract_review": "合同条款审查",
    "claim_notice": "索赔与通知",
    "country_entry": "国别与属地化",
    "material_quick": "材料快速了解",
    "material_systematic": "材料系统学习（分主题）",
    "learning_quiz": "材料学习自检",
}


BASE_SYSTEM_PROMPT = """你是国际工程项目的资深顾问。你只能依据给定的本地知识库证据作答，并遵守：
1. 每个关键事实、数字、期限、费率或合同结论后标注来源 [S1]、[S2]。
2. 资料没有覆盖时明确写“资料不足”，不要用常识伪装成资料结论。
3. 区分：原文事实、你的推断、建议。推断必须写明“推断”。
4. 合同、法律、税务与安全问题必须提示人工复核；不同版本文件冲突时列出冲突。
5. 默认用中文，保留关键英文合同术语。回答应可执行、结构清楚、不过度铺陈。
"""


def template_dir(config: Dict[str, Any]) -> Path:
    return Path(config["_root"]) / "templates"


def load_mode_prompt(config: Dict[str, Any], mode: str) -> str:
    selected = mode if mode in MODE_LABELS else "grounded_qa"
    path = template_dir(config) / (selected + ".md")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "请直接回答问题，先给结论，再列证据、资料缺口和下一步。"


def modes() -> List[Dict[str, str]]:
    return [{"id": key, "label": value} for key, value in MODE_LABELS.items()]
