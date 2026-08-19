# SPEC: SPEC_CCC_M5_ECONOMETRIC
"""AI attribution engine — dark traffic, Granger, VARMAX seam."""
from .dark_traffic import (
    branded_search_inflation,
    estimate_dark_ai_traffic,
    visible_ai_traffic,
)
from .granger import (
    fit_full,
    fit_reduced,
    granger_f_test,
    granger_report,
    interpret_lags,
    prepare_series,
)
from .varmax_attr import (
    assemble_exogenous,
    econometric_panels,
    fit_varmax,
    impulse_response,
    revenue_attribution,
    roi_dashboard,
)
from .registry import MIN_GRANGER_DAYS, WEIGHTS_STATUS

__all__ = [
    "visible_ai_traffic",
    "estimate_dark_ai_traffic",
    "branded_search_inflation",
    "prepare_series",
    "fit_reduced",
    "fit_full",
    "granger_f_test",
    "interpret_lags",
    "granger_report",
    "assemble_exogenous",
    "fit_varmax",
    "impulse_response",
    "revenue_attribution",
    "roi_dashboard",
    "econometric_panels",
    "MIN_GRANGER_DAYS",
    "WEIGHTS_STATUS",
]
