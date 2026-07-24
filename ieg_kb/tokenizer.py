from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Sequence


LATIN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.%+\-/]*")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


DOMAIN_SYNONYMS: Dict[str, Sequence[str]] = {
    "投标": ("招标", "报价", "tender", "bid", "proposal"),
    "报价": ("估价", "价格", "quotation", "pricing", "estimate"),
    "工程量清单": ("清单", "boq", "bill of quantities"),
    "合同": ("contract", "agreement", "conditions of contract"),
    "变更": ("variation", "change order", "vo"),
    "索赔": ("claim", "compensation event"),
    "工期延长": ("eot", "extension of time"),
    "通知": ("notice", "notification"),
    "误期损害赔偿": ("delay damages", "liquidated damages", "ld"),
    "履约保函": ("performance security", "performance bond"),
    "预付款保函": ("advance payment guarantee", "apg"),
    "工效": ("productivity", "production rate", "output rate"),
    "人工": ("labour", "labor", "manpower"),
    "机械": ("equipment", "plant", "machinery"),
    "风险": ("risk", "exposure", "uncertainty"),
    "施工方案": ("method statement", "construction method", "technical proposal"),
    "健康安全环境": ("hse", "ehs", "health safety environment"),
    "不可抗力": ("force majeure", "exceptional event"),
    "fidic": ("红皮书", "黄皮书", "银皮书", "合同条件"),
}


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower().strip()


def cjk_ngrams(sequence: str, sizes: Iterable[int] = (2, 3)) -> List[str]:
    result: List[str] = []
    if len(sequence) == 1:
        return [sequence]
    for size in sizes:
        if len(sequence) < size:
            continue
        result.extend(sequence[index:index + size] for index in range(len(sequence) - size + 1))
    return result


def basic_tokens(text: str) -> List[str]:
    value = normalize(text)
    tokens = LATIN_RE.findall(value)
    for sequence in CJK_RE.findall(value):
        tokens.append(sequence)
        tokens.extend(cjk_ngrams(sequence))
    return _unique(tokens)


def expand_query(text: str) -> List[str]:
    value = normalize(text)
    expanded = list(basic_tokens(value))
    for concept, synonyms in DOMAIN_SYNONYMS.items():
        concept_norm = normalize(concept)
        synonym_norms = [normalize(item) for item in synonyms]
        if concept_norm in value or any(item in value for item in synonym_norms):
            expanded.extend(basic_tokens(concept))
            for synonym in synonyms:
                expanded.extend(basic_tokens(synonym))
    return _unique(expanded)


def search_token_text(text: str) -> str:
    return " ".join(basic_tokens(text))


def fts_query(text: str, max_terms: int = 80) -> str:
    tokens = expand_query(text)[:max_terms]
    safe = ['"' + token.replace('"', '""') + '"' for token in tokens if token]
    return " OR ".join(safe)


def _unique(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
