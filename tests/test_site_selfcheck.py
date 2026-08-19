import sys
import os
import tempfile
import unittest
from uuid import uuid4
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.schemas.site_schemas import BusinessFacts, Service, FAQ, Rating
from backend.app.services.site_engine import generate_site
from backend.app.services.site_selfcheck import check_site

class TestSiteSelfcheck(unittest.TestCase):
    def setUp(self):
        self.facts = BusinessFacts(
            business_name="Test Dentist",
            subtype="Dentist",
            street="123 Main St",
            locality="Portland",
            region="OR",
            postal_code="97204",
            country="US",
            telephone="555-0100",
            email="hello@example.com",
            domain="example.com",
            hours=["Mon-Fri 8:00-17:00"],
            service_areas=["Portland"],
            services=[Service(name="Teeth Cleaning", description="Deep clean")],
            credentials=["ADA member"],
            faqs=[],
            same_as=["https://g.page/example"],
            rating=Rating(value=4.9, count=218),
            last_updated="2026-07-24",
            tagline="Smile"
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.site_dir = Path(self.temp_dir.name)
        generate_site(self.facts, self.site_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_site_passes(self):
        # 1. Clean generated site passes: `check_site` on a freshly generated site → `ok is True`, all lists empty.
        res = check_site(self.site_dir)
        self.assertTrue(res.ok, msg=str(res.findings))
        self.assertEqual(len(res.broken_links), 0)
        self.assertEqual(len(res.pages_missing_canonical), 0)
        self.assertEqual(len(res.pages_missing_mirror), 0)

    def test_broken_link_caught(self):
        # 2. Broken link caught
        index_file = self.site_dir / "index.html"
        content = index_file.read_text(encoding="utf-8")
        index_file.write_text(content + '<a href="missing.html">Link</a>', encoding="utf-8")
        
        res = check_site(self.site_dir)
        self.assertFalse(res.ok)
        self.assertGreater(len(res.broken_links), 0)

    def test_missing_mirror_caught(self):
        # 3. Missing mirror caught: delete one page's `.md` mirror file
        mirror_file = self.site_dir / "index.md"
        mirror_file.unlink()
        res = check_site(self.site_dir)
        self.assertFalse(res.ok)
        self.assertIn("index.html", res.pages_missing_mirror)

    def test_bad_robots_caught(self):
        # 4. Bad robots caught: overwrite `robots.txt`
        robots_file = self.site_dir / "robots.txt"
        robots_file.write_text("User-agent: PerplexityBot\nDisallow: /", encoding="utf-8")
        
        res = check_site(self.site_dir)
        self.assertFalse(res.ok)
        self.assertFalse(res.robots_ok)

if __name__ == "__main__":
    unittest.main(argv=["ign"])
