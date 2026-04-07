"""
utils.app_new_nudges

Rule-based nudge generation for dealer actions.

UPDATED per your latest requirements:
1) Ordering Pattern:
   - returns ALL applicable ordering nudges (no limit)
   - Territory AND ASM comparisons are BOTH supported where relevant
     (i.e., "similar dealers" within territory vs within ASM)
   - ASM cadence stays as a separate ASM nudge

2) Product Recommendations:
   - Territory and ASM product recs are separate nudges/sections
   - Dealer-level product recs (Most Ordered + Repurchase) are separate
   - No limits on # products returned (no truncation)

3) Payment nudges:
   - returns ALL applicable payment nudges (no limit)
   - classification + nudge_type included for each
   - overlaps are allowed (e.g., CEI<70 AND nearing OD => 2 nudges)
"""

from __future__ import annotations

import ast
import json
import math
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from utils import app_utils as U

import pandas as pd

# -------------------------
# CONFIGURABLE CONSTANTS
# -------------------------
# OD_THRESHOLD_DAYS = 50
# NEARING_OD_WARNING_DAYS = 45
# CD10_DISCOUNT_RATE = 0.02
# DEFAULT_CEI_PERCENT = 70.0

# Impact basis defaults (Rs. )
NEW_DEALER_POTENTIAL_DEFAULT = 90_000
WATERPROOF_CATEGORY_DEFAULT = 30_000
MIN_INVOICE_FLOOR = 8_000
REACTIVATION_FLOOR = 10_000
GAP_CLOSURE_FLOOR = 12_000
ACTIVATION_FLOOR = 20_000
CROSS_SELL_FLOOR = 30_000

# =========================
# RANKING CONSTANTS (tunable)
# =========================
MAX_NUDGES_DEFAULT = 5

# Higher = rank earlier
NUDGE_TAG_PRIORITY = {
    # Collections / payments
    "OVERDUE_HIGH_AMOUNT": 1000,
    "OVERDUE_DUE_TODAY": 900,
    "OVERDUE_DUE_TOMORROW": 850,
    "OVERDUE_DUE_IN_7_DAYS": 800,
    "OVERDUE_OS_HIGH": 700,

    # Ordering / churn
    "CHURN_RISK_INACTIVE_90D": 650,
    "CHURN_RISK_HIGH_SCORE": 640,
    "SALES_DROP_SHARP": 600,

    # Product / portfolio
    "PRODUCT_VARIETY_LOW": 500,

    # Fallback
    "PRODUCT_REC_GENERAL": 10,
}

# weighting
RANK_W_TAG = 1_000_000.0
RANK_W_IMPACT = 10.0
RANK_W_STRENGTH = 1.0


def safe_get(dealer: dict, key: str, default=0):
    """Safely get value from dealer dict (handles pandas NaN)."""
    val = (dealer or {}).get(key, default)
    try:
        if pd.isna(val):
            return default
    except Exception:
        pass
    return val


def _parse_jsonish(s: str) -> Any:
    """Parse stringified list/dict from CSV (JSON or python-literal)."""
    if not isinstance(s, str):
        return None
    raw = s.strip()
    if not raw or raw.lower() in {"nan", "none", "null"}:
        return None

    try:
        return json.loads(raw)
    except Exception:
        pass

    try:
        return ast.literal_eval(raw)
    except Exception:
        return None


def _ensure_list_of_dicts(x: Any) -> List[dict]:
    """Return List[dict] for list/dict/str-jsonish/empty inputs."""
    if x is None:
        return []
    if isinstance(x, float) and math.isnan(x):
        return []

    if isinstance(x, dict):
        return [x]

    if isinstance(x, list):
        out: List[dict] = []
        for it in x:
            if isinstance(it, dict):
                out.append(it)
            elif isinstance(it, str) and it.strip():
                out.append({"product": it.strip()})
        return out

    if isinstance(x, str):
        parsed = _parse_jsonish(x)
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            out: List[dict] = []
            for it in parsed:
                if isinstance(it, dict):
                    out.append(it)
                elif isinstance(it, str) and it.strip():
                    out.append({"product": it.strip()})
            return out
        return []

    return []


def _pick_product_names(items: List[dict], limit: Optional[int] = None) -> List[str]:
    """
    Extract product names from list[dict].
    If limit is None => no limit.
    """
    keys = ["product", "base_product", "product_name", "sku_name", "sku", "name"]
    out: List[str] = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        name = ""
        for k in keys:
            v = it.get(k)
            if isinstance(v, str) and v.strip():
                name = v.strip()
                break
        if name and name not in out:
            out.append(name)
        if limit is not None and len(out) >= limit:
            break
    return out


def _pick_category_names(items: List[dict], limit: Optional[int] = None) -> List[str]:
    """
    Extract category/subcategory labels.
    If limit is None => no limit.
    """
    out: List[str] = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        cat = (it.get("category") or "").strip()
        sub = (it.get("sub_category") or "").strip()
        if not cat and not sub:
            continue
        label = f"{cat} / {sub}".strip(" /")
        if label and label not in out:
            out.append(label)
        if limit is not None and len(out) >= limit:
            break
    return out


def _parse_date(x: Any) -> Optional[date]:
    if x is None:
        return None
    if isinstance(x, date) and not isinstance(x, datetime):
        return x
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
    return None


# -------------------------
# Dealer category turnover buckets
# -------------------------
def _norm_turnover_label(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, str):
        s = x.strip()
        if not s or s.lower() in {"nan", "none", "null", "na", "n/a"}:
            return None
        return s
    return None


def derive_dealer_turnover_category(dealer: dict) -> Optional[str]:
    """Return dealer turnover category label."""
    for k in (
        "dealer_category_filled",
        # "category_paint_turnover",
        # "product_category_turnover",
        # "dealer_category_turnover",
        # "dealer_cat",
        # "dealer_category",
        # "turnover_category",
    ):
        v = _norm_turnover_label((dealer or {}).get(k))
        if v:
            return v

    cl = safe_get(dealer, "dealer_credit_limit_effective", None)
    try:
        cl = float(cl) if cl is not None else None
    except Exception:
        cl = None

    if cl is None or cl <= 0:
        return None

    if cl < 75_000:
        return "D"
    if cl < 150_000:
        return "C"
    if cl <= 300_000:
        return "B"
    return "A"


# -------------------------
# CEI handling
# -------------------------
# def get_cei_percent(dealer: dict) -> Optional[float]:
#     cei = (dealer or {}).get("cei_percent")
#     try:
#         if cei is None or (isinstance(cei, float) and math.isnan(cei)):
#             return DEFAULT_CEI_PERCENT
#         cei = float(cei)
#     except Exception:
#         return DEFAULT_CEI_PERCENT

#     if cei == -1:
#         return DEFAULT_CEI_PERCENT

#     if 0 <= cei <= 1:
#         cei = cei * 100.0

#     cei = max(0.0, min(100.0, cei))
#     return cei


# def get_cei(dealer: dict) -> Optional[float]:
#     cei = get_cei_percent(dealer)
#     if cei is not None:
#         return cei
#     return DEFAULT_CEI_PERCENT


# -------------------------
# Formatting helpers
# -------------------------
def fmt_currency(amount: float) -> str:
    try:
        amount = float(amount or 0)
    except Exception:
        amount = 0.0

    if amount >= 10_000_000:
        return f"Rs. {amount/10_000_000:.1f}Cr"
    if amount >= 100_000:
        return f"Rs. {amount/100_000:.1f}L"
    if amount >= 1_000:
        return f"Rs. {amount/1_000:.0f}K"
    return f"Rs. {int(amount)}"


def _priority_badge(p: Any) -> str:
    s = str(p or "").strip().upper()
    return s if s in {"HIGH", "MODERATE", "LOW"} else ""


def _fmt_money(x: Any) -> str:
    try:
        v = float(x)
    except Exception:
        return ""
    if v <= 0:
        return ""
    return fmt_currency(v)


