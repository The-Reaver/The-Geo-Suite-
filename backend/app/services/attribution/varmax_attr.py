# SPEC: SPEC_CCC_M5_ECONOMETRIC
"""VARMAX / IRF / ROI seam + M8 econometric_panels (ATT-5.3).

Deepened offline stack (Anirak holding ORLOK queue): ARX via OLS with AIC
lag grid, MA(q) residual lags when q>0, IRF from companion recursion — still
tagged UNVALIDATED. No numpy/statsmodels dependency.
"""
from __future__ import annotations

import math
from typing import Any

from .granger import _lag_matrix, _ols, run_granger
from .registry import IRF_HORIZON, MIN_VARMAX_DAYS, WEIGHTS_STATUS


def assemble_exogenous(
    paid: list[dict],
    social: list[dict],
    other: list[dict],
) -> dict:
    """ATT-5.3.1 — name missing exogenous terms."""
    missing = []
    if not paid:
        missing.append("paid")
    if not social:
        missing.append("social")
    present = {
        "paid": list(paid or []),
        "social": list(social or []),
        "other": list(other or []),
    }
    if len(missing) == 3 and not other:
        return {
            "status": "INSUFFICIENT_DATA",
            "exog": present,
            "missing": missing,
            "policy": None,
            "reason": "no exogenous regressors present",
        }
    if missing:
        return {
            "status": "PARTIAL",
            "exog": present,
            "missing": missing,
            "policy": "exog:PARTIAL",
            "reason": f"missing exogenous terms: {', '.join(missing)}",
        }
    return {
        "status": "OK",
        "exog": present,
        "missing": [],
        "policy": "exog:FULL",
        "reason": "all exogenous groups present",
    }


def _series_from_exog_group(rows: list[dict]) -> list[float]:
    out = []
    for r in rows or []:
        out.append(float(r.get("value") or r.get("spend") or r.get("amount") or 0.0))
    return out


def _align_exog_matrix(exog: dict, n: int) -> tuple[list[list[float]] | None, list[str]]:
    """Build T×k exogenous matrix aligned to endog length; pad/trim honestly."""
    named: list[tuple[str, list[float]]] = []
    for key in ("paid", "social", "other"):
        series = _series_from_exog_group((exog or {}).get("exog", {}).get(key) or [])
        if series:
            named.append((key, series))
    if not named:
        return None, []
    cols = []
    labels = []
    for label, series in named:
        if len(series) < n:
            # Do not invent spend — leave short series as PARTIAL column skipped
            continue
        cols.append([float(series[i]) for i in range(n)])
        labels.append(label)
    if not cols:
        return None, []
    # rows
    mat = [[cols[c][t] for c in range(len(cols))] for t in range(n)]
    return mat, labels


def _aic(rss: float, n: int, k: int) -> float:
    if n <= k or rss <= 0:
        return float("inf")
    return n * math.log(rss / n) + 2 * k


def _fit_arx(
    y: list[float],
    *,
    x: list[float] | None,
    exog_mat: list[list[float]] | None,
    p: int,
    q: int,
) -> dict:
    """ARX(+MA residual lags) on y. Returns betas + structure or INSUFFICIENT."""
    Y, Xbase = _lag_matrix(y, x, p)
    if len(Y) < p + 2:
        return {"status": "INSUFFICIENT_DATA", "reason": "too few rows after lagging"}

    # Attach contemporaneous exogenous (aligned to lagged rows: drop first p)
    if exog_mat is not None:
        for i, t in enumerate(range(p, p + len(Y))):
            if t >= len(exog_mat):
                break
            Xbase[i] = Xbase[i] + list(exog_mat[t])

    fit = _ols(Y, Xbase)
    resid = fit["resid"]

    # Optional MA(q): augment with lagged residuals and re-fit once
    if q > 0 and len(resid) > q + 2:
        Y2 = Y[q:]
        X2 = []
        for i in range(q, len(Y)):
            row = list(Xbase[i])
            for L in range(1, q + 1):
                row.append(resid[i - L])
            X2.append(row)
        fit2 = _ols(Y2, X2)
        return {
            "status": "OK",
            "beta": fit2["beta"],
            "rss": fit2["rss"],
            "n": fit2["n"],
            "k": fit2["k"],
            "p": p,
            "q": q,
            "has_x": x is not None,
            "exog_k": 0 if exog_mat is None else len(exog_mat[0]),
            "aic": _aic(fit2["rss"], fit2["n"], fit2["k"]),
        }

    return {
        "status": "OK",
        "beta": fit["beta"],
        "rss": fit["rss"],
        "n": fit["n"],
        "k": fit["k"],
        "p": p,
        "q": 0,
        "has_x": x is not None,
        "exog_k": 0 if exog_mat is None else len(exog_mat[0]),
        "aic": _aic(fit["rss"], fit["n"], fit["k"]),
    }


