import unittest

from cc_sessions import ui


class IndexHtmlTests(unittest.TestCase):
    def test_returns_self_contained_document(self):
        html = ui.index_html()
        self.assertIn("Claude Sessions", html)
        self.assertIn("/api/sessions", html)
        self.assertIn("/api/resume", html)
        # No external resources allowed.
        self.assertNotIn("http://", html.replace("http://127.0.0.1", ""))
        self.assertNotIn("https://", html)


if __name__ == "__main__":
    unittest.main()