def _fmt_reco_line(it: dict) -> str:
    """
    One-line compact representation for UI text blocks.
    Example:
      'ITALIAN PU MATTE BASE [HIGH] • Lift Rs. 22K (Rs. 15K-Rs. 29K) • 45% peers'
    """
    if not isinstance(it, dict):
        return ""

    name = (it.get("product") or it.get("base_product_name") or it.get("name") or "").strip()
    if not name:
        name = (it.get("category") or "").strip()

    pr = _priority_badge(it.get("priority"))

    lift = _fmt_money(it.get("estimated_revenue_lift"))
    lift_low = _fmt_money(it.get("estimated_revenue_lift_low"))
    lift_high = _fmt_money(it.get("estimated_revenue_lift_high"))

    peers = it.get("percent_peers_stocking") or it.get("percent_peers_buying")
    peers_txt = ""
    try:
        if peers is not None:
            peers_txt = f"{float(peers):.0f}% peers"
    except Exception:
        peers_txt = ""

    parts = []
    if name:
        parts.append(name)
    if pr:
        parts.append(f"[{pr}]")
    if lift:
        if lift_low and lift_high:
            parts.append(f"Lift {lift} ({lift_low}-{lift_high})")
        else:
            parts.append(f"Lift {lift}")
    if peers_txt:
        parts.append(peers_txt)

    return " • ".join(parts).strip()

# def _nudge_rank_score(a: dict) -> float:
#     """
#     Deterministic ranking:
#       1) Tag priority weight
#       2) Impact numeric (parsed from impact string)
#       3) strength_score (if present)
#     """
#     if not isinstance(a, dict):
#         return 0.0

#     tag = str(a.get("tag") or "").strip()
#     tag_priority = float(NUDGE_TAG_PRIORITY.get(tag, 0))

#     impact = _impact_score(a)  # uses your existing parser
#     strength = U.to_float(a.get("strength_score"), 0.0)

#     return tag_priority * RANK_W_TAG + impact * RANK_W_IMPACT + strength * RANK_W_STRENGTH


# -------------------------
# Basis + impact range (grounded in credit limit)
# -------------------------
def calc_basis(signal_value: float, credit_limit: float, floor: float = 8_000.0) -> float:
    """
    Impact basis only.
    Use business signal as primary input.
    Clamp to credit limit ONLY if the credit limit is meaningful.
    This avoids absurd Rs. 1 / Rs. 12 impacts from bad or tiny credit limits.
    """
    try:
        b = float(signal_value or 0)
    except Exception:
        b = 0.0

    try:
        cl = float(credit_limit or 0)
    except Exception:
        cl = 0.0

    # signal basis should never be tiny once a nudge exists
    b = max(floor, b) if b > 0 else floor

    # only respect credit limit if it is meaningful
    # tiny / dirty values should not collapse the impact to Rs. 1
    if cl >= MIN_INVOICE_FLOOR:
        b = min(b, cl)

    return b


def fmt_impact_range(basis: float, credit_limit: float) -> str:
    try:
        cl = float(credit_limit or 0)
    except Exception:
        cl = 0.0

    try:
        b = float(basis or 0)
    except Exception:
        b = 0.0

    b = max(0.0, b)

    if cl >= MIN_INVOICE_FLOOR:
        b = min(b, cl)
        if b >= 0.999 * cl:
            low = 0.8 * cl
            high = cl
        else:
            low = 0.8 * b
            high = min(1.2 * b, cl)
    else:
        low = 0.8 * b
        high = 1.2 * b

    return f"Rs. {low:,.0f}-Rs. {high:,.0f}"

# -------------------------
# Similar-peer helpers (Territory & ASM)
# -------------------------
def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isnan(v):
            return default
        return v
    except Exception:
        return default


def _prefer_sim_overall(sim_val: Any, overall_val: Any) -> float:
    """
    Choose sim_val if it's usable (>0), else fallback to overall_val.
    """
    s = _to_float(sim_val, 0.0)
    if s > 0:
        return s
    return _to_float(overall_val, 0.0)


def _peer_monthly_sim(dealer: dict, level: str) -> float:
    """
    Similar category peers monthly sales.
    level: "territory" | "asm"
    Prefers *_sim_avg_revenue_last_90d, else *_avg_revenue_last_90d.
    Returns monthly number.
    """
    if level == "area":
        v90 = _prefer_sim_overall(
            dealer.get("asm_sim_avg_revenue_last_90d"),
            dealer.get("asm_avg_revenue_last_90d"),
        )
    else:
        v90 = _prefer_sim_overall(
            dealer.get("territory_sim_avg_revenue_last_90d"),
            dealer.get("territory_avg_revenue_last_90d"),
        )
    return (v90 / 3.0) if v90 > 0 else 0.0


def _growth_pct(x: Any) -> float:
    try:
        return float(x or 0)
    except Exception:
        return 0.0

def _peer_growth_pct_sim(dealer: dict, level: str) -> Optional[float]:
    """
    Similar peers growth over last 90d vs prev 90d.
    Returns None when it can't be computed.
    """
    if level == "area":
        prev = _prefer_sim_overall(
            dealer.get("asm_sim_avg_revenue_prev_90d"),
            dealer.get("asm_peer_avg_revenue_prev_90d"),
        )
        curr = _prefer_sim_overall(
            dealer.get("asm_sim_avg_revenue_last_90d"),
            dealer.get("asm_peer_avg_revenue_last_90d"),
        )
    else:
        prev = _prefer_sim_overall(
            dealer.get("territory_sim_avg_revenue_prev_90d"),
            dealer.get("territory_peer_avg_revenue_prev_90d"),
        )
        curr = _prefer_sim_overall(
            dealer.get("territory_sim_avg_revenue_last_90d"),
            dealer.get("territory_peer_avg_revenue_last_90d"),
        )

    if prev <= 0 or curr <= 0:
        return None

    return ((curr / prev) - 1.0) * 100.0


def _fmt_growth_phrase(pct: Any) -> str:
    """Return 'grew by X%' or 'shrunk by X%' (handles negatives)."""
    try:
        v = float(pct or 0)
    except Exception:
        v = 0.0
    
    if v<0:
        return f"shrunk by {abs(v):.0f}%"
    elif v>0:
        return f"grew by {v:.0f}%"
    else:
        return "is dormant"

def _fmt_growth_phrase_only(pct: Any) -> str:
    """Return 'grew by only X%' or 'shrunk by X%' (for underperformer dealer text)."""
    try:
        v = float(pct or 0)
    except Exception:
        v = 0.0
    if v<0:
        return f"shrunk by {abs(v):.0f}%"
    elif v>0:
        return f"grew by only {v:.0f}%"
    else:
        return "is dormant"

def _to_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        v = int(float(x))
        return v
    except Exception:
        return default

def _fmt_rupees(x: float) -> str:
    return f"Rs. {float(x or 0):,.0f}"

def _display_amount(x: Any, floor: float = 0.0) -> float:
    """
    Amount used in the OBSERVATION/ACTION text.
    This should reflect business logic directly, not credit-limit-clamped impact basis.
    """
    try:
        v = float(x or 0)
    except Exception:
        v = 0.0

    if math.isnan(v) or v < 0:
        v = 0.0

    if floor > 0:
        v = max(v, floor)

    return v


def _meaningful_monthly_amount(x: Any, minimum: float = 100.0) -> float:
    """
    Suppress nonsense tiny monthly values in text like Rs. 0 / Rs. 1.
    """
    v = _display_amount(x, floor=0.0)
    return v if v >= minimum else 0.0

# # -------------------------
# # Payment nudges (MULTI; overlaps allowed)
# # -------------------------
# def generate_payment_nudges(dealer: dict) -> List[Dict[str, Any]]:
#     nudges: List[Dict[str, Any]] = []

#     overdue = _to_float(safe_get(dealer, "overdue_amt_total", 0), 0.0)
#     due_today = _to_float(safe_get(dealer, "due_today_total", 0), 0.0)
#     due_tomorrow = _to_float(safe_get(dealer, "due_tomorrow_total", 0), 0.0)
#     due_in7 = _to_float(safe_get(dealer, "due_in7_total", 0), 0.0)

#     invoice_count = _to_int(safe_get(dealer, "invoice_count", 0), 0)
#     credit_limit = _to_float(safe_get(dealer, "dealer_credit_limit_effective", 0), 0.0)

#     cei = _to_float(get_cei(dealer), DEFAULT_CEI_PERCENT)

#     nearing_od_amt = due_today + due_tomorrow + due_in7

#     # Explicit mutually exclusive gates
#     not_od = overdue <= 0
#     is_od = overdue > 10
#     has_nearing_od = nearing_od_amt > 0

