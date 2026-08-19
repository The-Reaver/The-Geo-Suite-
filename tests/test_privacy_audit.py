import os
import sys
import tempfile
from pathlib import Path

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)

from backend.app.services import site_engine, privacy_audit

class DummyFacts:
    def __init__(self, name="Test Biz", tel="555-1234"):
        self.business_name = name
        self.subtype = "Dentist"
        self.locality = "Testville"
        self.region = "TE"
        self.street = "123 Test St"
        self.postal_code = "12345"
        self.telephone = tel
        self.domain = "testbiz.com"
        self.service_areas = ["Area 1"]
        self.services = []
        self.faqs = []
        self.same_as = []
        self.hours = []
        self.credentials = []
        self.last_updated = "2023-01-01"

def create_test_site(tmp_path, name="Test Biz", tel="555-1234"):
    facts = DummyFacts(name=name, tel=tel)
    site_engine.generate_site(facts, tmp_path)
    return Path(tmp_path)

def test_generated_site_passes():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        result = privacy_audit.audit_privacy(test_site)
        assert result.ok is True, f"Failures: {result.failures}"
        assert len(result.failures) == 0

def test_missing_privacy_page_caught():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        privacy_file = test_site / "privacy.html"
        privacy_file.unlink()
        
        result = privacy_audit.audit_privacy(test_site)
        assert result.ok is False
        assert any("missing privacy.html" in f.lower() for f in result.failures)

def test_missing_footer_link_caught():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        index = test_site / "index.html"
        content = index.read_text(encoding="utf-8")
        content = content.replace('<a href="privacy.html">Privacy</a>', '')
        index.write_text(content, encoding="utf-8")
        
        result = privacy_audit.audit_privacy(test_site)
        assert result.ok is False
        assert any("missing privacy.html link in footer" in f.lower() for f in result.failures)
        assert any("index.html" in f for f in result.failures)

def test_missing_consent_region_caught():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_site = create_test_site(tmpdir)
        index = test_site / "index.html"
        content = index.read_text(encoding="utf-8")
        content = content.replace('id="cookie-consent"', 'id="something-else"')
        index.write_text(content, encoding="utf-8")
        
        result = privacy_audit.audit_privacy(test_site)
        assert result.ok is False
        assert any("missing cookie consent" in f.lower() for f in result.failures)
        assert any("index.html" in f for f in result.failures)

def test_business_named():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        dir1 = tmp_path / "site1"
        dir2 = tmp_path / "site2"
        dir1.mkdir()
        dir2.mkdir()
        
        create_test_site(dir1, name="First Business", tel="555-1111")
        create_test_site(dir2, name="Second Business", tel="555-2222")
        
        privacy1 = (dir1 / "privacy.html").read_text(encoding="utf-8")
        privacy2 = (dir2 / "privacy.html").read_text(encoding="utf-8")
        
        assert "First Business" in privacy1
        assert "555-1111" in privacy1
        assert "Second Business" not in privacy1
        
        assert "Second Business" in privacy2
        assert "555-2222" in privacy2
        assert "First Business" not in privacy2

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
