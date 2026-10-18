"""Check Markdown link handling through the public command-line interface."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ste-lint-zh.py"


class MarkdownLinkTests(unittest.TestCase):
    def lint(self, text, *options):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json", *options],
            input=text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            timeout=10,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_link_label_reports_the_same_violation_as_plain_text(self):
        for text in (
            "请对日志进行分析。",
            "[请对日志进行分析。](https://example.com)",
            "[请对日志进行分析。](../logs.md)",
        ):
            with self.subTest(text=text):
                status, findings = self.lint(text)
                self.assertEqual(status, 1)
                self.assertEqual([item["rule"] for item in findings], ["nominalization"])
                self.assertEqual(findings[0]["col"], text.index("进行") + 1)

    def test_destinations_do_not_count_as_prose(self):
        for destination in (
            "https://example.com/进行分析;强大",
            "../进行分析;强大.md",
            "docs/(缓存)/进行分析;强大.md",
            r"docs/缓存\(示例\)/进行分析;强大.md",
            "<docs/进行分析;强大.md>",
            "<docs/缓存)/进行分析;强大.md>",
            'docs/config.md "进行分析；强大"',
            'docs/config.md "缓存)进行分析；强大"',
            "docs/config.md '缓存)进行分析；强大'",
        ):
            with self.subTest(destination=destination):
                self.assertEqual(self.lint("[读取配置](" + destination + ")。"), (0, []))

    def test_two_links_keep_both_labels_and_original_columns(self):
        text = "[先备份；再删除。](docs/a;b) [对日志进行分析。](docs/strong.md)"
        status, findings = self.lint(text)
        self.assertEqual(status, 1)
        self.assertEqual([item["rule"] for item in findings], ["semicolon", "nominalization"])
        self.assertEqual([item["col"] for item in findings],
                         [text.index("；") + 1, text.index("进行") + 1])

    def test_inline_code_in_labels_remains_excluded(self):
        self.assertEqual(self.lint("[运行 `a(); b()`。](docs/config.md)"), (0, []))

    def test_link_syntax_inside_inline_code_remains_excluded(self):
        self.assertEqual(self.lint("使用 `[进行分析；强大](docs/config.md)`。"), (0, []))

    def test_nested_label_brackets_preserve_visible_text(self):
        status, findings = self.lint("[查看[进行分析]的结果](docs/config.md)")
        self.assertEqual(status, 1)
        self.assertEqual([item["rule"] for item in findings], ["nominalization"])

    def test_image_alt_text_is_checked(self):
        status, findings = self.lint("![请对日志进行分析。](images/强大;图.png)")
        self.assertEqual(status, 1)
        self.assertEqual([item["rule"] for item in findings], ["nominalization"])

    def test_link_in_table_keeps_source_position(self):
        text = "| 说明 | [请对日志进行分析。](docs/a;b) |"
        status, findings = self.lint(text)
        self.assertEqual(status, 1)
        self.assertEqual(findings[0]["rule"], "nominalization")
        self.assertEqual(findings[0]["col"], text.index("进行") + 1)

    def test_prose_after_balanced_destination_is_not_hidden(self):
        text = "[读取配置](docs/(缓存)/config.md)。请对日志进行分析。"
        status, findings = self.lint(text)
        self.assertEqual(status, 1)
        self.assertEqual([item["rule"] for item in findings], ["nominalization"])
        self.assertEqual(findings[0]["col"], text.index("进行") + 1)

    def test_escaped_opening_bracket_is_not_a_link(self):
        status, findings = self.lint(r"\[读取配置](进行分析;强大)")
        self.assertEqual(status, 1)
        self.assertIn("nominalization", [item["rule"] for item in findings])

    def test_escaped_closing_bracket_in_label_keeps_destination_excluded(self):
        self.assertEqual(self.lint(r"[读取配置\]](docs/进行分析;强大.md)。"), (0, []))

    def test_unclosed_destination_does_not_hide_label(self):
        status, findings = self.lint("[请对日志进行分析。](docs/unfinished")
        self.assertEqual(status, 1)
        self.assertEqual([item["rule"] for item in findings], ["nominalization"])

    def test_bare_urls_remain_excluded(self):
        self.assertEqual(self.lint("访问 https://example.com/a;b 。"), (0, []))

    def test_synonym_checks_include_link_labels(self):
        status, findings = self.lint("[用户](docs/a)登录。[客户](docs/b)退出。")
        self.assertEqual(status, 1)
        self.assertEqual([item["rule"] for item in findings], ["synonym-rotation"])

    def test_length_checks_count_labels_and_ignore_destinations(self):
        status, findings = self.lint("[甲乙丙丁戊己](docs/" + "甲" * 50 + ")。", "--max-chars", "5")
        self.assertEqual(status, 1)
        self.assertEqual([item["rule"] for item in findings], ["long-sentence"])
        self.assertEqual(findings[0]["match"], "6 字")

    def test_options_apply_to_link_label_findings(self):
        text = "[请对日志进行分析。](docs/config.md)"
        self.assertEqual(self.lint(text, "--disable", "nominalization"), (0, []))
        status, findings = self.lint(text, "--baseline", "1")
        self.assertEqual(status, 0)
        self.assertEqual([item["rule"] for item in findings], ["nominalization"])


if __name__ == "__main__":
    unittest.main()
