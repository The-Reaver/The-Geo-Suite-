import os
import sys
import tempfile
from pathlib import Path

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)

from backend.app.services import site_engine, a11y_audit

class DummyFacts:
    def __init__(self):
        self.business_name = "Test Biz"
        self.subtype = "Dentist"
        self.locality = "Testville"
        self.region = "TE"
        self.street = "123 Test St"
        self.postal_code = "12345"
        self.telephone = "555-1234"
        self.domain = "testbiz.com"
        self.service_areas = ["Area 1"]
        self.services = []
        self.faqs = []
        self.same_as = []
        self.hours = []
        self.credentials = []
        self.last_updated = "2023-01-01"

def create_test_site(tmp_path):
    facts = DummyFacts()
    site_engine.generate_site(facts, tmp_path)
    return Path(tmp_path)

def test_generated_site_passes():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        result = a11y_audit.audit_accessibility(test_site)
        assert result.ok is True
        assert len(result.failures) == 0

def test_missing_alt_caught():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        index = test_site / "index.html"
        content = index.read_text(encoding="utf-8")
        content = content.replace("</article>", "<img src='test.jpg'></article>")
        index.write_text(content, encoding="utf-8")
        
        result = a11y_audit.audit_accessibility(test_site)
        assert result.ok is False
        assert any("missing alt" in f.lower() for f in result.failures)
        assert any("index.html" in f for f in result.failures)

def test_missing_lang_caught():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        index = test_site / "index.html"
        content = index.read_text(encoding="utf-8")
        content = content.replace('<html lang="en">', "<html>")
        index.write_text(content, encoding="utf-8")
        
        result = a11y_audit.audit_accessibility(test_site)
        assert result.ok is False
        assert any("missing lang" in f.lower() for f in result.failures)
        assert any("index.html" in f for f in result.failures)

def test_unlabeled_control_caught():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        index = test_site / "index.html"
        content = index.read_text(encoding="utf-8")
        content = content.replace("</article>", "<input type='text'></article>")
        index.write_text(content, encoding="utf-8")
        
        result = a11y_audit.audit_accessibility(test_site)
        assert result.ok is False
        assert any("missing associated label" in f.lower() for f in result.failures)
        assert any("index.html" in f for f in result.failures)

def test_skipped_heading_caught():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        index = test_site / "index.html"
        content = index.read_text(encoding="utf-8")
        content = content.replace("</h1>", "</h1><h3>Skipped heading</h3>")
        index.write_text(content, encoding="utf-8")
        
        result = a11y_audit.audit_accessibility(test_site)
        assert result.ok is False
        assert any("skipped heading" in f.lower() for f in result.failures)
        assert any("index.html" in f for f in result.failures)


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
    print(f"\\n{passed}/{len(tests)} passed")
    return passed == len(tests)

if __name__ == "__main__":
    import sys; sys.exit(0 if _run_all() else 1)