def fit_varmax(endog: dict, exog: dict, *, p_grid=(1, 2, 3), q_grid=(0, 1)) -> dict:
    """ATT-5.3.2 — ARX(+MA) AIC grid; min-data gate; UNVALIDATED."""
    endog = endog or {}
    y = [float(v) for v in (endog.get("y") or endog.get("revenue") or endog.get("series") or [])]
    x_raw = endog.get("x") or endog.get("sov")
    x = [float(v) for v in x_raw] if x_raw is not None else None
    n = len(y)
    if n < MIN_VARMAX_DAYS:
        return {
            "status": "INSUFFICIENT_DATA",
            "n": n,
            "min_required": MIN_VARMAX_DAYS,
            "panel": "ABSENT",
            "weights_status": WEIGHTS_STATUS,
            "reason": f"VARMAX needs >={MIN_VARMAX_DAYS} days, got {n}",
        }
    if x is not None and len(x) != n:
        return {
            "status": "INVALID",
            "n": n,
            "panel": "ABSENT",
            "reason": "endog x/y length mismatch",
        }
    exog_status = (exog or {}).get("status")
    if exog_status == "INSUFFICIENT_DATA":
        return {
            "status": "INSUFFICIENT_DATA",
            "n": n,
            "panel": "ABSENT",
            "reason": "exogenous block insufficient",
        }

    exog_mat, exog_labels = _align_exog_matrix(exog or {}, n)
    if (exog or {}).get("policy") == "exog:PARTIAL" and exog_mat is None:
        # Policy allows partial — continue without exog columns
        pass

    best = None
    trials = []
    for p in p_grid:
        for q in q_grid:
            trial = _fit_arx(y, x=x, exog_mat=exog_mat, p=int(p), q=int(q))
            trials.append({"p": p, "q": q, "status": trial.get("status"), "aic": trial.get("aic")})
            if trial.get("status") != "OK":
                continue
            if best is None or trial["aic"] < best["aic"]:
                best = trial

    if best is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "n": n,
            "panel": "ABSENT",
            "trials": trials,
            "reason": "no ARX candidate fitted",
        }

    # AR coeffs: beta layout [const, y_lag1..p, (x_lag1..p), (exog...), (ma...)]
    p = best["p"]
    ar = best["beta"][1 : 1 + p]
    return {
        "status": "FITTED_UNVALIDATED",
        "n": n,
        "p": p,
        "q": best["q"],
        "aic": best["aic"],
        "rss": best["rss"],
        "beta": best["beta"],
        "ar_coeffs": ar,
        "has_x": best["has_x"],
        "exog_labels": exog_labels,
        "exog_policy": (exog or {}).get("policy"),
        "y_mean": sum(y) / len(y),
        "trials": trials,
        "weights_status": WEIGHTS_STATUS,
        "method": "arx_aic_grid_pure_python",
        "reason": "UNVALIDATED ARX(+MA) stand-in for VARMAX — not production MLE",
    }