#     # ----------------------------
#     # OD Dealers (can still overlap with GOOD_PAYER by CEI if you want)
#     # BUT: MUST NOT overlap with NEARING_OD tags
#     # ----------------------------
#     if is_od:
#         # Ground impact in credit limit; use overdue as primary signal
#         # (you can replace with your blocked-days logic if max_bucket exists)
#         avg_monthly_rev = _to_float(safe_get(dealer, "avg_monthly_revenue_180d", 0), 0.0)
#         signal = max(overdue, avg_monthly_rev, REACTIVATION_FLOOR)
#         basis_loss = calc_basis(signal, credit_limit, floor=REACTIVATION_FLOOR)

#         nudges.append({
#             "tag": "PAY_OD_DEALER",
#             "nudge_type": "payment",
#             "classification": "OD_DEALER",
#             "why": f"Invoice(s) in OD ({_fmt_rupees(overdue)}); credit limit blocked.",
#             "do": "Collect payment now to resume orders and unblock credit.",
#             "impact": None,
#             "level": "dealer",
#         })

#     # ----------------------------
#     # Nearing OD (ONLY when NOT in OD)
#     # ----------------------------
#     if not_od and has_nearing_od:
#         if cei < 70:
#             nudges.append({
#                 "tag": "PAY_NEARING_OD",
#                 "nudge_type": "payment",
#                 "classification": "NEARING_OD",
#                 "why": "Invoice nearing due date; OD risk this week.",
#                 "do": f"Invoice amount {_fmt_rupees(nearing_od_amt)} will be overdue post this week - collect payment now to avoid credit block and order stoppage.",
#                 "impact": None,
#                 "level": "dealer",
#             })
#         else:
#             nudges.append({
#                 "tag": "PAY_GOOD_PAYER_NEARING_OD",
#                 "nudge_type": "payment",
#                 "classification": "GOOD_PAYER_NEARING_OD",
#                 "why": "Invoice nearing due date; OD risk this week.",
#                 "do": f"Invoice amount {_fmt_rupees(nearing_od_amt)} will be overdue post this week - collect payment now to avoid credit block and order stoppage.",
#                 "impact": None,
#                 "level": "dealer",
#             })

#     # ----------------------------
#     # Payment Discipline (independent; your requirement allows overlaps)
#     # ----------------------------
#     if cei < 70:
#         nudges.append({
#             "tag": "PAY_PAYMENT_DISCIPLINE",
#             "nudge_type": "payment",
#             "classification": "PAYMENT_DISCIPLINE",
#             "why": f"CEI% at {cei:.0f}% (below 70%) - payment discipline weak.",
#             "do": "Start timely payments to unlock full discounts and avoid future losses-continued delays risk credit block if OD persists.",
#             "impact": None,
#             "level": "dealer",
#         })

#     # ----------------------------
#     # Good payer baseline (ONLY when CEI>=70 and not already emitted as GOOD_PAYER_NEARING_OD)
#     # OD + GOOD_PAYER is allowed as per your rule.
#     # ----------------------------
#     if cei >= 70 and not (not_od and has_nearing_od):
#         nudges.append({
#             "tag": "PAY_GOOD_PAYER",
#             "nudge_type": "payment",
#             "classification": "GOOD_PAYER",
#             "why": f"CEI% at {cei:.0f}% (healthy) - payment behaviour is good.",
#             "do": "Maintain timely payments to maximize discounts and keep credit line unblocked.",
#             "impact": None,
#             "level": "dealer",
#         })

#     return nudges


# -------------------------
# Ordering helpers
# -------------------------
def _hero_products(level_items_primary: List[dict], level_items_fallback: List[dict], limit: Optional[int] = None) -> List[str]:
    items = level_items_primary if level_items_primary else level_items_fallback
    return _pick_product_names(items, limit=limit)


def _get_territory_hero_names(dealer: dict, limit: Optional[int] = None) -> List[str]:
    in_cat_items = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_products_in_dealer_categories", []))
    terr_top_items = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_top_products_90d", []))
    return _hero_products(in_cat_items, terr_top_items, limit=limit)


def _get_asm_hero_names(dealer: dict, limit: Optional[int] = None) -> List[str]:
    in_cat_items = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_products_in_dealer_categories", []))
    asm_top_items = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_top_products_90d", []))
    return _hero_products(in_cat_items, asm_top_items, limit=limit)


def _inactive_categories_info(dealer: dict) -> Tuple[List[dict], float]:
    inactive_items = _ensure_list_of_dicts(safe_get(dealer, "llm_inactive_categories_90d", []))

    peer_typical = 0.0
    if inactive_items and isinstance(inactive_items[0], dict):
        try:
            peer_typical = float(inactive_items[0].get("peer_typical_monthly_sales") or 0)
        except Exception:
            peer_typical = 0.0

    return inactive_items, peer_typical


def _pick_hero_or_top_new_category(level_new_cat_items: List[dict]) -> Tuple[Optional[dict], str, float]:
    default_label = "Hero product categories"
    default_benchmark = 30_000.0

    if not level_new_cat_items:
        return None, default_label, default_benchmark

    chosen = None
    for it in level_new_cat_items:
        if isinstance(it, dict):
            chosen = it
            break

    if not chosen:
        return None, default_label, default_benchmark

    cat = (chosen.get("category") or "").strip() or default_label
    bench = chosen.get("benchmark_monthly_category_sales")
    try:
        bench_f = float(bench or 0)
    except Exception:
        bench_f = 0.0
    if bench_f <= 0:
        bench_f = default_benchmark

    return chosen, cat, bench_f


def _tenure_days(dealer: dict, as_of: Optional[date] = None) -> Optional[int]:
    """
    Best-effort tenure days.
    Tries:
      - tenure_days
      - tenure_months * 30
      - customer_creation_date against as_of_date / today
    """
    td = safe_get(dealer, "tenure_days", None)
    try:
        if td is not None and not (isinstance(td, float) and math.isnan(td)):
            td = int(td)
            if td >= 0:
                return td
    except Exception:
        pass

    tm = safe_get(dealer, "tenure_months", None)
    try:
        if tm is not None and not (isinstance(tm, float) and math.isnan(tm)):
            tm = float(tm)
            if tm >= 0:
                return int(round(tm * 30))
    except Exception:
        pass

    created = _parse_date(safe_get(dealer, "customer_creation_date", None))
    if created is None:
        return None

    as_of_date = _parse_date(safe_get(dealer, "as_of_date", None)) or as_of or date.today()
    try:
        return max(0, (as_of_date - created).days)
    except Exception:
        return None


def _monthly_runrate_from_90d(revenue_90d: float) -> float:
    try:
        return float(revenue_90d or 0) / 3.0
    except Exception:
        return 0.0

def _meta_items_for_products(items: List[dict], max_items: int = 5) -> List[dict]:
    out = []
    for it in (items or [])[:max_items]:
        if not isinstance(it, dict):
            continue
        out.append({
            "base_product_code": it.get("base_product_code") or it.get("product_code") or it.get("sku_code"),
            "base_product_id": it.get("base_product_id") or it.get("product_id") or it.get("sku_id"),
            "category_code": it.get("category_code") or it.get("category_id"),
            "category_id": it.get("category_id"),
        })
    # keep only rows that have at least product_code/id or category_code/id
    cleaned = []
    for x in out:
        if any([x.get("base_product_code"), x.get("base_product_id"), x.get("category_code"), x.get("category_id")]):
            cleaned.append(x)
    return cleaned

def _meta_for_category(it: Optional[dict]) -> dict:
    if not isinstance(it, dict):
        return {"items": []}
    return {"items": [{
        "category_code": it.get("category_code") or it.get("category_id"),
        "category_id": it.get("category_id"),
        "category": it.get("category"),
        "sub_category": it.get("sub_category"),
    }]}
    
def _obs_action(why_obs: str, do_action: str) -> Dict[str, str]:
    return {
        "why": f"{why_obs}".strip(),
        "do": f"{do_action}".strip(),
    }
    
# def _make_peer_based_nudges(
#     *,
#     dealer: dict,
#     credit_limit: float,
#     is_new_30d: bool,
#     is_existing: bool,
#     orders_90d: int,
#     revenue_90d: float,
#     dealer_growth: float,
#     inactive_cat_items: List[dict],
#     inactive_peer_typical: float,
#     days_since_order: int,
#     terr_hero_str: str,
#     asm_hero_str: str,
#     terr_hero_items: List[dict],
#     asm_hero_items: List[dict],
#     waterproof_cat_item: Optional[dict],
#     waterproof_cat_label: str,
#     waterproof_bench: float,
#     turnover_hint: str,
#     turnover_cat: Optional[str],
# ) -> List[Dict[str, Any]]:

