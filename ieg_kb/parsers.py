from __future__ import annotations

import csv
import html
import io
import json
import posixpath
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from .archive_safety import read_member, validate_archive


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
        validate_archive(archive)
        root = ET.fromstring(read_member(archive, "word/document.xml"))
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
        validate_archive(archive)
        names = sorted(
            (name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)),
            key=_natural_number,
        )
        for index, name in enumerate(names, 1):
            root = ET.fromstring(read_member(archive, name))
            parts = [node.text or "" for node in root.findall(".//a:t", namespace)]
            text = _clean_text("\n".join(part for part in parts if part.strip()))
            if text:
                units.append(ParsedUnit("第%d页" % index, text))
    return ParsedDocument(units, "pptx-xml", [])


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(read_member(archive, "xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in item.findall(".//x:t", namespace)) for item in root.findall("x:si", namespace)]


def _xlsx_sheet_names(archive: zipfile.ZipFile) -> List[str]:
    if "xl/workbook.xml" not in archive.namelist():
        return []
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(read_member(archive, "xl/workbook.xml"))
    return [node.attrib.get("name", "Sheet%d" % (index + 1)) for index, node in enumerate(root.findall(".//x:sheet", namespace))]


def _parse_xlsx(path: Path) -> ParsedDocument:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    units: List[ParsedUnit] = []
    with zipfile.ZipFile(path) as archive:
        validate_archive(archive)
        shared = _xlsx_shared_strings(archive)
        sheet_names = _xlsx_sheet_names(archive)
        files = sorted(
            (name for name in archive.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", name)),
            key=_natural_number,
        )
        for index, name in enumerate(files):
            root = ET.fromstring(read_member(archive, name))
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


def _epub_opf_path(archive: zipfile.ZipFile) -> str:
    try:
        root = ET.fromstring(read_member(archive, "META-INF/container.xml"))
        for node in root.iter():
            if node.tag.endswith("}rootfile") or node.tag == "rootfile":
                value = (node.attrib.get("full-path") or "").strip()
                if value:
                    return value
    except (KeyError, ET.ParseError):
        pass
    return next((name for name in sorted(archive.namelist()) if name.lower().endswith(".opf")), "")


def _epub_spine(archive: zipfile.ZipFile, opf_path: str) -> List[str]:
    root = ET.fromstring(read_member(archive, opf_path))
    base = posixpath.dirname(opf_path)
    manifest = {}
    for node in root.iter():
        if not (node.tag.endswith("}item") or node.tag == "item"):
            continue
        item_id = (node.attrib.get("id") or "").strip()
        href = unquote((node.attrib.get("href") or "").split("#", 1)[0]).strip()
        media = (node.attrib.get("media-type") or "").lower()
        if item_id and href and ("html" in media or href.lower().endswith((".html", ".htm", ".xhtml"))):
            manifest[item_id] = posixpath.normpath(posixpath.join(base, href))
    order = []
    for node in root.iter():
        if not (node.tag.endswith("}itemref") or node.tag == "itemref"):
            continue
        if (node.attrib.get("linear") or "yes").lower() == "no":
            continue
        target = manifest.get((node.attrib.get("idref") or "").strip())
        if target and target not in order:
            order.append(target)
    return order


def _parse_epub(path: Path) -> ParsedDocument:
    units: List[ParsedUnit] = []
    warnings: List[str] = []
    with zipfile.ZipFile(path) as archive:
        validate_archive(archive)
        names = set(archive.namelist())
        opf_path = _epub_opf_path(archive)
        ordered = _epub_spine(archive, opf_path) if opf_path else []
        if not ordered:
            ordered = sorted(name for name in names if name.lower().endswith((".html", ".htm", ".xhtml")))
            warnings.append("EPUB 未找到有效阅读顺序，已按文件名顺序提取章节。")
        for index, name in enumerate(ordered, 1):
            if name not in names:
                continue
            parser = _HTMLTextExtractor()
            parser.feed(read_member(archive, name).decode("utf-8", errors="replace"))
            text = parser.text()
            if text:
                heading = text.splitlines()[0][:80].strip()
                locator = "EPUB第%d节%s" % (index, "：《%s》" % heading if heading else "")
                units.append(ParsedUnit(locator, text))
    return ParsedDocument(units, "epub-zip", warnings)


def _parse_rtf(path: Path) -> ParsedDocument:
    raw = _read_text(path)
    try:
        from striprtf.striprtf import rtf_to_text  # type: ignore
        converted = _clean_text(rtf_to_text(raw))
        if converted:
            return ParsedDocument([ParsedUnit("全文", converted)], "striprtf", [])
    except (ImportError, ValueError, TypeError):
        pass
    value = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    value = re.sub(r"\\par[d]?", "\n", value)
    value = re.sub(r"\\tab", "\t", value)
    value = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", value)
    value = value.replace("{", "").replace("}", "")
    return ParsedDocument([ParsedUnit("全文", _clean_text(html.unescape(value)))], "rtf-basic", [])


def _parse_calibre_ebook(path: Path) -> ParsedDocument:
    converter = shutil.which("ebook-convert")
    if not converter:
        return ParsedDocument([], "calibre-unavailable", [
            "MOBI/AZW/AZW3 解析需要可选的 Calibre ebook-convert；安装后重新索引。"
        ])
    with tempfile.TemporaryDirectory(prefix="ieg-kb-ebook-") as temporary:
        target = Path(temporary) / "converted.epub"
        try:
            subprocess.run(
                [converter, str(path), str(target)],
                check=True,
                capture_output=True,
                timeout=180,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            return ParsedDocument([], "calibre-error", ["电子书转换失败：%s" % exc])
        parsed = _parse_epub(target)
        parsed.parser = "calibre+%s" % parsed.parser
        return parsed


def parse_file(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".text", ".md", ".markdown", ".rst", ".adoc", ".asciidoc", ".xml", ".yaml", ".yml", ".toml"}:
        return ParsedDocument([ParsedUnit("全文", _clean_text(_read_text(path)))], "text", [])
    if suffix == ".csv":
        return _parse_delimited(path, ",")
    if suffix == ".tsv":
        return _parse_delimited(path, "\t")
    if suffix in {".html", ".htm", ".xhtml"}:
        return _parse_html(path)
    if suffix == ".json":
        return _parse_json(path)
    if suffix == ".docx":
        return _parse_docx(path)
    if suffix in {".pptx", ".pptm"}:
        return _parse_pptx(path)
    if suffix == ".xlsx":
        return _parse_xlsx(path)
    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix == ".epub":
        return _parse_epub(path)
    if suffix == ".rtf":
        return _parse_rtf(path)
    if suffix in {".mobi", ".azw", ".azw3"}:
        return _parse_calibre_ebook(path)
    return ParsedDocument([], "unsupported", ["不支持的文件格式：%s" % suffix])
