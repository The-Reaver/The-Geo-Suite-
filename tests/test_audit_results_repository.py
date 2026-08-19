import sys
import os
import unittest
from uuid import uuid4
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.audit_engine import run_audit
from backend.app.repositories.audit_results_repository import InMemoryAuditResultsRepository

class TestAuditResultsRepository(unittest.TestCase):
    def setUp(self):
        self.site_dir = os.path.join(os.path.dirname(__file__), "fixtures", "site_pass")
        # passing cwv
        self.cwv = {"lcp_s": 1.2, "inp_ms": 50, "cls": 0.01}
        self.result = run_audit(self.site_dir, cwv=self.cwv)
        self.repo = InMemoryAuditResultsRepository()
        self.site_id = uuid4()

    def test_round_trip(self):
        # save then latest returns a row whose score and passed match the AuditResult, 
        # and whose breakdown contains the 7 category entries.
        row = self.repo.save(self.site_id, self.result, trigger="test")
        latest = self.repo.latest(self.site_id)
        
        self.assertIsNotNone(latest)
        self.assertEqual(latest["score"], self.result.normalized_score)
        self.assertEqual(latest["passed"], self.result.passed)
        self.assertEqual(len(latest["breakdown"]["categories"]), 7)

    def test_latest_is_newest(self):
        # two saves for the same site (different scores) -> latest returns the second
        self.result.normalized_score = 50
        self.repo.save(self.site_id, self.result, trigger="test1")
        time.sleep(0.01) # Ensure slightly different run_at
        
        self.result.normalized_score = 99
        self.repo.save(self.site_id, self.result, trigger="test2")
        
        latest = self.repo.latest(self.site_id)
        self.assertEqual(latest["score"], 99)

    def test_isolation(self):
        # latest for a site with no saved results returns None
        self.assertIsNone(self.repo.latest(uuid4()))

    def test_breakdown_fidelity(self):
        # the persisted breakdown round-trips the not_measured list and the fix_list unchanged
        row = self.repo.save(self.site_id, self.result, trigger="test")
        latest = self.repo.latest(self.site_id)
        
        self.assertEqual(latest["breakdown"]["not_measured"], self.result.not_measured)
        self.assertEqual(latest["breakdown"]["fix_list"], self.result.fix_list)

if __name__ == "__main__":
    unittest.main(argv=["ign"])
