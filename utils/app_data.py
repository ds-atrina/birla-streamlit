# utils/app_data.py
from __future__ import annotations

import math
import pathlib
from typing import Any, List

import pandas as pd
import streamlit as st


NUMERIC_COLS = [
    "total_revenue_last_90d", "total_revenue_prev_90d", "total_revenue_lifetime",
    "total_orders_last_90d", "total_orders_prev_90d",
    "overdue_amt_total", "os_amt_total", "due_today_total", "due_tomorrow_total", "due_in7_total",
    "days_since_last_order", "avg_order_gap_180d",
    "order_churn_risk_score",
    "pct_revenue_trend_90d", "pct_aov_trend_90d",
    "avg_order_value_last_90d",
    "priority_score_OP",
    "dealer_rank_in_territory_revenue", "territory_count_dealers",
    "tenure_months",
    "count_base_product_last_90d", "base_product_gap_vs_cluster_avg_last_90d",
    "cluster_avg_monthly_revenue_last_90d", "cluster_avg_aov_last_90d",
    "revenue_gap_vs_cluster_avg_monthly_last_90d",
]

CATEGORY_COLS = ["territory_name", "asm_name", "dealer_segment_OP", "dealer_segment_BG"]


def coerce_dealer_df(df: pd.DataFrame) -> pd.DataFrame:
    """Type normalization shared by both cached and uncached loaders."""
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in CATEGORY_COLS:
        if col in df.columns:
            df[col] = df[col].astype("category")

    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _load_dealer_df_from_path(path: str) -> pd.DataFrame:
    """Cached only for file paths (stable hash)."""
    df = pd.read_csv(path)
    return coerce_dealer_df(df)


def load_dealer_df(path_or_file: Any) -> pd.DataFrame:
    """
    Public loader:
    - If string/path -> cached
    - If file-like (UploadedFile) -> uncached
    """
    if isinstance(path_or_file, (str, pathlib.Path)):
        return _load_dealer_df_from_path(str(path_or_file))

    df = pd.read_csv(path_or_file)
    return coerce_dealer_df(df)


def get_territory_df(df: pd.DataFrame, territory_name: str) -> pd.DataFrame:
    """Fast filter (no caching; avoids hashing full DF)."""
    if df is None or df.empty or "territory_name" not in df.columns:
        return pd.DataFrame()
    return df[df["territory_name"] == territory_name].copy()


def extract_all_reasons(action_df: pd.DataFrame, reason_col: str = "reason_chips") -> List[str]:
    if action_df is None or action_df.empty or reason_col not in action_df.columns:
        return []

    # Preferred order (case-insensitive matching)
    preferred_order = [
        "high_overdue",
        "overdue",
        "churn_risk",
        "declining",
        "due_today",
        "due_tomorrow",
        "due_in7",
        "gap_vs_peers",
        "inactive",
    ]
    rank = {k.lower(): i for i, k in enumerate(preferred_order)}

    uniq = set()
    for s in action_df[reason_col].fillna(""):
        for r in (x.strip() for x in str(s).split(",") if x.strip()):
            uniq.add(r)

    # Sort by preferred rank first; anything not in list goes after (alphabetically)
    def sort_key(reason: str):
        r = reason.strip()
        rl = r.lower()
        return (rank.get(rl, 10_000), rl)

    return sorted(uniq, key=sort_key)

def filter_by_any_reason(action_df: pd.DataFrame, selected_reasons: list[str], reason_col: str = "reason_chips") -> pd.DataFrame:
    if not selected_reasons or action_df.empty or reason_col not in action_df.columns:
        return action_df

    def _matches(s: str) -> bool:
        chips = [x.strip() for x in str(s).split(",") if x.strip()]
        return any(r in chips for r in selected_reasons)

    return action_df[action_df[reason_col].apply(_matches)]


def _num(x) -> float:
    try:
        v = float(x)
        if math.isnan(v):
            return 0.0
        return v
    except Exception:
        return 0.0


def get_dealer_collections_numbers(dealer: dict) -> dict:
    overdue = _num(dealer.get("overdue_amt_total", 0))
    os_total = _num(dealer.get("os_amt_total", 0))
    due_today = _num(dealer.get("due_today_total", 0))
    due_today_only = _num(dealer.get("due_today_only_total"))
    due_tomorrow = _num(dealer.get("due_tomorrow_total", 0))
    due_in7 = _num(dealer.get("due_in7_total", 0))

    show = (overdue > 0) or (os_total > 0) or (due_today > 0) or (due_today_only > 0) or (due_tomorrow > 0) or (due_in7 > 0)

    return {
        "show": show,
        "overdue": overdue,
        "os_total": os_total,
        "due_today": due_today,
        "due_today_only": due_today_only,
        "due_tomorrow": due_tomorrow,
        "due_in7": due_in7,
    }
