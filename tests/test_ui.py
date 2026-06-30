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

    def test_has_detail_then_confirm_flow(self):
        html = ui.index_html()
        # Clicking a row fetches detail before resuming.
        self.assertIn("/api/session?path=", html)
        self.assertIn("openDetail", html)
        # Resume is an explicit confirm button, not the row click itself.
        self.assertIn("Resume in new tab", html)
        self.assertIn("Cancel", html)


if __name__ == "__main__":
    unittest.main()