#     nudges: List[Dict[str, Any]] = []
#     dealer_monthly = _monthly_runrate_from_90d(revenue_90d)

#     for level in ("territory", "area"):
#         peer_monthly = _peer_monthly_sim(dealer, level)
#         peer_growth_opt = _peer_growth_pct_sim(dealer, level)
#         hero_str = terr_hero_str if level == "territory" else asm_hero_str
#         bench_label = "similar category dealers in territory" if level == "territory" else "similar category dealers in Area"

#         # ----------------------------
#         # New Dealer Nudges
#         # ----------------------------
#         if is_new_30d and orders_90d == 0:
#             cluster_potential = _to_float(
#                 safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", NEW_DEALER_POTENTIAL_DEFAULT),
#                 NEW_DEALER_POTENTIAL_DEFAULT,
#             )
#             basis = calc_basis(cluster_potential, credit_limit, floor=ACTIVATION_FLOOR)
            
#             # Only add if basis is meaningful
#             if basis > 0:
#                 nudges.append({
#                     "tag": f"ORDERING_NEW_NO_ORDERS_{str(level).upper()}",
#                     "nudge_type": "ordering",
#                     "classification": f"NEW_NO_ORDERS_{level.upper()}",
#                     **_obs_action(
#                         f"New dealer onboarded - but no orders yet.",
#                         f"Potential business of {fmt_currency(basis)} per month based on similar dealers. "
#                         f"Pitch Birla Opus Hero products (bill from the AI-recommended list)."
#                     ),
#                     "meta": {"items": _meta_items_for_products(terr_hero_items if level=="territory" else asm_hero_items)},
#                     "impact": fmt_impact_range(basis, credit_limit),
#                     "level": level,
#                 })

#         if is_new_30d and dealer_monthly > 0 and peer_monthly > 0 and dealer_monthly < peer_monthly:
#             gap_monthly = max(0.0, peer_monthly - dealer_monthly)
            
#             # Only add if gap is meaningful (at least 10% difference)
#             if gap_monthly > (peer_monthly * 0.1):
#                 basis = calc_basis(gap_monthly, credit_limit, floor=GAP_CLOSURE_FLOOR)
#                 nudges.append({
#                     "tag": f"ORDERING_NEW_LOW_{str(level).upper()}",
#                     "nudge_type": "ordering",
#                     "classification": f"NEW_LOW_ORDERS_{level.upper()}",
#                     **_obs_action(
#                         f"New dealer onboarded - but current billing is {fmt_currency(gap_monthly)} less than the average of {bench_label}{turnover_hint}.",
#                         f"Pitch Birla Opus hero products ({hero_str}) to increase overall billing and bridge the gap."
#                     ),
#                     "meta": {"items": _meta_items_for_products(terr_hero_items if level=="territory" else asm_hero_items)},
#                     "impact": fmt_impact_range(basis, credit_limit),
#                     "level": level,
#                 })

#         if is_new_30d and peer_monthly > 0 and dealer_monthly > peer_monthly:
#             basis = calc_basis(waterproof_bench, credit_limit, floor=CROSS_SELL_FLOOR)
            
#             if basis > 0:
#                 nudges.append({
#                     "tag": f"ORDERING_NEW_HIGH_{str(level).upper()}",
#                     "nudge_type": "ordering",
#                     "classification": f"NEW_HIGH_ORDERS_{level.upper()}",
#                     **_obs_action(
#                         f"Billing value is greater than {bench_label}{turnover_hint}.",
#                         f"Introduce Birla Opus {waterproof_cat_label}-{bench_label} are already doing {fmt_currency(basis)} monthly with this."
#                     ),
#                     "meta": _meta_for_category(waterproof_cat_item),
#                     "impact": fmt_impact_range(basis, credit_limit),
#                     "level": level,
#                 })

#         # ----------------------------
#         # EXISTING DEALER: Compare GROWTH rates
#         # ----------------------------
#         if is_existing and peer_growth_opt is not None:
#             # Underperformer: dealer growth < peer growth (at least 5% difference)
#             if dealer_growth < (peer_growth_opt - 5):
#                 # Calculate gap based on peer monthly (for impact estimation)
#                 gap = max(0.0, peer_monthly - dealer_monthly) if peer_monthly > 0 else ACTIVATION_FLOOR
                
#                 # Only add if gap is meaningful
#                 if gap > 0:
#                     basis = calc_basis(gap, credit_limit, floor=ACTIVATION_FLOOR)

#                     growth_text = (
#                         f"In the last 3 months, {turnover_cat or 'similar category'} dealers in "
#                         f"{'territory' if level == 'territory' else 'area'} {_fmt_growth_phrase(peer_growth_opt)}, "
#                         f"while this dealer {_fmt_growth_phrase_only(dealer_growth)}."
#                     )

#                     nudges.append({
#                         "tag": f"ORDERING_UNDERPERFORMER_{str(level).upper()}",
#                         "nudge_type": "ordering",
#                         "classification": f"UNDERPERFORMER_{level.upper()}",
#                         **_obs_action(
#                             growth_text + (turnover_hint or ""),
#                             f"Dealers in similar category are making {fmt_currency(gap)} more every month. "
#                             f"Bridge it by ordering Birla Opus hero products: {hero_str}."
#                         ),
#                         "meta": {"items": _meta_items_for_products(terr_hero_items if level=="territory" else asm_hero_items)},
#                         "impact": fmt_impact_range(basis, credit_limit),
#                         "level": level,
#                     })

#             # Good Performer: dealer growth >= peer growth
#             elif dealer_growth >= (peer_growth_opt - 5):
#                 basis = calc_basis(waterproof_bench, credit_limit, floor=CROSS_SELL_FLOOR)

#                 if basis > 0:
#                     growth_text = (
#                         f"In the last 3 months, dealer {_fmt_growth_phrase(dealer_growth)}, "
#                         f"which is {'higher than' if dealer_growth > peer_growth_opt else 'in line with'} "
#                         f"{bench_label} who {_fmt_growth_phrase(peer_growth_opt)}."
#                     )

#                     nudges.append({
#                         "tag": f"ORDERING_GOOD_PERFORMER_{str(level).upper()}",
#                         "nudge_type": "ordering",
#                         "classification": f"GOOD_PERFORMER_{level.upper()}",
#                         **_obs_action(
#                             growth_text + (turnover_hint or ""),
#                             f"Introduce Birla Opus {waterproof_cat_label}-{bench_label} are already doing {fmt_currency(basis)} monthly with this."
#                         ),
#                         "meta": _meta_for_category(waterproof_cat_item),
#                         "impact": fmt_impact_range(basis, credit_limit),
#                         "level": level,
#                     })

#     # Territory-only actions (inactive categories, 90d inactive)
#     if is_existing and inactive_cat_items and days_since_order < 90:
#         for it in inactive_cat_items:
#             if not isinstance(it, dict):
#                 continue
#             category_name = f"{(it.get('category') or '').strip()} / {(it.get('sub_category') or '').strip()}".strip(" /")
#             if not category_name:
#                 continue

#             basis_val = inactive_peer_typical if inactive_peer_typical > 0 else ACTIVATION_FLOOR
            
#             # Only add if basis is meaningful
#             if basis_val > 0:
#                 basis = calc_basis(basis_val, credit_limit, floor=ACTIVATION_FLOOR)

#                 nudges.append({
#                     "tag": "ORDERING_INACTIVE_CATEGORY",
#                     "nudge_type": "ordering",
#                     "classification": "INACTIVE_CATEGORY",
#                     "why": f"Dealer hasn't ordered {category_name} for 90+ days, though it was part of past purchases{turnover_hint}.",
#                     "do": (
#                         f"Similar dealers in territory earn {fmt_currency(basis)}/month from this category. "
#                         f"Encourage dealer to reorder {category_name} now to capture demand and boost sales."
#                     ),
#                     "impact": fmt_impact_range(basis, credit_limit),
#                     "level": "territory",
#                     "meta": {
#                         "items": [{
#                             "category_code": it.get("category_code") or it.get("category_id"),
#                             "category_id": it.get("category_id"),
#                             "category": it.get("category"),
#                             "sub_category": it.get("sub_category"),
#                         }]
#                     },
#                 })

#     if is_existing and days_since_order >= 90:
#         avg_monthly_rev = _to_float(safe_get(dealer, "avg_monthly_revenue_180d", 0), 0.0)
#         if avg_monthly_rev <= 0:
#             avg_monthly_rev = 45_000.0
#         loss_3m = avg_monthly_rev * 3.0
#         basis = calc_basis(loss_3m, credit_limit, floor=CROSS_SELL_FLOOR)

