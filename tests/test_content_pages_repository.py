import sys
import os
import unittest
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.repositories.content_pages_repository import InMemoryContentPagesRepository

class TestContentPagesRepository(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryContentPagesRepository()
        self.site_id = uuid4()

    def test_save_and_read(self):
        # 1. Save/read: save a home page, get_page returns it with version == 1
        page = self.repo.save_page(
            self.site_id,
            slug="/",
            title="Home",
            page_type="home",
            body_json={"blocks": []}
        )
        self.assertEqual(page["version"], 1)
        
        loaded = self.repo.get_page(self.site_id, "/")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["version"], 1)
        self.assertEqual(loaded["page_type"], "home")

    def test_resave_increments_version(self):
        # 2. Re-save increments version: saving the same (site_id, slug) again 
        # returns version == 2 and there is still exactly one row for that slug in list_pages
        self.repo.save_page(self.site_id, slug="/", title="Home", page_type="home", body_json={})
        page2 = self.repo.save_page(self.site_id, slug="/", title="Home v2", page_type="home", body_json={})
        
        self.assertEqual(page2["version"], 2)
        
        pages = self.repo.list_pages(self.site_id)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["version"], 2)
        self.assertEqual(pages[0]["title"], "Home v2")

    def test_list_by_site(self):
        # 3. List by site: three slugs saved → list_pages returns three; a different site returns zero.
        self.repo.save_page(self.site_id, slug="/", title="Home", page_type="home", body_json={})
        self.repo.save_page(self.site_id, slug="/about", title="About", page_type="about", body_json={})
        self.repo.save_page(self.site_id, slug="/faq", title="FAQ", page_type="faq", body_json={})
        
        pages = self.repo.list_pages(self.site_id)
        self.assertEqual(len(pages), 3)
        
        other_site = uuid4()
        other_pages = self.repo.list_pages(other_site)
        self.assertEqual(len(other_pages), 0)

    def test_bad_page_type_rejected(self):
        # 4. Bad page_type rejected: save_page(..., page_type="banner") raises ValueError
        with self.assertRaises(ValueError):
            self.repo.save_page(self.site_id, slug="/banner", title="Banner", page_type="banner", body_json={})

if __name__ == "__main__":
    unittest.main(argv=["ign"])
