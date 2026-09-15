from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List


ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}
BIDI_CONTROLS = {chr(code) for code in range(0x202A, 0x202F)} | {chr(code) for code in range(0x2066, 0x206A)}

PATTERNS = (
    ("prompt-injection", "high", re.compile(
        r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?)"
        r"|忽略(?:以上|之前|先前|所有)(?:指令|提示|要求)"
        r"|不要遵守(?:系统|开发者|之前)(?:指令|提示)", re.IGNORECASE)),
    ("role-override", "medium", re.compile(
        r"(?:system|developer)\s*(?:message|prompt)\s*:|you\s+are\s+now\s+(?:an?|the)\b"
        r"|(?:系统|开发者)(?:消息|提示词)\s*[：:]|你现在是", re.IGNORECASE)),
    ("external-action", "medium", re.compile(
        r"(?:upload|exfiltrate|send)\s+(?:the\s+)?(?:file|data|secret|credential)s?"
        r"|(?:read|open)\s+(?:other|local|private)\s+files?"
        r"|(?:上传|发送|外传)(?:文件|数据|密钥|凭据)|读取(?:其他|本地|私有)文件", re.IGNORECASE)),
    ("shell-command", "low", re.compile(
        r"(?:^|\n)\s*(?:sudo\s+)?(?:curl|wget|bash|sh|powershell|cmd\.exe)\s+[^\n]+", re.IGNORECASE)),
)

ACTIVE_HTML = re.compile(
    r"<\s*(?:script|iframe|object|embed)\b|\bon\w+\s*=|javascript\s*:|data\s*:\s*text/html",
    re.IGNORECASE,
)
REMOTE_HTML = re.compile(r"(?:src|href)\s*=\s*['\"]\s*https?://", re.IGNORECASE)


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_material(path: Path, extracted_text: str) -> Dict[str, Any]:
    """把材料视为不可信数据，仅报告可疑内容，不执行或删除原文。"""
    findings: List[Dict[str, Any]] = []
    for kind, severity, pattern in PATTERNS:
        for match in list(pattern.finditer(extracted_text))[:20]:
            findings.append({
                "kind": kind,
                "severity": severity,
                "line": _line(extracted_text, match.start()),
                "evidence": re.sub(r"\s+", " ", match.group(0))[:160],
                "action": "treat-as-source-data-do-not-execute",
            })

    zero_width = sum(extracted_text.count(char) for char in ZERO_WIDTH)
    bidi = sum(extracted_text.count(char) for char in BIDI_CONTROLS)
    if zero_width:
        findings.append({"kind": "hidden-unicode", "severity": "medium", "count": zero_width,
                         "action": "review-hidden-characters"})
    if bidi:
        findings.append({"kind": "bidi-control", "severity": "high", "count": bidi,
                         "action": "review-display-order"})

    if path.suffix.lower() in {".html", ".htm", ".xhtml"}:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")[:5_000_000]
        except OSError:
            raw = ""
        for match in list(ACTIVE_HTML.finditer(raw))[:20]:
            findings.append({"kind": "active-html", "severity": "high", "line": _line(raw, match.start()),
                             "evidence": match.group(0)[:160], "action": "do-not-execute-html"})
        for match in list(REMOTE_HTML.finditer(raw))[:20]:
            findings.append({"kind": "remote-resource", "severity": "medium", "line": _line(raw, match.start()),
                             "evidence": match.group(0)[:160], "action": "do-not-fetch-implicitly"})

    severities = {item["severity"] for item in findings}
    status = "review-required" if severities & {"high", "medium"} else ("notice" if findings else "clear")
    return {
        "filename": path.name,
        "status": status,
        "policy": "material-content-is-data-not-instructions",
        "finding_count": len(findings),
        "findings": findings,
    }