#         if basis > 0:
#             nudges.append({
#                 "tag": "ORDERING_INACTIVE_90D",
#                 "nudge_type": "ordering",
#                 "classification": "INACTIVE_90D",
#                 **_obs_action(
#                     f"Dealer inactive for 90 days-no orders placed{turnover_hint}.",
#                     f"Losing approx. {fmt_currency(basis)} in sales (based on monthly run rate {fmt_currency(avg_monthly_rev)}). "
#                     f"Place orders for high-demand Birla Opus products: {terr_hero_str}."
#                 ),
#                 "meta": {"items": _meta_items_for_products(terr_hero_items)},
#                 "impact": fmt_impact_range(basis, credit_limit),
#                 "level": "territory",
#             })

#     return nudges

def _dealer_is_active_last_30d(dealer: dict) -> bool:
    """
    Spec: 'active dealer; has billed with us in past 30 days'
    We gate by any of:
      - total_revenue_last_30d > 0
      - total_orders_last_30d > 0
      - days_since_last_order <= 30
    (fallback-friendly if some columns don't exist)
    """
    rev30 = _to_float(safe_get(dealer, "total_revenue_last_30d", 0), 0.0)
    ord30 = _to_int(safe_get(dealer, "total_orders_last_30d", 0), 0)
    dsl = _to_int(safe_get(dealer, "days_since_last_order", 9999), 9999)
    return (rev30 > 0) or (ord30 > 0) or (dsl <= 30)


def _dealer_prev90_monthly_runrate(dealer: dict) -> float:
    """
    Spec: Inactive 90d lost sales should be based on previous 90d (days 91-180).
    Prefer fields if present; otherwise fallback to avg_monthly_revenue_180d.

    Expected upstream columns (try in order):
      - total_revenue_prev_90d
      - total_revenue_91_180d
      - prev_90d_revenue
      - avg_monthly_revenue_prev_90d
      - avg_monthly_revenue_180d (fallback)
    """
    prev90 = _to_float(safe_get(dealer, "total_revenue_prev_90d", 0), 0.0)
    if prev90 <= 0:
        prev90 = _to_float(safe_get(dealer, "total_revenue_91_180d", 0), 0.0)
    if prev90 <= 0:
        prev90 = _to_float(safe_get(dealer, "prev_90d_revenue", 0), 0.0)

    if prev90 > 0:
        return prev90 / 3.0

    avg_prev = _to_float(safe_get(dealer, "avg_monthly_revenue_prev_90d", 0), 0.0)
    if avg_prev > 0:
        return avg_prev

    # fallback
    avg180 = _to_float(safe_get(dealer, "avg_monthly_revenue_180d", 0), 0.0)
    return avg180 if avg180 > 0 else 45_000.0

def _classify_ordering_bucket(
    *,
    is_new_30d: bool,
    is_existing: bool,
    orders_90d: int,
    dealer_monthly: float,
    days_since_order: int,
    inactive_cat_items: List[dict],
    dealer_growth: float,
    peer_monthly: float,
    peer_growth_opt: Optional[float],
) -> Optional[str]:
    """
    Coverage-first classification.
    Always tries to assign one ordering bucket.
    """

    if is_new_30d:
        if orders_90d == 0:
            return "NEW_NO_ORDERS_AREA"
        if peer_monthly > 0 and dealer_monthly < peer_monthly:
            return "NEW_LOW_ORDERS_AREA"
        return "NEW_HIGH_ORDERS_AREA"

    if is_existing:
        if days_since_order >= 90:
            return "INACTIVE_90D"
        if bool(inactive_cat_items) and days_since_order < 90:
            return "INACTIVE_CATEGORY"

        # performance fallback bucketing
        if peer_growth_opt is not None:
            if dealer_growth < peer_growth_opt:
                return "UNDERPERFORMER_AREA"
            return "GOOD_PERFORMER_AREA"

        # if growth peers missing, fallback to monthly comparison
        if peer_monthly > 0 and dealer_monthly < peer_monthly:
            return "UNDERPERFORMER_AREA"
        return "GOOD_PERFORMER_AREA"

    return None

