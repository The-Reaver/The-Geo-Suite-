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
        # generate_site() always writes index/about/privacy/accessibility plus
        # one page per service -- there is no separate FAQ page (FAQs render
        # as a section of index.html).
        page_types = [p["page_type"] for p in pages]
        self.assertIn("home", page_types)
        self.assertIn("about", page_types)
        self.assertIn("service", page_types)
        # privacy.html and accessibility.html used to silently fall through
        # to page_type "about" (the old "default fallback" branch) -- real,
        # generated pages mislabeled in the content repo.
        self.assertIn("privacy", page_types)
        self.assertIn("accessibility", page_types)
        self.assertNotIn("other", page_types, "every page generate_site() actually writes must have its own real page_type")
        
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

    def test_reuses_caller_supplied_generation_and_audit(self):
        # 2026-08-20: generate_and_store() used to unconditionally call
        # generate_site()+run_audit() itself, even when the caller (the real
        # /sites/{id}/audit route) had already generated the site and run
        # the audit a few lines earlier to decide pass/fail -- doubling the
        # real work on every publish. Passing site_dir/audit_result must
        # make it skip regenerating and re-auditing entirely.
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from backend.app.services.site_engine import generate_site
        from backend.app.services import audit_engine

        with tempfile.TemporaryDirectory() as td:
            tmp_dir = Path(td)
            generate_site(self.facts, tmp_dir)
            audit_res = audit_engine.run_audit(tmp_dir, cwv=None)

            with patch("backend.app.services.site_pipeline.generate_site") as mock_gen, \
                 patch("backend.app.services.site_pipeline.run_audit") as mock_audit:
                res = generate_and_store(
                    self.site_id, self.facts,
                    content_repo=self.content_repo,
                    schema_repo=self.schema_repo,
                    opt_repo=self.opt_repo,
                    audit_repo=self.audit_repo,
                    cwv=None,
                    trigger="owner_publish",
                    site_dir=tmp_dir,
                    audit_result=audit_res,
                )
                mock_gen.assert_not_called()
                mock_audit.assert_not_called()

        self.assertEqual(res["score"], audit_res.normalized_score)
        self.assertEqual(res["passed"], audit_res.passed)


if __name__ == "__main__":
    unittest.main(argv=["ign"])
