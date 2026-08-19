"""Standalone design-variation test for verify.py battery.

Tests determinism, variation, WCAG contrast, and template coverage of the
site_design engine. No pytest — standalone-runnable with a __main__ runner.
"""
import os
import sys
import types
import tempfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.site_engine import generate_site
from app.services.site_design import engine, palettes


def _F(**kwargs):
    return types.SimpleNamespace(**kwargs)


GOOD_CWV = {"lcp_s": 1.8, "inp_ms": 120, "cls": 0.05}


def test_deterministic_seed_generation():
    f1 = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber")
    f2 = _F(business_name="Acme Plumbing", domain="acme.com", subtype="Plumber")
    f3 = _F(business_name="Zen Dental", domain="zen.com", subtype="Dentist")

    assert engine.compute_seed(f1) == engine.compute_seed(f2), "Same facts must give same seed"
    assert engine.compute_seed(f1) != engine.compute_seed(f3), "Different facts must give different seed"


def test_palettes_wcag_contrast():
    for seed in range(20):
        p = palettes.palette_for("Hair Salon", seed)

        def luminance(hex_col):
            hex_col = hex_col.lstrip("#")
            if len(hex_col) == 3:
                hex_col = "".join(c + c for c in hex_col)
            r, g, b = (int(hex_col[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

            def srgb(c):
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

            return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)

        l1, l2 = luminance(p.ink), luminance(p.bg)
        bright, dark = max(l1, l2), min(l1, l2)
        cr = (bright + 0.05) / (dark + 0.05)
        assert cr >= 4.5, f"Contrast {cr:.2f} < 4.5 for ink={p.ink} bg={p.bg}"


def test_variation_across_businesses():
    businesses = [
        ("Alpha Dental", "alpha.com", "Dentist"),
        ("Beta Plumbers", "beta.com", "Plumber"),
        ("Gamma Legal", "gamma.com", "Attorney"),
        ("Delta Foods", "delta.com", "Restaurant"),
        ("Epsilon Spa", "epsilon.com", "BeautySalon"),
        ("Zeta Hair", "zeta.com", "Hair Salon"),
        ("Eta Real Estate", "eta.com", "Real Estate"),
        ("Theta Repair", "theta.com", "Auto Repair"),
        ("Iota Heating", "iota.com", "HVAC"),
        ("Kappa Vet", "kappa.com", "VeterinaryCare"),
        ("Lambda Movers", "lambda.com", "MovingCompany"),
        ("Mu Nails", "mu.com", "Nail Salon"),
    ]

    templates_seen = set()
    palettes_seen = set()

    for name, domain, subtype in businesses:
        f = _F(business_name=name, domain=domain, subtype=subtype, has_photos=True)
        theme = engine.select_theme(f)
        templates_seen.add(str(theme.template))
        palettes_seen.add(theme.palette.name)

    assert len(templates_seen) >= 3, f"Expected >= 3 templates, got {len(templates_seen)}: {templates_seen}"
    assert len(palettes_seen) >= 4, f"Expected >= 4 palettes, got {len(palettes_seen)}: {palettes_seen}"


def test_generate_site_with_variations():
    f = _F(
        business_name="Acme Plumbing",
        domain="acme.com",
        subtype="Plumber",
        locality="Austin",
        region="TX",
        postal_code="78701",
        country="US",
        telephone="555-0100",
        street="123 Main St",
        services=[types.SimpleNamespace(name="Fixing leaks", description="We fix them.")],
        service_areas=["Austin"],
        same_as=[],
        hours=["Mon-Fri 8-5"],
        faqs=[],
        credentials=[],
        last_updated="2026-07-25",
        tagline="Quality plumbing",
        has_photos=False
    )
    with tempfile.TemporaryDirectory() as tmp:
        generate_site(f, tmp)
        assert os.path.exists(os.path.join(tmp, "index.html")), "index.html missing"
        with open(os.path.join(tmp, "index.html")) as fh:
            html = fh.read()
            assert "Acme Plumbing" in html, "Business name missing from HTML"


# ---------------------------------------------------------------------------
def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
        except Exception as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    if passed < len(tests):
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
