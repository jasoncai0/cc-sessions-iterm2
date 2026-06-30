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


if __name__ == "__main__":
    unittest.main()
