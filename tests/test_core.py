from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from ieg_kb.config import DEFAULT_CONFIG, save_chat_selection
from ieg_kb.database import connect, initialize, stats
from ieg_kb.ingest import ingest_library
from ieg_kb.gemini import GeminiError, chat as gemini_chat
from ieg_kb.openai_compatible import CompatibleAPIError, chat as compatible_chat
from ieg_kb.parsers import parse_file
from ieg_kb.search import search
from ieg_kb.tokenizer import expand_query


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / "library"
        target = self.library / "05_合同与索赔" / "05_通知与函件"
        target.mkdir(parents=True)
        document = target / "项目变更工作卡.md"
        document.write_text(
            "# 变更通知\n\n合同经理必须回到签署版特别条件核对通知期限、收件人和送达方式。"
            "现场应保存指令、日报、照片、人工工时和设备台班等同期记录。",
            encoding="utf-8",
        )
        Path(str(document) + ".meta.json").write_text(json.dumps({
            "title": "A项目变更工作卡",
            "category": "合同与索赔",
            "country": "沙特阿拉伯",
            "contract_form": "FIDIC 2017 Red Book",
            "tags": ["变更", "通知"],
        }, ensure_ascii=False), encoding="utf-8")
        self.config = deepcopy(DEFAULT_CONFIG)
        self.config["_root"] = str(self.root)
        self.config["_config_path"] = str(self.root / "kb_config.json")
        self.config["ollama"]["enabled"] = False

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_chinese_and_domain_token_expansion(self) -> None:
        tokens = expand_query("变更通知和 EOT")
        self.assertIn("变更", tokens)
        self.assertIn("variation", tokens)
        self.assertIn("extension", tokens)

    def test_ingest_and_filtered_search(self) -> None:
        report = ingest_library(self.config)
        self.assertEqual(report["indexed"], 1)
        results = search(
            self.config,
            "变更通知期限和同期记录",
            filters={"category": "合同与索赔", "country": "沙特阿拉伯"},
            semantic=False,
        )
        self.assertTrue(results)
        self.assertEqual(results[0]["title"], "A项目变更工作卡")
        self.assertEqual(results[0]["retrieval"], "lexical")

    def test_incremental_and_delete_sync(self) -> None:
        first = ingest_library(self.config)
        second = ingest_library(self.config)
        self.assertEqual(first["indexed"], 1)
        self.assertEqual(second["skipped"], 1)
        next(self.library.rglob("*.md")).unlink()
        third = ingest_library(self.config)
        self.assertEqual(third["removed"], 1)

    def test_incremental_skip_without_embedding_model(self) -> None:
        ingest_library(self.config)
        connection = connect(Path(self.config["_root"]) / "data" / "kb.sqlite3")
        initialize(connection)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM chunks WHERE vector IS NULL").fetchone()[0], 1)
        connection.close()
        report = ingest_library(self.config)
        self.assertEqual(report["skipped"], 1)

    def test_docx_parser_without_external_dependency(self) -> None:
        path = self.root / "sample.docx"
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>施工方案测试文字</w:t></w:r></w:p></w:body>
        </w:document>"""
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", xml)
        parsed = parse_file(path)
        self.assertEqual(parsed.parser, "docx-xml")
        self.assertIn("施工方案", parsed.units[0].text)

    def test_gemini_requires_key(self) -> None:
        config = deepcopy(self.config)
        config["gemini"] = {"enabled": True, "model": "gemini-3.6-flash"}
        config["privacy"]["allow_cloud_chat"] = True
        with patch.dict("os.environ", {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}, clear=False):
            with self.assertRaises(GeminiError):
                gemini_chat(config, [{"role": "user", "content": "test"}])

    def test_compatible_provider_requires_key(self) -> None:
        config = deepcopy(self.config)
        config["qwen"]["enabled"] = True
        config["privacy"]["allow_cloud_chat"] = True
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": ""}, clear=False):
            with self.assertRaises(CompatibleAPIError):
                compatible_chat(config, "qwen", [{"role": "user", "content": "test"}])

    def test_chat_selection_is_persisted_without_secrets(self) -> None:
        config_path = self.root / "kb_config.json"
        config_path.write_text(json.dumps({"chat": {"provider": "gemini"}}, ensure_ascii=False), encoding="utf-8")
        config = deepcopy(self.config)
        config["_config_path"] = str(config_path)
        save_chat_selection(config, "kimi", "kimi-k2.6")
        saved = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["chat"]["provider"], "kimi")
        self.assertEqual(saved["kimi"]["model"], "kimi-k2.6")
        self.assertNotIn("api_key", json.dumps(saved))

    def test_gpt_5_6_luna_uses_max_reasoning(self) -> None:
        config = deepcopy(self.config)
        config["openai"]["enabled"] = True
        config["openai"]["model"] = "gpt-5.6-luna"
        config["privacy"]["allow_cloud_chat"] = True
        response_body = json.dumps({
            "choices": [{"message": {"content": "已完成分析"}}]
        }).encode("utf-8")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value.read.return_value = response_body
                answer = compatible_chat(config, "openai", [{"role": "user", "content": "test"}])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(answer, "已完成分析")
        self.assertEqual(payload["model"], "gpt-5.6-luna")
        self.assertEqual(payload["reasoning_effort"], "max")
        self.assertNotIn("temperature", payload)

    def test_deepseek_v4_uses_official_model_and_reasoning(self) -> None:
        config = deepcopy(self.config)
        config["deepseek"]["enabled"] = True
        config["deepseek"]["model"] = "deepseek-v4-flash"
        config["privacy"]["allow_cloud_chat"] = True
        response_body = json.dumps({
            "choices": [{"message": {"content": "DeepSeek 已完成分析"}}]
        }).encode("utf-8")
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}, clear=False):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value.read.return_value = response_body
                answer = compatible_chat(config, "deepseek", [{"role": "user", "content": "test"}])
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(answer, "DeepSeek 已完成分析")
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertNotIn("temperature", payload)


if __name__ == "__main__":
    unittest.main()
