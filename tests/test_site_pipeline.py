import sys
import os
import unittest
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.schemas.site_schemas import BusinessFacts, Service, FAQ, Rating
from backend.app.services.site_pipeline import generate_and_store
from backend.app.repositories.content_pages_repository import InMemoryContentPagesRepository
from backend.app.repositories.schema_records_repository import InMemorySchemaRecordsRepository
from backend.app.repositories.optimization_files_repository import InMemoryOptimizationFilesRepository
from backend.app.repositories.audit_results_repository import InMemoryAuditResultsRepository

class TestSitePipeline(unittest.TestCase):
    def setUp(self):
        self.site_id = uuid4()
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
        self.content_repo = InMemoryContentPagesRepository()
        self.schema_repo = InMemorySchemaRecordsRepository()
        self.opt_repo = InMemoryOptimizationFilesRepository()
        self.audit_repo = InMemoryAuditResultsRepository()

    def test_pipeline(self):
        res = generate_and_store(
            self.site_id, self.facts,
            content_repo=self.content_repo,
            schema_repo=self.schema_repo,
            opt_repo=self.opt_repo,
            audit_repo=self.audit_repo,
            cwv=None,
            trigger="manual"
        )
        
        # 1. Pages stored
        pages = self.content_repo.list_pages(self.site_id)
        # Should have home, service-teeth-cleaning, about. Maybe faq? We have no faqs, so maybe no faq page.
        # But let's check what's there
        page_types = [p["page_type"] for p in pages]
        self.assertIn("home", page_types)
        self.assertIn("about", page_types)
        self.assertIn("service", page_types)
        
        # 2. Opt files stored
        self.assertIsNotNone(self.opt_repo.latest(self.site_id, "robots"))
        self.assertIsNotNone(self.opt_repo.latest(self.site_id, "sitemap"))
        
        # 3. Schema stored valid
        schema = self.schema_repo.get(self.site_id, "/")
        self.assertEqual(schema["validation_status"], "valid")
        
        # 4. Audit stored and passing
        audit = self.audit_repo.latest(self.site_id)
        self.assertGreaterEqual(audit["score"], 90)
        self.assertTrue(audit["passed"])
        
        # 5. Summary
        self.assertEqual(res["pages"], len(pages))
        self.assertEqual(res["opt_files"], 4)
        self.assertEqual(res["schema_status"], "valid")
        self.assertEqual(res["score"], audit["score"])
        self.assertEqual(res["passed"], audit["passed"])

if __name__ == "__main__":
    unittest.main(argv=["ign"])
