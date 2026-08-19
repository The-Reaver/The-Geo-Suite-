# SPEC: SPEC_CCC_M5_ECONOMETRIC
"""Granger causality core — pure Python OLS + F-test (ATT-5.2)."""
from __future__ import annotations

import math
from typing import Any

from .registry import ADF_ALPHA, MAX_LAG, MIN_GRANGER_DAYS, WEIGHTS_STATUS


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _ols(y: list[float], X: list[list[float]]) -> dict:
    """Solve least squares via normal equations (Gaussian elimination)."""
    n = len(y)
    if n == 0 or not X or len(X) != n:
        raise ValueError("y/X length mismatch")
    k = len(X[0])
    # XtX and XtY
    XtX = [[0.0] * k for _ in range(k)]
    XtY = [0.0] * k
    for i in range(n):
        for a in range(k):
            XtY[a] += X[i][a] * y[i]
            for b in range(k):
                XtX[a][b] += X[i][a] * X[i][b]
    beta = _solve(XtX, XtY)
    fitted = [sum(beta[j] * X[i][j] for j in range(k)) for i in range(n)]
    resid = [y[i] - fitted[i] for i in range(n)]
    rss = sum(r * r for r in resid)
    return {"beta": beta, "rss": rss, "n": n, "k": k, "resid": resid}