def impulse_response(model: dict, *, horizon: int = IRF_HORIZON, shock: float = 1.0) -> dict:
    """ATT-5.3.3 — IRF from AR companion recursion; ABSENT if unfitted."""
    if (model or {}).get("status") not in ("FITTED_UNVALIDATED", "MEASURED", "OK"):
        return {
            "status": "ABSENT",
            "irf": None,
            "reason": (model or {}).get("reason") or "model not fitted",
        }
    ar = list((model or {}).get("ar_coeffs") or [])
    if not ar:
        # Fallback only if legacy mean-only model — still tag honestly
        mean = float((model or {}).get("y_mean") or 0)
        path = [mean * (0.5 ** (h / max(1, horizon))) for h in range(horizon)]
        return {
            "status": "OK",
            "irf": path,
            "horizon": horizon,
            "ci_lower": [v * 0.5 for v in path],
            "ci_upper": [v * 1.5 for v in path],
            "n": (model or {}).get("n"),
            "weights_status": WEIGHTS_STATUS,
            "method": "mean_decay_fallback",
            "reason": "UNVALIDATED mean-decay fallback — no AR coeffs on model",
        }

    # Companion form recursion: y_t = sum a_i y_{t-i}; shock at t=0
    p = len(ar)
    hist = [0.0] * p
    path = []
    for h in range(horizon):
        if h == 0:
            yt = float(shock)
        else:
            yt = sum(ar[i] * hist[i] for i in range(p))
        path.append(yt)
        hist = [yt] + hist[:-1]

    # Analytic CI proxy from residual scale if present
    rss = float((model or {}).get("rss") or 0.0)
    n = int((model or {}).get("n") or 0)
    k = int((model or {}).get("k") or (model or {}).get("p") or 1)
    sigma = math.sqrt(rss / max(1, n - k)) if n > k else abs(shock) * 0.5
    ci_lo = [v - 1.96 * sigma for v in path]
    ci_hi = [v + 1.96 * sigma for v in path]
    return {
        "status": "OK",
        "irf": path,
        "horizon": horizon,
        "shock": shock,
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "n": (model or {}).get("n"),
        "sigma": sigma,
        "weights_status": WEIGHTS_STATUS,
        "method": "ar_companion_irf",
        "reason": "UNVALIDATED IRF from AR companion recursion (not full VARMAX MLE)",
    }


def revenue_attribution(irf: dict, *, conversion: dict, deal_value: dict) -> dict:
    """ATT-5.3.4 — unsourced conversion/deal → WITHHELD / INSUFFICIENT_BENCHMARKS."""
    conversion = conversion or {}
    deal_value = deal_value or {}
    if not conversion.get("url") or conversion.get("status") in ("UNSOURCED", "WITHHELD"):
        return {
            "status": "INSUFFICIENT_BENCHMARKS",
            "display": None,
            "reason": "conversion benchmark withheld — no resolvable primary URL",
            "panel": "ABSENT",
        }
    if not deal_value.get("url") or deal_value.get("status") in ("UNSOURCED", "WITHHELD"):
        return {
            "status": "INSUFFICIENT_BENCHMARKS",
            "display": None,
            "reason": "deal_value benchmark withheld — no resolvable primary URL",
            "panel": "ABSENT",
        }
    if (irf or {}).get("status") != "OK":
        return {
            "status": "ABSENT",
            "display": None,
            "reason": "IRF not available",
            "panel": "ABSENT",
        }
    conv = float(conversion.get("value") or 0)
    deal = float(deal_value.get("value") or 0)
    peak = max(irf.get("irf") or [0])
    est = peak * conv * deal
    peak_lo = max(irf.get("ci_lower") or [peak * 0.5])
    peak_hi = max(irf.get("ci_upper") or [peak * 1.5])
    return {
        "status": "MEASURED",
        "value": est,
        "ci_lower": peak_lo * conv * deal,
        "ci_upper": peak_hi * conv * deal,
        "n": irf.get("n"),
        "reason": "sourced conversion x deal_value x IRF peak",
    }