def _make_peer_based_nudges(
    *,
    dealer: dict,
    credit_limit: float,
    is_new_30d: bool,
    is_existing: bool,
    orders_90d: int,
    revenue_90d: float,
    dealer_growth: float,
    inactive_cat_items: List[dict],
    inactive_peer_typical: float,
    days_since_order: int,
    terr_hero_str: str,
    asm_hero_str: str,
    terr_hero_items: List[dict],
    asm_hero_items: List[dict],
    waterproof_cat_item: Optional[dict],
    waterproof_cat_label: str,
    waterproof_bench: float,
    turnover_hint: str,
    turnover_cat: Optional[str],
) -> List[Dict[str, Any]]:

    nudges: List[Dict[str, Any]] = []
    dealer_monthly = _monthly_runrate_from_90d(revenue_90d)

    # ----------------------------------------------------------
    # Mutually-exclusive EXISTING dealer state hierarchy
    # Priority:
    #   1) INACTIVE_90D
    #   2) INACTIVE_CATEGORY
    #   3) PERFORMANCE buckets (UNDER / GOOD)
    # ----------------------------------------------------------
    level = "area"
    peer_monthly = _peer_monthly_sim(dealer, level)
    peer_growth_opt = _peer_growth_pct_sim(dealer, level)

    hero_str = asm_hero_str
    hero_items = asm_hero_items
    bench_label = "similar category dealers in the Area"

    dealer_monthly = _monthly_runrate_from_90d(revenue_90d)

    assigned_bucket = _classify_ordering_bucket(
        is_new_30d=is_new_30d,
        is_existing=is_existing,
        orders_90d=orders_90d,
        dealer_monthly=dealer_monthly,
        days_since_order=days_since_order,
        inactive_cat_items=inactive_cat_items if _dealer_is_active_last_30d(dealer) else [],
        dealer_growth=dealer_growth,
        peer_monthly=peer_monthly,
        peer_growth_opt=peer_growth_opt,
    )

    # ----------------------------
    # 1) New Dealer - No orders
    # ----------------------------
    if assigned_bucket == "NEW_NO_ORDERS_AREA":
        basis_monthly = peer_monthly
        if basis_monthly <= 0:
            basis_monthly = _to_float(
                safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", NEW_DEALER_POTENTIAL_DEFAULT),
                NEW_DEALER_POTENTIAL_DEFAULT,
            )
        if basis_monthly <= 0:
            basis_monthly = NEW_DEALER_POTENTIAL_DEFAULT

        display_monthly = _display_amount(basis_monthly, floor=NEW_DEALER_POTENTIAL_DEFAULT)
        basis = calc_basis(display_monthly, credit_limit, floor=ACTIVATION_FLOOR)

        nudges.append({
            "tag": "ORDERING_NEW_NO_ORDERS_AREA",
            "nudge_type": "ordering",
            "classification": "NEW_NO_ORDERS_AREA",
            **_obs_action(
                "New dealer onboarded - but no orders yet.",
                f"Potential business of {fmt_currency(display_monthly)} per month based on similar dealers. "
                f"Pitch Birla Opus Hero products (bill from the AI-recommended list)."
            ),
            "meta": {"items": _meta_items_for_products(hero_items)},
            "impact": fmt_impact_range(basis, credit_limit),
            "level": level,
        })

    # ----------------------------
    # 2) New Dealer - Low orders
    # ----------------------------
    if assigned_bucket == "NEW_LOW_ORDERS_AREA":
        gap_monthly = max(0.0, peer_monthly - dealer_monthly)
        display_gap = _display_amount(gap_monthly, floor=0.0)
        
        if gap_monthly <= 0 and peer_monthly > 0:
            gap_monthly = max(peer_monthly * 0.1, GAP_CLOSURE_FLOOR)

        display_gap = _display_amount(gap_monthly, floor=GAP_CLOSURE_FLOOR)
        basis = calc_basis(display_gap, credit_limit, floor=GAP_CLOSURE_FLOOR)

        nudges.append({
            "tag": "ORDERING_NEW_LOW_AREA",
            "nudge_type": "ordering",
            "classification": "NEW_LOW_ORDERS_AREA",
            **_obs_action(
                f"New dealer onboarded, but current billing is {fmt_currency(display_gap)} less than the average of similar dealers.",
                "Pitch Birla Opus Hero products to increase billing and bridge this gap (bill from the AI-recommended list)."
            ),
            "meta": {"items": _meta_items_for_products(hero_items)},
            "impact": fmt_impact_range(basis, credit_limit),
            "level": level,
        })

    # ----------------------------
    # 3) New Dealer - High orders (cross-sell & upsell)
    # ----------------------------
    if assigned_bucket == "NEW_HIGH_ORDERS_AREA":
        display_cat_bench = _meaningful_monthly_amount(waterproof_bench, minimum=100.0)
        if display_cat_bench <= 0:
            display_cat_bench = WATERPROOF_CATEGORY_DEFAULT

        fallback_label = waterproof_cat_label or "hero product categories"
        basis = calc_basis(display_cat_bench, credit_limit, floor=CROSS_SELL_FLOOR)

        nudges.append({
            "tag": "ORDERING_NEW_HIGH_AREA",
            "nudge_type": "ordering",
            "classification": "NEW_HIGH_ORDERS_AREA",
            **_obs_action(
                "Dealer's billing value is higher than similar dealers.",
                f"Keep up the great work!\n"
                f"Also, introduce {fallback_label}, as similar dealers are billing {fmt_currency(display_cat_bench)} from this category."
            ),
            "meta": _meta_for_category(waterproof_cat_item),
            "impact": fmt_impact_range(basis, credit_limit),
            "level": level,
        })

    # ----------------------------
    # 4) Existing Dealer - Underperformer (upsell)
    # 5) Existing Dealer - Good performer (cross-sell & upsell)
    #
    # Requirement-aligned logic:
    # - only for EXISTING dealers
    # - only when NOT already classified as INACTIVE_90D / INACTIVE_CATEGORY
    # - mutually exclusive
    # - based on GROWTH comparison only
    # ----------------------------
    if assigned_bucket == "UNDERPERFORMER_AREA":
        gap_monthly = max(0.0, peer_monthly - dealer_monthly) if peer_monthly > 0 else 0.0
        if gap_monthly <= 0:
            gap_monthly = GAP_CLOSURE_FLOOR

        display_gap = _display_amount(gap_monthly, floor=GAP_CLOSURE_FLOOR)
        basis = calc_basis(display_gap, credit_limit, floor=ACTIVATION_FLOOR)

        if peer_growth_opt is not None and peer_growth_opt != 0:
            why_txt = (
                f"In the last 3 months, the dealer {_fmt_growth_phrase_only(dealer_growth)}, "
                f"whereas similar dealers {_fmt_growth_phrase(peer_growth_opt)}."
            )
        else:
            why_txt = (
                f"In the last 3 months, the dealer {_fmt_growth_phrase_only(dealer_growth)} "
                f"versus similar dealers in the Area."
            )

        nudges.append({
            "tag": "ORDERING_UNDERPERFORMER_AREA",
            "nudge_type": "ordering",
            "classification": "UNDERPERFORMER_AREA",
            **_obs_action(
                why_txt,
                f"Similar dealers are billing {fmt_currency(display_gap)} more every month. "
                f"Suggest Hero products to help close this gap (bill from the AI-recommended list)."
            ),
            "meta": {"items": _meta_items_for_products(hero_items)},
            "impact": fmt_impact_range(basis, credit_limit),
            "level": level,
        })

    elif assigned_bucket == "GOOD_PERFORMER_AREA":
        display_cat_bench = _meaningful_monthly_amount(waterproof_bench, minimum=100.0)
        if display_cat_bench <= 0:
            display_cat_bench = WATERPROOF_CATEGORY_DEFAULT

        fallback_label = waterproof_cat_label or "hero product categories"
        basis = calc_basis(display_cat_bench, credit_limit, floor=CROSS_SELL_FLOOR)

        if peer_growth_opt is not None and peer_growth_opt != 0:
            why_txt = (
                f"In the last 3 months, the dealer {_fmt_growth_phrase(dealer_growth)}, "
                f"which is better than similar dealers who {_fmt_growth_phrase_only(peer_growth_opt)}."
            )
        else:
            why_txt = (
                f"In the last 3 months, the dealer {_fmt_growth_phrase(dealer_growth)} "
                f"versus similar dealers in the Area."
            )

        nudges.append({
            "tag": "ORDERING_GOOD_PERFORMER_AREA",
            "nudge_type": "ordering",
            "classification": "GOOD_PERFORMER_AREA",
            **_obs_action(
                why_txt,
                f"Great momentum!\n"
                f"Introduce {fallback_label} to build on this growth, as similar dealers are billing {fmt_currency(display_cat_bench)} every month from this category."
            ),
            "meta": _meta_for_category(waterproof_cat_item),
            "impact": fmt_impact_range(basis, credit_limit),
            "level": level,
        })
            
    # ==========================================================
    # Territory-only actions (per spec):
    #   6) ORDERING_INACTIVE_CATEGORY
    #   7) ORDERING_INACTIVE_90D
    # ==========================================================

    # 6) Inactive Product Category:
    # Spec: dealer active (billed in last 30d), but a previously purchased category not bought in last 90d.
    if assigned_bucket == "INACTIVE_CATEGORY":
        for it in inactive_cat_items:
            if not isinstance(it, dict):
                continue
            category_name = f"{(it.get('category') or '').strip()} / {(it.get('sub_category') or '').strip()}".strip(" /")
            if not category_name:
                continue

            display_cat_monthly = _meaningful_monthly_amount(
                it.get("peer_typical_monthly_sales", inactive_peer_typical),
                minimum=100.0,
            )
            if display_cat_monthly <= 0:
                display_cat_monthly = ACTIVATION_FLOOR
            basis = calc_basis(display_cat_monthly, credit_limit, floor=ACTIVATION_FLOOR)

            nudges.append({
                "tag": "ORDERING_INACTIVE_CATEGORY",
                "nudge_type": "ordering",
                "classification": "INACTIVE_CATEGORY",
                **_obs_action(
                    f"Dealer hasn't ordered {category_name} in the last 90 days (as of last month end).",
                    f"Similar dealers bill {fmt_currency(display_cat_monthly)}/month from this category. "
                    f"Encourage the dealer to reorder {category_name} to boost sales."
                ),
                "impact": fmt_impact_range(basis, credit_limit),
                "level": "territory",
                "meta": {
                    "items": [{
                        "category_code": it.get("category_code") or it.get("category_id"),
                        "category_id": it.get("category_id"),
                        "category": it.get("category"),
                        "sub_category": it.get("sub_category"),
                    }]
                },
            })

    # 7) Inactive Dealer 90d:
    # Spec: lost sales = dealer avg monthly from prev 90d (91-180) * 3 months
    if assigned_bucket == "INACTIVE_90D":
        prev_monthly = _display_amount(_dealer_prev90_monthly_runrate(dealer), floor=45_000.0)
        loss_3m = prev_monthly * 3.0
        basis = calc_basis(loss_3m, credit_limit, floor=CROSS_SELL_FLOOR)

        nudges.append({
            "tag": "ORDERING_INACTIVE_90D",
            "nudge_type": "ordering",
            "classification": "INACTIVE_90D",
            **_obs_action(
                "Dealer hasn't placed any order in the last 90 days (as of last month end).",
                f"Dealer is missing {fmt_currency(loss_3m)} in sales (based on a monthly run rate of {fmt_currency(prev_monthly)}). "
                f"Suggest Hero products (bill from the AI-recommended list)."
            ),
            "meta": {"items": _meta_items_for_products(terr_hero_items)},
            "impact": fmt_impact_range(basis, credit_limit),
            "level": "territory",
        })

    return nudges

