"""cfr_watch.py -- "keep up with the Joneses" mini-slice 0: eCFR
amendment-date watcher.

Watches the 4 real CFR parts backend/app/services/compliance/
regulatory_citations.py already cites (16 CFR 255, 16 CFR 318, 21 CFR
801, 45 CFR 164) for real amendment-date changes, via eCFR's free,
keyless Versioner API (https://www.ecfr.gov/developers/documentation/
api/v1). Read-only, visibility-only -- never writes back to the
baseline file itself (a human commits a real, runner-observed date
after reviewing a genuine change), never fails the job it runs in.

This script's own HTTP-fetch layer could not be directly verified
against a live response from the environment that authored it --
ecfr.gov is blocked by that sandbox's egress proxy (confirmed via both
curl and WebFetch: EGRESS_BLOCKED). The GitHub Actions runner this
script actually executes on has normal outbound internet access and
is the real, live verification: cfr-watch.yml's first workflow_dispatch
run is the genuine test of this parsing logic against eCFR's real
response shape, not something asserted correct from memory.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

_BASELINE_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "regulatory" / "cfr_watch_baseline.json"
_ECFR_VERSIONS_URL = "https://www.ecfr.gov/api/versioner/v1/versions/title-{title}.json"


def load_baseline(path: Path = _BASELINE_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_live_amendment_date(title: int, part: str, timeout: float = 15.0) -> tuple[str | None, str | None]:
    """Returns (latest_amendment_date, error). error is None on success
    (even if no versions matched -- that's a real 'nothing found' result,
    not a fetch failure); error is a short string describing what went
    wrong when the date genuinely couldn't be determined."""
    url = _ECFR_VERSIONS_URL.format(title=title)
    try:
        resp = requests.get(url, params={"part": part}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return None, f"request failed: {exc}"
    except ValueError as exc:
        return None, f"response was not valid JSON: {exc}"

    versions = data.get("content_versions") or data.get("versions") or []
    if not isinstance(versions, list) or not versions:
        return None, "response had no recognizable version list (parser may need updating -- see this file's own docstring)"

    dates = [v.get("amendment_date") or v.get("date") for v in versions if isinstance(v, dict)]
    dates = [d for d in dates if d]
    if not dates:
        return None, "version entries present but none carried a recognizable date field"

    return max(dates), None


def diff_baseline(baseline: dict, live_by_part: dict[str, tuple[str | None, str | None]]) -> list[dict]:
    """Pure comparison logic, no network -- unit-testable against fixture
    data. `live_by_part` maps 'title:part' -> (live_date, error), as
    returned by fetch_live_amendment_date. Returns one row per baseline
    part with a `status` of 'changed', 'unchanged', 'unseeded' (no prior
    baseline date to compare against), or 'fetch_failed'."""
    rows = []
    for entry in baseline.get("parts", []):
        key = f"{entry['title']}:{entry['part']}"
        live_date, error = live_by_part.get(key, (None, "no live data provided"))
        baseline_date = entry.get("last_known_amendment_date")

        if error is not None:
            status = "fetch_failed"
        elif baseline_date is None:
            status = "unseeded"
        elif live_date != baseline_date:
            status = "changed"
        else:
            status = "unchanged"

        rows.append({
            "title": entry["title"],
            "part": entry["part"],
            "law": entry.get("law", ""),
            "citation_file": entry.get("citation_file", ""),
            "baseline_date": baseline_date,
            "live_date": live_date,
            "status": status,
            "error": error,
        })
    return rows


def format_summary(rows: list[dict]) -> str:
    lines = ["## CFR watch\n", "| Part | Law | Baseline date | Live date | Status |", "|---|---|---|---|---|"]
    for r in rows:
        status_label = {
            "changed": "**CHANGED**",
            "unchanged": "unchanged",
            "unseeded": "no baseline yet",
            "fetch_failed": f"fetch failed ({r['error']})",
        }[r["status"]]
        lines.append(
            f"| {r['title']} CFR {r['part']} | {r['law']} | {r['baseline_date'] or '—'} "
            f"| {r['live_date'] or '—'} | {status_label} |"
        )
    changed = [r for r in rows if r["status"] == "changed"]
    unseeded = [r for r in rows if r["status"] == "unseeded"]
    if changed:
        lines.append(
            f"\n**{len(changed)} part(s) changed** since the last known baseline. "
            f"Re-verify the affected citation file(s) and, once confirmed, commit the new "
            f"real date into `cfr_watch_baseline.json` — this job never writes that file itself."
        )
    if unseeded:
        lines.append(
            f"\n**{len(unseeded)} part(s) have no baseline yet.** The live date shown above is "
            f"this run's real, runner-observed value from eCFR — commit it into "
            f"`cfr_watch_baseline.json` to seed the baseline for future comparisons."
        )
    return "\n".join(lines)


def main() -> int:
    baseline = load_baseline()
    live_by_part = {}
    for entry in baseline.get("parts", []):
        key = f"{entry['title']}:{entry['part']}"
        live_by_part[key] = fetch_live_amendment_date(entry["title"], entry["part"])

    rows = diff_baseline(baseline, live_by_part)
    summary = format_summary(rows)
    print(summary)

    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        with open(step_summary_path, "a", encoding="utf-8") as f:
            f.write(summary + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
