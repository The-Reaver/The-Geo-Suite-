import sys
import os
import unittest
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.schemas.site_schemas import BusinessFacts, Service, FAQ, Rating
from backend.app.repositories.facts_repository import InMemoryFactsRepository, FactsNotConfirmed

class TestFactsWriter(unittest.TestCase):
    def setUp(self):
        self.site_id = str(uuid4())
        self.client_id = str(uuid4())
        
        self.sites = {self.site_id: {"id": self.site_id, "client_id": self.client_id, "domain": "example.com"}}
        self.clients = {self.client_id: {
            "id": self.client_id, 
            "business_name": "Test Biz", 
            "nap": {
                "street": "123 Main St",
                "locality": "Portland",
                "region": "OR",
                "postal_code": "97204",
                "country": "US",
                "telephone": "555-0100"
            }
        }}
        self.business_facts = {}
        
        self.repo = InMemoryFactsRepository(self.sites, self.clients, self.business_facts)
        
        self.facts = BusinessFacts(
            business_name="Test Biz",
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
            service_areas=["Portland", "Beaverton"],
            services=[Service(name="Teeth Cleaning", description="Deep clean")],
            credentials=["ADA member"],
            faqs=[FAQ(question="Does it hurt?", answer="No.")],
            same_as=["https://g.page/example"],
            rating=Rating(value=4.9, count=218),
            last_updated="2026-07-24T00:00:00Z",
            tagline="Smile brighter"
        )

    def test_round_trip_after_confirm(self):
        self.repo.save_business_facts(self.client_id, self.facts, confirmed=False)
        self.repo.confirm_facts(self.client_id)
        
        loaded = self.repo.load_business_facts(self.site_id)
        self.assertEqual(loaded.subtype, "Dentist")
        self.assertEqual(len(loaded.services), 1)
        self.assertEqual(loaded.services[0].name, "Teeth Cleaning")
        self.assertEqual(loaded.rating.value, 4.9)
        self.assertEqual(loaded.service_areas, ["Portland", "Beaverton"])
        
    def test_unconfirmed_is_not_loadable(self):
        self.repo.save_business_facts(self.client_id, self.facts, confirmed=False)
        # NO confirm step
        with self.assertRaises(FactsNotConfirmed):
            self.repo.load_business_facts(self.site_id)
            
    def test_json_keys_survive(self):
        self.repo.save_business_facts(self.client_id, self.facts, confirmed=True)
        loaded = self.repo.load_business_facts(self.site_id)
        self.assertEqual(loaded.services[0].name, "Teeth Cleaning")
        self.assertEqual(loaded.services[0].description, "Deep clean")
        self.assertEqual(loaded.rating.value, 4.9)
        self.assertEqual(loaded.rating.count, 218)
        
    def test_selective_confirm(self):
        self.repo.save_business_facts(self.client_id, self.facts, confirmed=False)
        self.repo.confirm_facts(self.client_id, field_names=["hours"])
        # still raises because subtype is unconfirmed
        with self.assertRaises(FactsNotConfirmed):
            self.repo.load_business_facts(self.site_id)

if __name__ == "__main__":
    unittest.main(argv=["ign"])
