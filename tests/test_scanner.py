import json
import os
import tempfile
import unittest

from cc_sessions import scanner


class DecodeCwdTests(unittest.TestCase):
    def test_decodes_dashed_folder_to_absolute_path(self):
        self.assertEqual(scanner.decode_cwd("-Users-mac-workspace"), "/Users/mac/workspace")

    def test_decodes_private_tmp(self):
        self.assertEqual(scanner.decode_cwd("-private-tmp"), "/private/tmp")


class ExtractUserTextTests(unittest.TestCase):
    def test_returns_string_content_directly(self):
        self.assertEqual(scanner.extract_user_text({"content": "hello"}), "hello")

    def test_returns_first_text_block_from_list_content(self):
        msg = {"content": [{"type": "text", "text": "hi there"}]}
        self.assertEqual(scanner.extract_user_text(msg), "hi there")

    def test_returns_none_for_non_dict(self):
        self.assertIsNone(scanner.extract_user_text(None))


class MeaningfulTextTests(unittest.TestCase):
    def test_rejects_empty_and_whitespace(self):
        self.assertFalse(scanner.is_meaningful_text(""))
        self.assertFalse(scanner.is_meaningful_text("   "))

    def test_rejects_meta_tag_text(self):
        self.assertFalse(scanner.is_meaningful_text("<local-command-caveat>blah"))

    def test_accepts_normal_text(self):
        self.assertTrue(scanner.is_meaningful_text("fix the bug"))


class TruncateLabelTests(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(scanner.truncate_label("a\n  b   c"), "a b c")

    def test_truncates_with_ellipsis(self):
        self.assertEqual(scanner.truncate_label("x" * 100, limit=10), "x" * 9 + "…")


class ParseSessionFileTests(unittest.TestCase):
    def _write(self, lines):
        d = tempfile.mkdtemp(prefix="-Users-demo-proj")
        path = os.path.join(d, "abc123.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for obj in lines:
                f.write(json.dumps(obj) + "\n")
        return path

    def test_uses_summary_when_present(self):
        path = self._write([
            {"type": "user", "cwd": "/Users/demo/proj", "gitBranch": "main",
             "timestamp": "2026-06-01T10:00:00Z",
             "message": {"content": "do the thing"}},
            {"type": "summary", "summary": "Refactor the parser"},
        ])
        result = scanner.parse_session_file(path)
        self.assertEqual(result["id"], "abc123")
        self.assertEqual(result["cwd"], "/Users/demo/proj")
        self.assertEqual(result["branch"], "main")
        self.assertEqual(result["label"], "Refactor the parser")

    def test_falls_back_to_first_meaningful_user_message(self):
        path = self._write([
            {"type": "user", "cwd": "/Users/demo/proj",
             "message": {"content": "<local-command-caveat>skip me"}},
            {"type": "user", "message": {"content": "real request here"}},
        ])
        result = scanner.parse_session_file(path)
        self.assertEqual(result["label"], "real request here")

    def test_skips_malformed_lines_and_decodes_cwd_fallback(self):
        d = tempfile.mkdtemp(prefix="-Users-demo-fallback")
        path = os.path.join(d, "s1.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not json\n")
            f.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        result = scanner.parse_session_file(path)
        # cwd not in records -> decoded from the temp folder name (starts with '/')
        self.assertTrue(result["cwd"].startswith("/"))
        self.assertEqual(result["label"], "hi")

    def test_returns_none_for_missing_file(self):
        self.assertIsNone(scanner.parse_session_file("/no/such/file.jsonl"))


if __name__ == "__main__":
    unittest.main()
