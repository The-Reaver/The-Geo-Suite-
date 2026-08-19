import os
import sys
import tempfile
from pathlib import Path


PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)

from backend.app.services.preview import generate_preview

class DummyFacts:
    def __init__(self, **kwargs):
        self.business_name = kwargs.get("business_name")
        self.subtype = kwargs.get("subtype")
        self.locality = kwargs.get("locality")
        self.region = kwargs.get("region")
        self.street = kwargs.get("street")
        self.postal_code = kwargs.get("postal_code")
        self.telephone = kwargs.get("telephone")
        self.domain = kwargs.get("domain")
        self.service_areas = kwargs.get("service_areas", ["Area 1"])
        self.services = kwargs.get("services", [])
        self.faqs = kwargs.get("faqs", [])
        self.same_as = kwargs.get("same_as", [])
        self.hours = kwargs.get("hours", [])
        self.credentials = kwargs.get("credentials", [])
        self.last_updated = kwargs.get("last_updated", "2023-01-01")

def test_preview_scores():
    facts = DummyFacts(
        business_name="Full Biz",
        subtype="Dentist",
        locality="City",
        region="ST",
        street="123 St",
        postal_code="12345",
        telephone="555-1234",
        domain="full.com"
    )
    res = generate_preview(facts)
    assert res.is_preview is True
    assert res.publishable is False
    assert isinstance(res.score, (int, float))

def test_watermarked_and_noindex():
    facts = DummyFacts(
        business_name="Watermark Biz",
        subtype="Dentist"
    )
    res = generate_preview(facts)
    out_dir = Path(res.out_dir)
    html_files = list(out_dir.rglob("*.html"))
    assert len(html_files) > 0
    for f in html_files:
        content = f.read_text(encoding="utf-8").lower()
        assert "noindex" in content
        assert "demo preview" in content

def test_incomplete_input_still_renders():
    # Provide absolutely nothing
    facts = DummyFacts()
    res = generate_preview(facts)
    
    assert res.is_preview is True
    # We should have missing details in fix_list
    assert any("business name" in f.lower() for f in res.fix_list)
    assert any("telephone" in f.lower() for f in res.fix_list)

def test_never_publishable():
    facts = DummyFacts(
        business_name="Full Biz",
        subtype="Dentist",
        locality="City",
        region="ST",
        street="123 St",
        postal_code="12345",
        telephone="555-1234",
        domain="full.com"
    )
    # We might pass some threshold depending on CWV, but it doesn't matter, we just check publishable
    # We can pass GOOD_CWV to ensure it scores higher
    cwv = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.05}
    res = generate_preview(facts, cwv=cwv)
    # Even if score >= 90, publishable is False
    assert res.publishable is False

def test_facts_driven():
    facts1 = DummyFacts(business_name="First Biz", subtype="Dentist")
    facts2 = DummyFacts(business_name="Second Biz", subtype="Plumber")
    
    res1 = generate_preview(facts1)
    res2 = generate_preview(facts2)
    
    idx1 = (Path(res1.out_dir) / "index.html").read_text(encoding="utf-8")
    idx2 = (Path(res2.out_dir) / "index.html").read_text(encoding="utf-8")
    
    assert "First Biz" in idx1
    assert "Second Biz" in idx2
    assert "Dentist" in idx1
    assert "Plumber" in idx2


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t(); print("PASS  " + t.__name__); passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
        except Exception as e:
            print("ERROR " + t.__name__ + ": " + type(e).__name__ + ": " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)

if __name__ == "__main__":
    import sys; sys.exit(0 if _run_all() else 1)
