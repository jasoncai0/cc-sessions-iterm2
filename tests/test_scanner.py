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

    def test_literal_head_branch_is_hidden(self):
        path = self._write([
            {"type": "user", "cwd": "/Users/demo/proj", "gitBranch": "HEAD",
             "message": {"content": "do it"}},
        ])
        self.assertIsNone(scanner.parse_session_file(path)["branch"])

    def test_named_branch_is_kept(self):
        path = self._write([
            {"type": "user", "cwd": "/Users/demo/proj", "gitBranch": "main",
             "message": {"content": "do it"}},
        ])
        self.assertEqual(scanner.parse_session_file(path)["branch"], "main")


class ScanAndGroupTests(unittest.TestCase):
    def _make_projects(self):
        root = tempfile.mkdtemp()
        proj_a = os.path.join(root, "-Users-demo-a")
        proj_b = os.path.join(root, "-Users-demo-b")
        os.makedirs(proj_a)
        os.makedirs(proj_b)
        for name, cwd in [("s1.jsonl", "/Users/demo/a"),
                          ("s2.jsonl", "/Users/demo/a")]:
            with open(os.path.join(proj_a, name), "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "user", "cwd": cwd,
                                    "message": {"content": name}}) + "\n")
        with open(os.path.join(proj_b, "s3.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "cwd": "/Users/demo/b",
                                "message": {"content": "b work"}}) + "\n")
        # Set proj_a sessions to earlier mtime.
        for name in ["s1.jsonl", "s2.jsonl"]:
            os.utime(os.path.join(proj_a, name), (10 ** 9, 10 ** 9))
        # Make proj_b's session the most recently modified.
        os.utime(os.path.join(proj_b, "s3.jsonl"), (10 ** 9 + 100, 10 ** 9 + 100))
        return root

    def test_scan_finds_all_sessions(self):
        root = self._make_projects()
        sessions = scanner.scan_sessions(root)
        self.assertEqual(len(sessions), 3)

    def test_scan_returns_empty_for_missing_dir(self):
        self.assertEqual(scanner.scan_sessions("/no/such/dir"), [])

    def test_group_orders_groups_by_latest_session(self):
        root = self._make_projects()
        groups = scanner.group_sessions(scanner.scan_sessions(root))
        self.assertEqual(groups[0]["cwd"], "/Users/demo/b")
        names = {g["cwd"]: g for g in groups}
        self.assertEqual(len(names["/Users/demo/a"]["sessions"]), 2)
        self.assertEqual(names["/Users/demo/a"]["name"], "a")

    def test_build_payload_shape(self):
        root = self._make_projects()
        payload = scanner.build_payload(root)
        self.assertIn("groups", payload)
        self.assertEqual(len(payload["groups"]), 2)


if __name__ == "__main__":
    unittest.main()
