import sys
import os
import tempfile
import unittest
import time
from uuid import uuid4
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.schemas.site_schemas import BusinessFacts, Service, FAQ, Rating
from backend.app.services.site_engine import generate_site
from backend.app.repositories.optimization_files_repository import InMemoryOptimizationFilesRepository

class TestOptimizationFilesRepository(unittest.TestCase):
    def setUp(self):
        self.site_id = uuid4()
        self.repo = InMemoryOptimizationFilesRepository()
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
        generate_site(self.facts, self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_site_dir(self):
        # 1. save_site_dir: reads the real files
        self.repo.save_site_dir(self.site_id, self.temp_dir.name)
        
        r_robots = self.repo.latest(self.site_id, "robots")
        self.assertIsNotNone(r_robots)
        self.assertIn("User-agent", r_robots["content"])
        
        r_sitemap = self.repo.latest(self.site_id, "sitemap")
        self.assertIsNotNone(r_sitemap)
        self.assertIn("<urlset", r_sitemap["content"])

    def test_all_four_types(self):
        # 2. All four types stored: robots, sitemap, llms, llms_full
        self.repo.save_site_dir(self.site_id, self.temp_dir.name)
        
        self.assertIsNotNone(self.repo.latest(self.site_id, "robots"))
        self.assertIsNotNone(self.repo.latest(self.site_id, "sitemap"))
        self.assertIsNotNone(self.repo.latest(self.site_id, "llms"))
        self.assertIsNotNone(self.repo.latest(self.site_id, "llms_full"))

    def test_latest_is_newest(self):
        # 3. latest is newest: saving robots twice with different content
        self.repo.save(self.site_id, file_type="robots", content="User-agent: *")
        time.sleep(0.01) # ensure generated_at differs
        self.repo.save(self.site_id, file_type="robots", content="User-agent: Googlebot")
        
        latest = self.repo.latest(self.site_id, "robots")
        self.assertEqual(latest["content"], "User-agent: Googlebot")

    def test_bad_type_rejected(self):
        # 4. Bad type rejected: favicon
        with self.assertRaises(ValueError):
            self.repo.save(self.site_id, file_type="favicon", content="x")

if __name__ == "__main__":
    unittest.main(argv=["ign"])