def generate_ordering_nudges(dealer: dict) -> List[Dict[str, Any]]:
    """
    Generates ALL applicable ordering nudges (no limit),
    with BOTH territory+asm peer comparison nudges wherever relevant.
    """
    nudges: List[Dict[str, Any]] = []

    credit_limit = _to_float(safe_get(dealer, "dealer_credit_limit_effective", 0), 0.0)

    days_since_order = safe_get(dealer, "days_since_last_order", 0)
    try:
        days_since_order = int(days_since_order or 0)
    except Exception:
        days_since_order = 0

    orders_90d = safe_get(dealer, "total_orders_last_90d", 0)
    try:
        orders_90d = int(orders_90d or 0)
    except Exception:
        orders_90d = 0

    revenue_90d = _to_float(safe_get(dealer, "total_revenue_last_90d", 0), 0.0)

    dealer_growth = _growth_pct(safe_get(dealer,"pct_revenue_trend_90d_winsorized",
            safe_get(dealer, "pct_revenue_trend_90d", 0),
        )
    )
    
    tenure_days = _tenure_days(dealer)
    is_new_30d = (tenure_days is not None and tenure_days <= 30) or (safe_get(dealer, "is_new_dealer", 0) == 1)

    # IMPORTANT:
    # Existing must be the exact complement of new, otherwise unknown-tenure dealers
    # can fall into both buckets.
    is_existing = not is_new_30d

    turnover_cat = derive_dealer_turnover_category(dealer)
    turnover_hint = f" (category {turnover_cat})" if turnover_cat else ""

    terr_heroes = _get_territory_hero_names(dealer, limit=None)
    asm_heroes = _get_asm_hero_names(dealer, limit=None)

    terr_hero_str = ", ".join(terr_heroes[:3]) if terr_heroes else "Premium Emulsion, Exterior Weathercoat, Interior Primer"
    asm_hero_str = ", ".join(asm_heroes[:3]) if asm_heroes else terr_hero_str

    # terr_new_cat = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_new_categories_reco_90d", []))
    # asm_new_cat = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_new_categories_reco_90d", []))
    # waterproof_cat_item, waterproof_cat_label, waterproof_bench = _pick_hero_or_top_new_category(terr_new_cat or asm_new_cat)
    
    terr_new_cat = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_new_categories_reco_90d", []))
    asm_new_cat = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_new_categories_reco_90d", []))

    # AREA nudges must use AREA new-categories first (peers in Area), fallback to territory if missing
    waterproof_cat_item, waterproof_cat_label, waterproof_bench = _pick_hero_or_top_new_category(asm_new_cat or terr_new_cat)

    inactive_cat_items, inactive_peer_typical = _inactive_categories_info(dealer)
    # inactive_cat_names = _pick_category_names(inactive_cat_items, limit=None)
    terr_hero_items = (
        _ensure_list_of_dicts(safe_get(dealer, "llm_territory_products_in_dealer_categories", []))
        or _ensure_list_of_dicts(safe_get(dealer, "llm_territory_top_products_90d", []))
    )
    asm_hero_items = (
        _ensure_list_of_dicts(safe_get(dealer, "llm_asm_products_in_dealer_categories", []))
        or _ensure_list_of_dicts(safe_get(dealer, "llm_asm_top_products_90d", []))
    )
    
    nudges.extend(
        _make_peer_based_nudges(
            dealer=dealer,
            credit_limit=credit_limit,
            is_new_30d=is_new_30d,
            is_existing=is_existing,
            orders_90d=orders_90d,
            revenue_90d=revenue_90d,
            dealer_growth=dealer_growth,
            inactive_cat_items=inactive_cat_items,
            inactive_peer_typical=inactive_peer_typical,
            days_since_order=days_since_order,
            terr_hero_str=terr_hero_str,
            asm_hero_str=asm_hero_str,
            terr_hero_items=terr_hero_items,
            asm_hero_items=asm_hero_items,
            waterproof_cat_item=waterproof_cat_item,
            waterproof_cat_label=waterproof_cat_label,
            waterproof_bench=waterproof_bench,
            turnover_hint=turnover_hint,
            turnover_cat=turnover_cat,
        )
    )

    return nudges

# -------------------------
# Product recommendations (NO truncation) + separate Territory vs ASM nudges
# -------------------------
def generate_product_recommendations(dealer: dict) -> Dict[str, Any]:
    """
    Returns BOTH:
      - legacy name-lists for UI compatibility
      - raw item dicts preserving priority + lift for future UI upgrades
    """
    dealer_top_items = _ensure_list_of_dicts(safe_get(dealer, "llm_dealer_top_products_90d", []))
    repurchase_items = _ensure_list_of_dicts(safe_get(dealer, "llm_repurchase_recommendations", []))

    terr_in_cat_items = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_products_in_dealer_categories", []))
    terr_top_items = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_top_products_90d", []))

    asm_in_cat_items = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_products_in_dealer_categories", []))
    asm_top_items = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_top_products_90d", []))

    terr_new_cat_items = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_new_categories_reco_90d", []))
    asm_new_cat_items = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_new_categories_reco_90d", []))

    territory_heroes_items = terr_in_cat_items if terr_in_cat_items else terr_top_items
    asm_heroes_items = asm_in_cat_items if asm_in_cat_items else asm_top_items

    regularly_ordered = _pick_product_names(dealer_top_items, limit=None)
    repurchase_recs = _pick_product_names(repurchase_items, limit=None)
    territory_heroes = _pick_product_names(territory_heroes_items, limit=None)
    asm_heroes = _pick_product_names(asm_heroes_items, limit=None)

    terr_new_cats_items = [it for it in terr_new_cat_items if isinstance(it, dict)]
    asm_new_cats_items = [it for it in asm_new_cat_items if isinstance(it, dict)]

    territory_new_categories = []
    for it in terr_new_cats_items:
        cat = (it.get("category") or "").strip()
        if cat and cat not in territory_new_categories:
            territory_new_categories.append(cat)

    asm_new_categories = []
    for it in asm_new_cats_items:
        cat = (it.get("category") or "").strip()
        if cat and cat not in asm_new_categories:
            asm_new_categories.append(cat)

    return {
        "regularly_ordered": regularly_ordered,
        "repurchase_recs": repurchase_recs,
        "territory_heroes": territory_heroes,
        "area_heroes": asm_heroes,
        "territory_new_categories": territory_new_categories,
        "area_new_categories": asm_new_categories,
        "regularly_ordered_items": dealer_top_items,
        "repurchase_recs_items": repurchase_items,
        "territory_heroes_items": territory_heroes_items,
        "area_heroes_items": asm_heroes_items,
        "territory_new_categories_items": terr_new_cats_items,
        "area_new_categories_items": asm_new_cats_items,
    }


def _format_lines(items: List[dict], max_lines: int = 8) -> str:
    """
    Pretty multi-line formatting.
    Shows first N lines + “(+X more)” summary.
    """
    lines = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        line = _fmt_reco_line(it)
        if line:
            lines.append(f"- {line}")

    if not lines:
        return ""

    if len(lines) <= max_lines:
        return "\n".join(lines)

    head = "\n".join(lines[:max_lines])
    return f"{head}\n- (+{len(lines) - max_lines} more)"


def generate_product_rec_nudges_as_actions(dealer: dict) -> List[Dict[str, Any]]:
    """
    Emits separate nudges/sections with PRIORITY preserved (from snapshot).
    """
    prod = generate_product_recommendations(dealer)
    nudges: List[Dict[str, Any]] = []

    mo_items = prod.get("regularly_ordered_items") or []
    if mo_items:
        nudges.append(
            {
                "tag": "PRODREC_DEALER_MOST_ORDERED",
                "nudge_type": "product_reco",
                "classification": "MOST_ORDERED",
                "level": "dealer",
                "why": "Top products this dealer already sells - defend share & ensure replenishment.",
                "do": _format_lines(mo_items, max_lines=8) or ("- " + ", ".join(prod.get("regularly_ordered") or [])),
                "impact": None,
            }
        )

    rp_items = prod.get("repurchase_recs_items") or []
    if rp_items:
        nudges.append(
            {
                "tag": "PRODREC_DEALER_REPURCHASE",
                "nudge_type": "product_reco",
                "classification": "REPURCHASE",
                "level": "dealer",
                "why": "Products likely due based on repurchase cycle & delay ratio.",
                "do": _format_lines(rp_items, max_lines=8) or ("- " + ", ".join(prod.get("repurchase_recs") or [])),
                "impact": None,
            }
        )

    terr_hero_items = prod.get("territory_heroes_items") or []
    terr_newcat_items = prod.get("territory_new_categories_items") or []
    if terr_hero_items or terr_newcat_items:
        sections = []
        if terr_hero_items:
            sections.append("**Territory heroes (within dealer categories):**\n" + (_format_lines(terr_hero_items, max_lines=8) or ""))
        if terr_newcat_items:
            sections.append("**Territory new categories (outside dealer categories):**\n" + (_format_lines(terr_newcat_items, max_lines=6) or ""))
        nudges.append(
            {
                "tag": "PRODREC_TERRITORY",
                "nudge_type": "product_reco",
                "classification": "TERRITORY_PRODUCTS",
                "level": "territory",
                "why": "Territory benchmark opportunities - includes priority (HIGH/MODERATE/LOW) from snapshot.",
                "do": "\n\n".join([s for s in sections if s.strip()]).strip(),
                "impact": None,
            }
        )

    asm_hero_items = prod.get("area_heroes_items") or []
    asm_newcat_items = prod.get("area_new_categories_items") or []
    if asm_hero_items or asm_newcat_items:
        sections = []
        if asm_hero_items:
            sections.append("**Area heroes (within dealer categories):**\n" + (_format_lines(asm_hero_items, max_lines=8) or ""))
        if asm_newcat_items:
            sections.append("**Area new categories (outside dealer categories):**\n" + (_format_lines(asm_newcat_items, max_lines=6) or ""))
        nudges.append(
            {
                "tag": "PRODREC_AREA",
                "nudge_type": "product_reco",
                "classification": "AREA_PRODUCTS",
                "level": "area",
                "why": "AREA benchmark opportunities - includes priority (HIGH/MODERATE/LOW) from snapshot.",
                "do": "\n\n".join([s for s in sections if s.strip()]).strip(),
                "impact": None,
            }
        )

    return nudges


