import sys
import os
import unittest
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.site_engine import _build_jsonld
from backend.app.schemas.site_schemas import BusinessFacts, Service, FAQ, Rating
from backend.app.repositories.schema_records_repository import InMemorySchemaRecordsRepository

class TestSchemaValidation(unittest.TestCase):
    def setUp(self):
        self.site_id = uuid4()
        self.page_id = uuid4()
        self.repo = InMemorySchemaRecordsRepository()
        
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
        self.graph = _build_jsonld(self.facts, "https://example.com")

    def test_valid(self):
        # 1. Valid: specific-subtype graph with full NAP+url
        row = self.repo.save(self.site_id, page_id=self.page_id, schema_type="LocalBusiness", json_ld=self.graph)
        self.assertEqual(row["validation_status"], "valid")

    def test_warning_generic(self):
        # 2. Warning: business node is generic LocalBusiness
        # mutate the graph
        for node in self.graph["@graph"]:
            if node.get("@type") == "Dentist":
                node["@type"] = "LocalBusiness"
                
        row = self.repo.save(self.site_id, page_id=self.page_id, schema_type="LocalBusiness", json_ld=self.graph)
        self.assertEqual(row["validation_status"], "warning")

    def test_warning_missing_field(self):
        # 3. Warning: subtype node missing telephone
        for node in self.graph["@graph"]:
            if node.get("@type") == "Dentist":
                if "telephone" in node:
                    del node["telephone"]
                    
        row = self.repo.save(self.site_id, page_id=self.page_id, schema_type="LocalBusiness", json_ld=self.graph)
        self.assertEqual(row["validation_status"], "warning")

    def test_error_empty(self):
        # 4. Error: empty list or no business node
        row = self.repo.save(self.site_id, page_id=self.page_id, schema_type="LocalBusiness", json_ld=[])
        self.assertEqual(row["validation_status"], "error")
        
        row2 = self.repo.save(self.site_id, page_id=self.page_id, schema_type="LocalBusiness", json_ld=[{"@type": "WebPage"}])
        self.assertEqual(row2["validation_status"], "error")

if __name__ == "__main__":
    unittest.main(argv=["ign"])