def roi_dashboard(attribution: dict, costs: dict) -> dict:
    """ATT-5.3.5 — ABSENT unless IRF + sourced costs + sourced conversion MEASURED."""
    if (attribution or {}).get("status") != "MEASURED":
        return {
            "status": "ABSENT",
            "roi": None,
            "reason": attribution.get("reason") if attribution else "attribution not MEASURED",
        }
    costs = costs or {}
    if not costs.get("url") or costs.get("status") in ("UNSOURCED", "WITHHELD"):
        return {
            "status": "ABSENT",
            "roi": None,
            "reason": "costs unsourced — ROI dashboard ABSENT",
        }
    cost_v = float(costs.get("value") or 0)
    if cost_v <= 0:
        return {"status": "ABSENT", "roi": None, "reason": "non-positive costs"}
    rev = float(attribution.get("value") or 0)
    return {
        "status": "MEASURED",
        "roi": (rev - cost_v) / cost_v,
        "revenue": rev,
        "cost": cost_v,
        "n": attribution.get("n"),
        "reason": "ROI from MEASURED attribution and sourced costs",
    }


def econometric_panels(client_id: str, window: dict) -> dict:
    """M8 integration contract — ABSENT until MEASURED with min-data."""
    window = window or {}
    x = list(window.get("x") or window.get("sov") or [])
    y = list(window.get("y") or window.get("revenue") or [])
    dates = list(window.get("dates") or [])

    absent = {
        "client_id": client_id,
        "granger": "ABSENT",
        "varmax": "ABSENT",
        "roi_irf": "ABSENT",
        "reason": "insufficient data or not MEASURED",
        "weights_status": WEIGHTS_STATUS,
    }

    if len(x) < MIN_VARMAX_DAYS or len(y) < MIN_VARMAX_DAYS or len(dates) < MIN_VARMAX_DAYS:
        absent["reason"] = (
            f"n<{MIN_VARMAX_DAYS} — Granger/VARMAX/ROI panels ABSENT "
            f"(got x={len(x)}, y={len(y)}, dates={len(dates)})"
        )
        return absent

    g = run_granger(x, y, dates=dates)
    if g.get("status") != "MEASURED":
        return {
            **absent,
            "granger": "ABSENT",
            "granger_detail": g,
            "reason": g.get("reason") or "Granger not MEASURED",
        }

    # Fit ARX when window supplies exog; still ABSENT ROI without sourced benches
    exog = window.get("exog") or assemble_exogenous(
        window.get("paid") or [],
        window.get("social") or [],
        window.get("other") or [],
    )
    model = fit_varmax({"y": y, "x": x}, exog)
    irf = impulse_response(model) if model.get("status") == "FITTED_UNVALIDATED" else {
        "status": "ABSENT",
        "reason": model.get("reason"),
    }

    varmax_panel: Any = "ABSENT"
    if model.get("status") == "FITTED_UNVALIDATED" and irf.get("status") == "OK":
        varmax_panel = {
            "status": "FITTED_UNVALIDATED",
            "model": {
                "p": model.get("p"),
                "q": model.get("q"),
                "aic": model.get("aic"),
                "method": model.get("method"),
                "n": model.get("n"),
            },
            "irf": {
                "values": irf.get("irf"),
                "ci_lower": irf.get("ci_lower"),
                "ci_upper": irf.get("ci_upper"),
                "n": irf.get("n"),
                "method": irf.get("method"),
            },
            "weights_status": WEIGHTS_STATUS,
            "reason": model.get("reason"),
        }

    return {
        "client_id": client_id,
        "granger": g,
        "varmax": varmax_panel,
        "roi_irf": "ABSENT",
        "reason": (
            "Granger MEASURED; VARMAX fitted UNVALIDATED when possible; "
            "ROI stays ABSENT until sourced conversion+costs"
        ),
        "weights_status": WEIGHTS_STATUS,
    }
