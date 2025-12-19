# utils/app_utils.py 

import re
import math
import json
import pandas as pd
import streamlit as st
from typing import Optional
from ast import literal_eval

def to_float(x, default=0.0):
    try:
        if x is None or is_nan(x):
            return float(default)
        if isinstance(x, str):
            x = x.strip()
            if x == "":
                return float(default)
        return float(x)
    except Exception:
        return float(default)

def to_int(x, default=0):
    try:
        if x is None or is_nan(x):
            return int(default)
        if isinstance(x, str):
            x = x.strip()
            if x == "":
                return int(default)
        return int(float(x))
    except Exception:
        return int(default)
    
def is_nan(x) -> bool:
    """Check if value is NaN"""
    try:
        return isinstance(x, float) and math.isnan(x)
    except:
        return False
    
def safe_get(d, k, default=0):
    """
    Safe getter for row-dicts.
    - If key missing -> return default (do NOT crash app).
    - If default is None -> return raw value (or None).
    - Otherwise -> try numeric conversion and return float-ish.
    """
    if d is None:
        return default
    if k not in d:
        return default

    v = d.get(k, default)
    if pd.isna(v):
        return default

    # If caller wants "raw" semantics
    if default is None:
        return v

    try:
        return to_float(v, default)
    except Exception:
        return v

def fmt_rs(x):
    """Compact INR formatting (K/L/Cr). Keep SINGLE definition (no overrides)."""
    try:
        val = to_float(x)
        if val >= 10000000:
            return f"₹{val/10000000:.2f}Cr"
        elif val >= 100000:
            return f"₹{val/100000:.2f}L"
        elif val >= 1000:
            return f"₹{val/1000:.1f}K"
        else:
            return f"₹{val:.0f}"
    except Exception:
        return "₹0"

# dealer-level caching
def get_dealer_data(df: pd.DataFrame, dealer_id: str) -> Optional[dict]:
    """Cache individual dealer data"""
    dealer = df[df['dealer_composite_id'] == dealer_id]
    if len(dealer) > 0:
        return dealer.iloc[0].to_dict()
    return None

def flag_text(x):
    return "Yes" if x == 1 else "No"

def ensure_list(x):
    if x is None or is_nan(x):
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        return [x]
    if isinstance(x, str):
        s = x.strip()
        if not s or s.lower() in {"none", "null", "nan"}:
            return []
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except Exception:
            pass
        try:
            parsed = literal_eval(s)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except Exception:
            return []
    return []

def parse_json_relaxed(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None

def calculate_opportunity(dealer: dict):
    has_no_orders = safe_get(dealer, 'has_no_orders', 0)
    if has_no_orders == 1:
        cluster_rev = safe_get(dealer, 'cluster_avg_monthly_revenue_last_90d', 0)
        if cluster_rev > 0:
            return cluster_rev, f"{fmt_rs(cluster_rev)}/month potential based on similar dealers"
        else:
            return 0, "No comparable dealer data available"

    dealer_rev = safe_get(dealer, 'monthly_revenue_last_90d', 0)
    cluster_rev = safe_get(dealer, 'cluster_avg_monthly_revenue_last_90d', 0)
    gap = cluster_rev - dealer_rev

    if gap > 0:
        return gap, "Potential monthly revenue increase"
    elif gap == 0:
        return 0, "Dealer performing at par with peers"
    else:
        return gap, "Dealer performing above peer average"
    