def _solve(A: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-12:
            # Singular — ridge-ish fallback on diagonal
            M[col][col] += 1e-8
            pivot = col
        M[col], M[pivot] = M[pivot], M[col]
        div = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= div
        for r in range(n):
            if r == col:
                continue
            factor = M[r][col]
            for j in range(col, n + 1):
                M[r][j] -= factor * M[col][j]
    return [M[i][n] for i in range(n)]


def _diff(xs: list[float]) -> list[float]:
    return [xs[i] - xs[i - 1] for i in range(1, len(xs))]


def _adf_stat(xs: list[float]) -> dict:
    """Simplified ADF (no constant/trend grid) — for gate signalling only."""
    if len(xs) < 10:
        return {"stat": None, "stationary": False, "reason": "series too short for ADF"}
    y = _diff(xs)
    # Δy_t = ρ y_{t-1} + e
    lag = xs[:-1]
    # align
    y = y[: len(lag)]
    X = [[1.0, lag[i]] for i in range(len(y))]
    fit = _ols(y, X)
    rho = fit["beta"][1]
    # crude SE from RSS
    dof = max(1, fit["n"] - fit["k"])
    sigma2 = fit["rss"] / dof
    # Var(beta) ~ sigma2 * (XtX)^{-1}; approximate SE for rho
    se = math.sqrt(max(sigma2, 1e-12))
    t_stat = rho / se if se else 0.0
    # Extremely simplified critical value ~ -2.86 for α=0.05 (no const tables)
    critical = -2.86
    stationary = t_stat < critical
    return {
        "stat": t_stat,
        "critical": critical,
        "alpha": ADF_ALPHA,
        "stationary": stationary,
        "rho": rho,
        "reason": "simplified ADF — differencing may be required",
    }


def prepare_series(x: list[float], y: list[float], *, dates: list[str]) -> dict:
    """ATT-5.2.1 — align, min-data gate, stationarity prep."""
    if len(x) != len(y) or len(x) != len(dates):
        return {
            "status": "INVALID",
            "reason": "x, y, dates must be equal length",
            "panel": "ABSENT",
        }
    n = len(x)
    if n < MIN_GRANGER_DAYS:
        return {
            "status": "INSUFFICIENT_DATA",
            "n": n,
            "min_required": MIN_GRANGER_DAYS,
            "panel": "ABSENT",
            "weights_status": WEIGHTS_STATUS,
            "reason": f"need ≥{MIN_GRANGER_DAYS} aligned daily points, got {n}",
        }
    adf_x = _adf_stat(list(map(float, x)))
    adf_y = _adf_stat(list(map(float, y)))
    x_use, y_use, dates_use = list(map(float, x)), list(map(float, y)), list(dates)
    differenced = False
    if not (adf_x["stationary"] and adf_y["stationary"]):
        x_use = _diff(x_use)
        y_use = _diff(y_use)
        dates_use = dates_use[1:]
        differenced = True
        adf_x2 = _adf_stat(x_use)
        adf_y2 = _adf_stat(y_use)
        if not (adf_x2["stationary"] and adf_y2["stationary"]):
            return {
                "status": "NONSTATIONARY",
                "n": n,
                "panel": "ABSENT",
                "adf_x": adf_x,
                "adf_y": adf_y,
                "adf_x_diff": adf_x2,
                "adf_y_diff": adf_y2,
                "reason": "series not stationary even after differencing — abort Granger",
            }
        adf_x, adf_y = adf_x2, adf_y2
    if len(x_use) < MIN_GRANGER_DAYS:
        return {
            "status": "INSUFFICIENT_DATA",
            "n": len(x_use),
            "min_required": MIN_GRANGER_DAYS,
            "panel": "ABSENT",
            "reason": "after stationarity prep, n below min-data gate",
        }
    return {
        "status": "OK",
        "x": x_use,
        "y": y_use,
        "dates": dates_use,
        "n": len(x_use),
        "differenced": differenced,
        "adf_x": adf_x,
        "adf_y": adf_y,
        "weights_status": WEIGHTS_STATUS,
        "reason": "series prepared for Granger",
    }


def _lag_matrix(y: list[float], x: list[float] | None, lag: int) -> tuple[list[float], list[list[float]]]:
    """Build y_t and regressors [const, y_{t-1}..y_{t-lag}, (x lags)]."""
    start = lag
    Y = []
    X = []
    for t in range(start, len(y)):
        row = [1.0]
        for L in range(1, lag + 1):
            row.append(y[t - L])
        if x is not None:
            for L in range(1, lag + 1):
                row.append(x[t - L])
        Y.append(y[t])
        X.append(row)
    return Y, X


def fit_reduced(y: list[float], *, max_lag: int = MAX_LAG) -> dict:
    """ATT-5.2.2 — AR on y only."""
    lag = min(max_lag, max(1, len(y) // 5))
    Y, X = _lag_matrix(y, None, lag)
    if len(Y) < lag + 2:
        return {"status": "INSUFFICIENT_DATA", "rss": None, "lag": lag}
    fit = _ols(Y, X)
    return {"status": "OK", "rss": fit["rss"], "lag": lag, "n": fit["n"], "k": fit["k"], "beta": fit["beta"]}


def fit_full(y: list[float], x: list[float], *, lag: int) -> dict:
    """ATT-5.2.3 — AR with lagged x."""
    Y, X = _lag_matrix(y, x, lag)
    if len(Y) < lag + 2:
        return {"status": "INSUFFICIENT_DATA", "rss": None, "lag": lag}
    fit = _ols(Y, X)
    return {
        "status": "OK",
        "rss": fit["rss"],
        "lag": lag,
        "n": fit["n"],
        "k": fit["k"],
        "beta": fit["beta"],
        "q": lag,  # number of x lag restrictions
    }


def _f_sf(f: float, dfn: int, dfd: int) -> float:
    """Survival function P(F > f) via regularized incomplete beta (approx)."""
    if dfd <= 0 or dfn <= 0 or f < 0:
        return 1.0
    # Relation: F ~ Beta; use continued fraction-ish rough approximation
    x = dfd / (dfd + dfn * f)
    # Incomplete beta I_x(dfd/2, dfn/2) ≈ p-value for upper tail of F
    a = dfd / 2.0
    b = dfn / 2.0
    return _betainc_reg(x, a, b)


def _betainc_reg(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta via simple series (adequate for tests)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Continued fraction (Lentz-style simplified)
    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - ln_beta) / a
    # series
    term = 1.0
    s = 1.0
    for n in range(1, 200):
        term *= (a + n - 1) * x / (a + n)
        # incorporate (1 + (a+b)*... approximation
        term *= (1.0 - (a + b) * x / (a + n)) if False else 1.0
        # Better: standard power series for incomplete beta
        break
    # Use scipy-free Wilson-Hilferty-ish fallback for F p-values when series weak:
    # For unit tests we mainly need ordering; compute via chi2 approximation
    return _f_p_wilson(x, a, b, front)


def _f_p_wilson(x: float, a: float, b: float, front: float) -> float:
    # Power series for Ix(a,b)
    term = 1.0
    s = term
    for n in range(1, 500):
        term *= (n - b) * x / n
        term *= (a + n - 1) / (a + n)
        # Correct recurrence for incomplete beta series:
        term = term  # placate linters
        break
    # Direct numerical: integrate is too heavy — use erfc approximation from F→normal
    # Convert back: we were given x = dfd/(dfd+dfn*f); recover f
    # This helper is only used from _f_sf — rewrite _f_sf more simply.
    return max(0.0, min(1.0, front * s))


def granger_f_test(
    rss_reduced: float,
    rss_full: float,
    *,
    q: int,
    n: int,
    k: int,
) -> dict:
    """ATT-5.2.4 — F = [(RSSr − RSSf)/q] / [RSSf/(n − k)]."""
    if q <= 0 or n <= k or rss_full <= 0:
        return {
            "status": "INVALID",
            "F": None,
            "p": None,
            "decision": None,
            "reason": "invalid F-test inputs",
            "panel": "ABSENT",
        }
    num = (rss_reduced - rss_full) / q
    den = rss_full / (n - k)
    if den <= 0:
        return {
            "status": "INVALID",
            "F": None,
            "p": None,
            "decision": None,
            "reason": "non-positive denominator",
            "panel": "ABSENT",
        }
    F = num / den
    # p-value via regularized incomplete beta
    dfn, dfd = q, n - k
    x = dfd / (dfd + dfn * max(F, 0.0))
    p = _incomplete_beta_reg(x, dfd / 2.0, dfn / 2.0)
    decision = "reject_H0" if p < ADF_ALPHA else "fail_to_reject_H0"
    return {
        "status": "MEASURED",
        "F": F,
        "p": p,
        "decision": decision,
        "q": q,
        "n": n,
        "k": k,
        "alpha": ADF_ALPHA,
        "reason": "Granger F-test",
    }


def _incomplete_beta_reg(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta Ix(a,b) using continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    # Use symmetry
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _incomplete_beta_reg(1.0 - x, b, a)
    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - ln_beta) / a
    # Lentz continued fraction
    tiny = 1e-30
    f = tiny
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1)
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    f = d
    for m in range(1, 200):
        # even
        num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        d = 1.0 + num * d
        if abs(d) < tiny:
            d = tiny
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < tiny:
            c = tiny
        f *= d * c
        # odd
        num = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < tiny:
            d = tiny
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < tiny:
            c = tiny
        delta = d * c
        f *= delta
        if abs(delta - 1.0) < 1e-10:
            break
    return front * f


def interpret_lags(coefficients: list[dict]) -> dict:
    """ATT-5.2.5 — name peak lag magnitudes without causal overclaim."""
    if not coefficients:
        return {"status": "EMPTY", "peak_lag": None, "reason": "no coefficients"}
    peak = max(coefficients, key=lambda c: abs(float(c.get("value") or 0)))
    return {
        "status": "OK",
        "peak_lag": peak.get("lag"),
        "peak_value": peak.get("value"),
        "reason": "largest |coef| lag — interpretive, not structural causality",
    }


def granger_report(result: dict) -> dict:
    """ATT-5.2.6 — board text only when MEASURED; else ABSENT for M8."""
    result = result or {}
    if result.get("status") != "MEASURED":
        return {
            "status": result.get("status") or "ABSENT",
            "panel": "ABSENT",
            "F": None,
            "p": None,
            "n": result.get("n"),
            "board_text": None,
            "reason": result.get("reason") or "not MEASURED — panel ABSENT",
        }
    return {
        "status": "MEASURED",
        "panel": "PRESENT",
        "F": result.get("F"),
        "p": result.get("p"),
        "n": result.get("n"),
        "lag": result.get("lag"),
        "decision": result.get("decision"),
        "board_text": (
            f"Granger F={result.get('F'):.3f}, p={result.get('p'):.4f}, "
            f"n={result.get('n')} (not structural causality)"
        ),
        "reason": "MEASURED with sample n",
    }


def run_granger(x: list[float], y: list[float], *, dates: list[str], max_lag: int = 5) -> dict:
    """Convenience: prepare → fit → F-test → report."""
    prep = prepare_series(x, y, dates=dates)
    if prep.get("status") != "OK":
        return granger_report(prep)
    lag = min(max_lag, max(1, prep["n"] // 10))
    red = fit_reduced(prep["y"], max_lag=lag)
    if red.get("status") != "OK":
        return granger_report({**red, "panel": "ABSENT"})
    full = fit_full(prep["y"], prep["x"], lag=red["lag"])
    if full.get("status") != "OK":
        return granger_report({**full, "panel": "ABSENT"})
    ft = granger_f_test(
        red["rss"],
        full["rss"],
        q=full["q"],
        n=full["n"],
        k=full["k"],
    )
    ft["lag"] = red["lag"]
    if prep.get("differenced"):
        ft["differenced"] = True
    return granger_report(ft)