# -------------------------
# Main entry point
# -------------------------
def generate_rule_nudges(dealer: dict) -> List[Dict[str, Any]]:
    """
    Returns ALL applicable nudges (no limit):
    - Payments: all applicable (overlaps allowed)
    - Ordering: all applicable (territory + asm comparisons) + optional ASM cadence
    - Product reco: optional (keep commented if your app renders separately)
    """
    nudges: List[Dict[str, Any]] = []

    # Payments (multi)
    # nudges.extend(generate_payment_nudges(dealer))

    # Ordering (multi)
    nudges.extend(generate_ordering_nudges(dealer))

    # Product reco (optional: uncomment if you want them inside the same actions feed)
    # nudges.extend(generate_product_rec_nudges_as_actions(dealer))
    
    return nudges


# -------------------------
# UI payload helper (top3 w/ explainers) - unchanged
# -------------------------
def _priority_rank(p: Any) -> int:
    s = str(p or "").strip().upper()
    return {"HIGH": 3, "MODERATE": 2, "LOW": 1}.get(s, 0)


def _top3_by_priority(items: List[dict]) -> List[dict]:
    def key(it: dict):
        pr = _priority_rank(it.get("priority"))
        lift = it.get("estimated_revenue_lift") or it.get("benchmark_monthly_category_sales") or it.get("sales_90d") or 0
        try:
            lift = float(lift or 0)
        except Exception:
            lift = 0.0
        return (pr, lift)

    items2 = [it for it in (items or []) if isinstance(it, dict)]
    items2.sort(key=key, reverse=True)
    return items2[:3]


def _name(it: dict) -> str:
    for k in ("product", "base_product_name", "product_name", "name", "sku_name"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    v = it.get("category")
    return v.strip() if isinstance(v, str) else "N/A"


def _explain_top_product(it: dict) -> str:
    share = it.get("revenue_share_pct")
    sales = it.get("sales_90d")
    orders = it.get("orders_90d")
    aov = it.get("avg_order_value")
    parts = []
    try:
        if share is not None:
            parts.append(f"{float(share):.0f}% of 90d revenue")
    except Exception:
        pass
    try:
        if orders is not None:
            parts.append(f"{int(float(orders))} orders")
    except Exception:
        pass
    try:
        if sales is not None and float(sales) > 0:
            parts.append(f"Rs. {float(sales):,.0f} sales (90d)")
    except Exception:
        pass
    try:
        if aov is not None and float(aov) > 0:
            parts.append(f"AOV Rs. {float(aov):,.0f}")
    except Exception:
        pass
    return " • ".join(parts) if parts else "High dealer affinity product (based on last 90 days)"


def _explain_repurchase(it: dict, dealer: dict) -> str:
    cycle = it.get("repurchase_cycle_days") or it.get("avg_cycle_days") or it.get("cycle_days")
    delay = it.get("delay_days")
    ratio = it.get("delay_ratio")
    last_dt = it.get("last_purchase_date")

    parts = []
    try:
        if last_dt:
            parts.append(f"Last bought: {str(last_dt)[:10]}")
    except Exception:
        pass
    try:
        if cycle is not None and float(cycle) > 0:
            parts.append(f"Cycle: {float(cycle):.0f}d")
    except Exception:
        pass
    try:
        if delay is not None and float(delay) > 0:
            parts.append(f"Overdue by {float(delay):.0f}d")
    except Exception:
        pass
    try:
        if ratio is not None and float(ratio) > 0:
            parts.append(f"Delay ratio {float(ratio):.1f}x")
    except Exception:
        pass

    if not parts:
        dsl = safe_get(dealer, "days_since_last_order", None)
        avg_gap = safe_get(dealer, "avg_order_gap_180d", None)
        try:
            if dsl is not None and avg_gap is not None and float(avg_gap) > 0:
                parts.append(f"Dealer last order {int(float(dsl))}d ago vs typical {int(float(avg_gap))}d")
        except Exception:
            pass

    return " • ".join(parts) if parts else "Likely due for replenishment (repurchase signal)"


def _explain_hero(it: dict) -> str:
    pr = (it.get("priority") or "").strip()
    peers = it.get("percent_peers_stocking") or it.get("percent_peers_buying")
    lift = it.get("estimated_revenue_lift")
    low = it.get("estimated_revenue_lift_low")
    high = it.get("estimated_revenue_lift_high")

    parts = []
    if pr:
        parts.append(f"Priority: {pr}")
    try:
        if peers is not None:
            parts.append(f"{float(peers):.0f}% peers stock/buy")
    except Exception:
        pass
    try:
        if lift is not None and float(lift) > 0:
            if low and high:
                parts.append(f"Lift {fmt_currency(float(lift))} ({fmt_currency(float(low))}-{fmt_currency(float(high))})")
            else:
                parts.append(f"Lift {fmt_currency(float(lift))}")
    except Exception:
        pass
    return " • ".join(parts) if parts else "High performer in similar dealers (territory/Area benchmark)"


def generate_product_rec_nudges(dealer: dict) -> Dict[str, Any]:
    """
    UI payload for Product Recommendations section.
    Returns 6 sections, each with top3 items + explainers + priority.
    """
    dealer_top = _ensure_list_of_dicts(safe_get(dealer, "llm_dealer_top_products_90d", []))
    repurchase = _ensure_list_of_dicts(safe_get(dealer, "llm_repurchase_recommendations", []))

    terr_heroes_src = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_products_in_dealer_categories", [])) or \
                      _ensure_list_of_dicts(safe_get(dealer, "llm_territory_top_products_90d", []))

    asm_in_cat_only = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_products_in_dealer_categories", []))
    asm_top_only = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_top_products_90d", []))
    asm_heroes_src = asm_in_cat_only or asm_top_only

    terr_newcats = _ensure_list_of_dicts(safe_get(dealer, "llm_territory_new_categories_reco_90d", []))
    asm_newcats = _ensure_list_of_dicts(safe_get(dealer, "llm_asm_new_categories_reco_90d", []))

    top_most = _top3_by_priority(dealer_top)
    top_rep = _top3_by_priority(repurchase)
    top_th = _top3_by_priority(terr_heroes_src)
    top_tnc = _top3_by_priority(terr_newcats)
    top_ah = _top3_by_priority(asm_heroes_src)
    top_asm_top = _top3_by_priority(asm_top_only)
    top_asm_in_cat = _top3_by_priority(asm_in_cat_only)
    top_anc = _top3_by_priority(asm_newcats)[:1]

    def to_ui(items: List[dict], explainer_fn):
        out = []
        for it in items:
            out.append(
                {
                    "name": _name(it),
                    "priority": (it.get("priority") or "").strip().upper(),
                    "why": explainer_fn(it),
                    "raw": it,
                }
            )
        return out

    return {
        "dealer_most_ordered": to_ui(top_most, _explain_top_product),
        "dealer_repurchase": to_ui(top_rep, lambda it: _explain_repurchase(it, dealer)),
        "territory_heroes": to_ui(top_th, _explain_hero),
        "territory_new_categories": to_ui(top_tnc, _explain_hero),
        "area_heroes": to_ui(top_ah, _explain_hero),
        "asm_hero_top": to_ui(top_asm_top, _explain_hero),
        "asm_hero_in_dealer_categories": to_ui(top_asm_in_cat, _explain_hero),
        "area_new_categories": to_ui(top_anc, _explain_hero),
    }
