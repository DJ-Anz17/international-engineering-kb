from __future__ import annotations

import re
import zipfile
from pathlib import PurePosixPath


MAX_ARCHIVE_MEMBERS = 10_000
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000
MIN_RATIO_CHECK_BYTES = 1024 * 1024
SUPPORTED_COMPRESSION_TYPES = {
    zipfile.ZIP_STORED,
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_BZIP2,
    zipfile.ZIP_LZMA,
}


class ArchiveSafetyError(ValueError):
    """ZIP 容器不满足保守的本地解析安全限制。"""


def validate_archive(archive: zipfile.ZipFile) -> None:
    """在读取 DOCX/PPTX/XLSX/EPUB 前拒绝路径穿越、加密和解压炸弹。"""
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ArchiveSafetyError("压缩容器条目过多：%d" % len(members))

    total = 0
    for info in members:
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if path.is_absolute() or name.startswith("//") or re.match(r"^[A-Za-z]:", name) or ".." in path.parts:
            raise ArchiveSafetyError("压缩容器包含不安全路径：%s" % info.filename)
        if info.flag_bits & 0x1:
            raise ArchiveSafetyError("不支持加密条目：%s" % info.filename)
        if info.compress_type not in SUPPORTED_COMPRESSION_TYPES:
            raise ArchiveSafetyError("不支持的压缩方式：%s" % info.filename)
        if info.file_size > MAX_MEMBER_BYTES:
            raise ArchiveSafetyError("压缩条目展开后过大：%s" % info.filename)
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise ArchiveSafetyError("压缩容器展开总量超过安全限制")
        if info.file_size >= MIN_RATIO_CHECK_BYTES:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_COMPRESSION_RATIO:
                raise ArchiveSafetyError("压缩比异常：%s（%.0f:1）" % (info.filename, ratio))


def read_member(archive: zipfile.ZipFile, name: str) -> bytes:
    info = archive.getinfo(name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise ArchiveSafetyError("压缩条目展开后过大：%s" % name)
    return archive.read(info)
