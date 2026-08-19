import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.crawler_policy import validate_robots

class TestCrawlerPolicy(unittest.TestCase):
    def test_good_policy_passes(self):
        # The robots.txt from fixtures/site_pass
        robots_txt = """# Cedar Ridge Dental — crawler policy
# Retrieval + user-triggered AI fetchers are allowed by design.
User-agent: *
Allow: /
Disallow: /admin/

Sitemap: https://cedarridgedental.example/sitemap.xml
"""
        res = validate_robots(robots_txt)
        self.assertTrue(res.ok)
        self.assertEqual(res.blocked_required, [])
        self.assertEqual(res.blocked_user_triggered, [])
        self.assertTrue(res.sitemap_referenced)
        self.assertFalse(res.wellknown_blocked)
        self.assertEqual(res.findings, [])

    def test_blocked_required_bot_fails(self):
        robots_txt = """User-agent: PerplexityBot
Disallow: /

Sitemap: https://cedarridgedental.example/sitemap.xml
"""
        res = validate_robots(robots_txt)
        self.assertFalse(res.ok)
        self.assertIn("PerplexityBot", res.blocked_required)
        self.assertEqual(res.blocked_user_triggered, [])

    def test_blocked_user_triggered_fetcher_hard_fails(self):
        robots_txt = """User-agent: ChatGPT-User
Disallow: /

Sitemap: https://cedarridgedental.example/sitemap.xml
"""
        res = validate_robots(robots_txt)
        self.assertFalse(res.ok)
        self.assertIn("ChatGPT-User", res.blocked_user_triggered)

    def test_missing_sitemap_flagged(self):
        robots_txt = """User-agent: *
Allow: /
"""
        res = validate_robots(robots_txt)
        self.assertFalse(res.ok)
        self.assertFalse(res.sitemap_referenced)
        self.assertTrue(any("sitemap" in f.lower() for f in res.findings))

    def test_wellknown_blocked_flagged(self):
        robots_txt = """User-agent: *
Allow: /
Disallow: /.well-known/

Sitemap: https://cedarridgedental.example/sitemap.xml
"""
        res = validate_robots(robots_txt)
        self.assertFalse(res.ok)
        self.assertTrue(res.wellknown_blocked)
        self.assertTrue(any(".well-known is blocked" in f for f in res.findings))

if __name__ == "__main__":
    unittest.main(argv=["ign"])
