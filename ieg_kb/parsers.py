from __future__ import annotations

import csv
import html
import io
import json
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple
from xml.etree import ElementTree as ET


@dataclass
class ParsedUnit:
    locator: str
    text: str


@dataclass
class ParsedDocument:
    units: List[ParsedUnit]
    parser: str
    warnings: List[str]


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style", "noscript"}:
            self._hidden += 1
        elif tag in {"p", "br", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._hidden:
            self._hidden -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._hidden:
            self.parts.append(data)

    def text(self) -> str:
        return _clean_text(" ".join(self.parts))


def _clean_text(value: str) -> str:
    value = value.replace("\x00", "")
    value = re.sub(r"[ \t\u00a0]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "big5", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_delimited(path: Path, delimiter: str) -> ParsedDocument:
    text = _read_text(path)
    rows = []
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        rows.append("\t".join(cell.strip() for cell in row))
    return ParsedDocument([ParsedUnit("表格", _clean_text("\n".join(rows)))], "csv", [])


def _parse_html(path: Path) -> ParsedDocument:
    parser = _HTMLTextExtractor()
    parser.feed(_read_text(path))
    return ParsedDocument([ParsedUnit("网页正文", parser.text())], "html", [])


def _parse_json(path: Path) -> ParsedDocument:
    raw = _read_text(path)
    try:
        value = json.loads(raw)
        raw = json.dumps(value, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        pass
    return ParsedDocument([ParsedUnit("全文", _clean_text(raw))], "json", [])


def _parse_docx(path: Path) -> ParsedDocument:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
        if text:
            paragraphs.append(text)
    return ParsedDocument([ParsedUnit("全文", _clean_text("\n".join(paragraphs)))], "docx-xml", [])


def _natural_number(name: str) -> int:
    match = re.search(r"(\d+)", name)
    return int(match.group(1)) if match else 0


def _parse_pptx(path: Path) -> ParsedDocument:
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    units: List[ParsedUnit] = []
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            (name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)),
            key=_natural_number,
        )
        for index, name in enumerate(names, 1):
            root = ET.fromstring(archive.read(name))
            parts = [node.text or "" for node in root.findall(".//a:t", namespace)]
            text = _clean_text("\n".join(part for part in parts if part.strip()))
            if text:
                units.append(ParsedUnit("第%d页" % index, text))
    return ParsedDocument(units, "pptx-xml", [])


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.findall(".//x:t", namespace)) for item in root.findall("x:si", namespace)]


def _xlsx_sheet_names(archive: zipfile.ZipFile) -> List[str]:
    if "xl/workbook.xml" not in archive.namelist():
        return []
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(archive.read("xl/workbook.xml"))
    return [node.attrib.get("name", "Sheet%d" % (index + 1)) for index, node in enumerate(root.findall(".//x:sheet", namespace))]


def _parse_xlsx(path: Path) -> ParsedDocument:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    units: List[ParsedUnit] = []
    with zipfile.ZipFile(path) as archive:
        shared = _xlsx_shared_strings(archive)
        sheet_names = _xlsx_sheet_names(archive)
        files = sorted(
            (name for name in archive.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", name)),
            key=_natural_number,
        )
        for index, name in enumerate(files):
            root = ET.fromstring(archive.read(name))
            rows = []
            for row in root.findall(".//x:row", namespace):
                values = []
                for cell in row.findall("x:c", namespace):
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("x:v", namespace)
                    if cell_type == "inlineStr":
                        value = "".join(node.text or "" for node in cell.findall(".//x:t", namespace))
                    else:
                        value = value_node.text if value_node is not None and value_node.text else ""
                        if cell_type == "s" and value.isdigit() and int(value) < len(shared):
                            value = shared[int(value)]
                    values.append(value)
                if any(value.strip() for value in values):
                    rows.append("\t".join(values))
            text = _clean_text("\n".join(rows))
            if text:
                locator = "工作表：%s" % (sheet_names[index] if index < len(sheet_names) else "Sheet%d" % (index + 1))
                units.append(ParsedUnit(locator, text))
    return ParsedDocument(units, "xlsx-xml", [])


def _parse_pdf(path: Path) -> ParsedDocument:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return ParsedDocument([], "pdf-unavailable", ["PDF 解析需要可选依赖 pypdf；请运行 ./setup.command 后重新索引。"])
    reader = PdfReader(str(path))
    units = []
    total_chars = 0
    for index, page in enumerate(reader.pages, 1):
        text = _clean_text(page.extract_text() or "")
        total_chars += len(text)
        if text:
            units.append(ParsedUnit("第%d页" % index, text))
    warnings = []
    if reader.pages and total_chars / max(1, len(reader.pages)) < 80:
        warnings.append("平均每页可提取文字少于 80 字，可能是扫描件；建议先做 OCR。")
    return ParsedDocument(units, "pypdf", warnings)


def parse_file(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".xml", ".yaml", ".yml", ".toml"}:
        return ParsedDocument([ParsedUnit("全文", _clean_text(_read_text(path)))], "text", [])
    if suffix == ".csv":
        return _parse_delimited(path, ",")
    if suffix == ".tsv":
        return _parse_delimited(path, "\t")
    if suffix in {".html", ".htm"}:
        return _parse_html(path)
    if suffix == ".json":
        return _parse_json(path)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix == ".pptx":
        return _parse_pptx(path)
    if suffix == ".xlsx":
        return _parse_xlsx(path)
    if suffix == ".pdf":
        return _parse_pdf(path)
    return ParsedDocument([], "unsupported", ["不支持的文件格式：%s" % suffix])
