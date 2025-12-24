# utils/app_nudges.py
from __future__ import annotations

import os
import math
import re
import time
import copy
from nudge_tag import (
    TAG_SCHEMA,
    get_tag_family,
    assign_rule_tag_v2,
    assign_llm_tag,
    get_strength_for_tag,
)

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except Exception:
    jsonschema = None
    _HAS_JSONSCHEMA = False
import logging
from typing import Any, List, Optional

from utils import app_utils as U

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Lang model client - may not be installed in some environments.
ChatGoogleGenerativeAI: Optional[Any] = None
try:
    from langchain_google_genai import ChatGoogleGenerativeAI as _ChatGoogleGenerativeAI
    ChatGoogleGenerativeAI = _ChatGoogleGenerativeAI
except Exception:
    ChatGoogleGenerativeAI = None

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------
def _nice_round(v: float) -> float:
    if v <= 0:
        return 0.0
    magnitude = 10 ** (len(str(int(v))) - 1)
    return round(v / magnitude) * magnitude

def _impact_range(v: float) -> str:
    v = U.to_float(v or 0.0, 0.0)
    v = _nice_round(v)
    lo, hi = 0.8 * v, 1.2 * v
    return f"~₹{lo:,.0f}-₹{hi:,.0f}"

def _extract_json_object(text: str) -> Optional[str]:
    """
    Best-effort extraction of the first JSON object from a model response.
    Handles cases where the model adds extra text or markdown fences.
    """
    if not text or not isinstance(text, str):
        return None

    # Remove common markdown fences
    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    # Try fenced code block first
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()

    # Fallback: find a balanced JSON object by scanning for matching braces
    start_idx = cleaned.find("{")
    if start_idx == -1:
        return None

    depth = 0
    for i in range(start_idx, len(cleaned)):
        ch = cleaned[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                # return the balanced JSON substring
                return cleaned[start_idx: i + 1]

    return None


def _validate_llm_insights(insights: dict) -> bool:
    """Basic validation for LLM JSON: must be a dict with an 'actions' list of action dicts.
    Each action should contain at least 'do' and 'primary_tag'."""
    if not isinstance(insights, dict):
        return False
    actions = insights.get("actions")
    if not isinstance(actions, list) or len(actions) == 0:
        return False
    for a in actions:
        if not isinstance(a, dict):
            return False
        if "do" not in a or "primary_tag" not in a:
            return False
    return True


def _safe_llm_impact(dealer: dict, action: dict) -> str:
    """
    Ensure LLM actions always have an impact range.
    If model doesn't provide it (or provides invalid), compute conservative range from:
    - typical_invoice (preferred)
    - baseline_monthly_sales (fallback)
    """
    raw = (action or {}).get("impact", "") or ""
    if isinstance(raw, str) and "~₹" in raw:
        return raw

    total_rev_90d = U.to_float(U.safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    total_orders_90d = U.to_int(U.safe_get(dealer, "total_orders_last_90d", 0), 0)

    avg_order_value_90d = U.to_float(U.safe_get(dealer, "avg_order_value_last_90d", 0.0), 0.0)
    typical_invoice = avg_order_value_90d if avg_order_value_90d > 0 else (
        (total_rev_90d / total_orders_90d) if total_orders_90d > 0 else 0.0
    )

    baseline_monthly_sales = (total_rev_90d / 3.0) if total_rev_90d > 0 else 0.0
    basis = typical_invoice if typical_invoice > 0 else max(8000.0, 0.2 * baseline_monthly_sales)
    return f"{_impact_range(basis)} this month (basis conservative)"


def _why_from_tag(dealer: dict, tag: str) -> str:
    dsl = U.to_int(dealer.get("days_since_last_order") or 0, 0)
    churn = U.to_float(dealer.get("order_churn_risk_score") or 0, 0.0)
    trend = U.to_float(dealer.get("pct_revenue_trend_90d") or 0, 0.0)

    if tag == "CHURN_RISK_INACTIVE_90D":
        return f"Dealer inactive for {dsl} days; high risk of churn."
    if tag == "CHURN_RISK_HIGH_SCORE":
        return f"High churn risk score ({churn:.2f}); needs immediate follow-up."
    if tag == "SALES_DROP_SHARP":
        return f"Revenue trend is down {abs(trend):.0f}% (90d); needs correction."
    if tag == "PRODUCT_VARIETY_LOW":
        return "Limited product variety vs peers; expanding range can lift invoice value."
    return "Rule trigger matched based on dealer's recent performance signals."


def _estimate_rule_impact(dealer: dict, tag: str) -> str:
    tiv = U.to_float(dealer.get("avg_invoice_value_90d") or dealer.get("typical_invoice_size") or 0, 0.0)
    monthly_rev = U.to_float(dealer.get("total_revenue_last_90d") or 0, 0.0) / 3.0
    gap_to_cluster = U.to_float(dealer.get("revenue_gap_vs_cluster_avg_monthly_last_90d") or 0, 0.0)

    if tag in {"CHURN_RISK_INACTIVE_90D", "CHURN_RISK_HIGH_SCORE", "NEW_DEALER_NO_ORDERS"}:
        basis = tiv if tiv > 0 else max(5000.0, 0.2 * monthly_rev)
        return f"{_impact_range(basis)} this month (basis first reactivation order)"

    if tag in {"GROWTH_OPPORTUNITY_BELOW_CLUSTER", "GROWTH_GAP_TO_CLUSTER"} and gap_to_cluster > 0:
        basis = min(gap_to_cluster, monthly_rev * 0.3 if monthly_rev > 0 else gap_to_cluster)
        return f"{_impact_range(basis)} this month (basis partial gap recovery)"

    basis = tiv if tiv > 0 else 8000.0
    return f"{_impact_range(basis)} this month (basis conservative add-on)"


# --------------------------------------------------------------------------------------
# RULE: Sub-brand nudges (kept as-is, with light hygiene)
# --------------------------------------------------------------------------------------
def get_subbrand_nudges(dealer: dict, enabled: bool = True) -> List[dict]:
    if not enabled:
        return []

    total_rev_180d = U.to_float(U.safe_get(dealer, "total_revenue_180d", 0.0), 0.0)
    if total_rev_180d < 100000:
        return []

    actions: List[dict] = []
    subbrand_shares = {
        "Allwood": U.to_float(U.safe_get(dealer, "share_revenue_allwood_180d", 0.0), 0.0),
        "Prime": U.to_float(U.safe_get(dealer, "share_revenue_prime_180d", 0.0), 0.0),
        "Allwood Pro": U.to_float(U.safe_get(dealer, "share_revenue_allwoodpro_180d", 0.0), 0.0),
        "One": U.to_float(U.safe_get(dealer, "share_revenue_one_180d", 0.0), 0.0),
        "Calista": U.to_float(U.safe_get(dealer, "share_revenue_calista_180d", 0.0), 0.0),
        "Style": U.to_float(U.safe_get(dealer, "share_revenue_style_180d", 0.0), 0.0),
        "AllDry": U.to_float(U.safe_get(dealer, "share_revenue_alldry_180d", 0.0), 0.0),
        "Artist": U.to_float(U.safe_get(dealer, "share_revenue_artist_180d", 0.0), 0.0),
        "Sample Kit": U.to_float(U.safe_get(dealer, "share_revenue_samplekit_180d", 0.0), 0.0),
        "Collaterals": U.to_float(U.safe_get(dealer, "share_revenue_collaterals_180d", 0.0), 0.0),
    }

    dominant_brand, dominant_share = max(subbrand_shares.items(), key=lambda kv: kv[1])
    if dominant_share <= 0.5:
        return actions

    dominant_pct = dominant_share * 100

    if dominant_brand == "Style":
        actions.append({
            "key": "SUBBRAND_DOMINANT_STYLE",
            "priority": 30,
            "text": (
                f"Mix Upgrade: {dominant_pct:.0f}% sales are 'Style'. "
                "Pitch 'Calista' as a longer-lasting finish for upgrade buyers."
            ),
            "tag": "SUBBRAND_DOMINANT_STYLE"
        })
    elif dominant_brand == "Calista":
        actions.append({
            "key": "SUBBRAND_DOMINANT_CALISTA",
            "priority": 30,
            "text": (
                f"Premium Push: 'Calista' is ~{dominant_pct:.0f}% of revenue. "
                "Show 'One' shade cards to premium clients for top-tier projects."
            ),
            "tag": "SUBBRAND_DOMINANT_CALISTA"
        })
    elif dominant_brand == "One":
        actions.append({
            "key": "SUBBRAND_DOMINANT_ONE",
            "priority": 30,
            "text": (
                f"Protect Premium: 'One' is {dominant_pct:.0f}% of sales. "
                "Ensure full SKU range availability so they don't switch brands."
            ),
            "tag": "SUBBRAND_DOMINANT_ONE"
        })
    else:
        actions.append({
            "key": "SUBBRAND_DOMINANT_OTHER",
            "priority": 25,
            "text": (
                f"Mix Risk: ~{dominant_pct:.0f}% revenue depends on {dominant_brand}. "
                "Use this strength to open 1-2 more sub-brands (reduce dependency)."
            ),
            "tag": "SUBBRAND_DOMINANT_OTHER"
        })

    return actions

# --------------------------------------------------------------------------------------
# RULE: Collections nudges (Overdue ALWAYS first if > 0)
# --------------------------------------------------------------------------------------
def generate_collections_nudges(dealer: dict) -> List[dict]:
    actions: List[dict] = []

    due_today = U.to_float(dealer.get("due_today_total", 0), 0.0)
    due_tomorrow = U.to_float(dealer.get("due_tomorrow_total", 0), 0.0)
    due_in7 = U.to_float(dealer.get("due_in7_total", 0), 0.0)
    overdue_amt = U.to_float(dealer.get("overdue_amt_total", 0), 0.0)
    os_amt = U.to_float(dealer.get("os_amt_total", 0), 0.0)

    # ABSOLUTE PRIORITY: Overdue
    if overdue_amt > 0:
        actions.append({
            "text": (
                f"Collections Alert: ₹{overdue_amt:,.0f} OVERDUE. "
                "Visit dealer today - understand reason (dispute/cash flow/missed reminder), "
                "negotiate partial payment if needed, lock payment date."
            ),
            "priority": 10_000,  # ensure first globally
            "key": "COLLECTIONS_OVERDUE",
            "tag": "OVERDUE_HIGH_AMOUNT"
        })
        return actions  # keep ONLY this as the top collections nudge (you can change if you want more)

    # Next priorities if not overdue
    if due_today > 0:
        actions.append({
            "text": (
                f"Collections URGENT: ₹{due_today:,.0f} payment due TODAY. "
                "Call dealer immediately - confirm payment status and mode (NEFT/cheque/cash). "
                "If delayed, get commitment for tomorrow with exact time."
            ),
            "priority": 200,
            "key": "COLLECTIONS_DUE_TODAY",
            "tag": "OVERDUE_DUE_TODAY"
        })
    elif due_tomorrow > 0:
        actions.append({
            "text": (
                f"Collections Reminder: ₹{due_tomorrow:,.0f} due tomorrow. "
                "Call dealer today for proactive reminder - confirm they have funds ready."
            ),
            "priority": 150,
            "key": "COLLECTIONS_DUE_TOMORROW",
            "tag": "OVERDUE_DUE_TOMORROW"
        })
    elif due_in7 > 0:
        actions.append({
            "text": (
                f"Collections Watch: ₹{due_in7:,.0f} due within 7 days. "
                "Courtesy call - remind dealer of upcoming payment, ask if any issues expected."
            ),
            "priority": 50,
            "key": "COLLECTIONS_DUE_IN_7",
            "tag": "OVERDUE_DUE_IN_7_DAYS"
        })
    elif os_amt > 100000:
        actions.append({
            "text": (
                f"High Outstanding: ₹{os_amt:,.0f} total OS (not yet overdue). "
                "Regular follow-up call - maintain relationship, ensure timely payment culture."
            ),
            "priority": 50,
            "key": "COLLECTIONS_HIGH_OS",
            "tag": "OVERDUE_OS_HIGH"
        })

    return actions


# --------------------------------------------------------------------------------------
# RULE: Main rule nudges (updated to match your rule categories + ensure collections-first)
# --------------------------------------------------------------------------------------
def generate_rule_nudges(dealer: dict, max_actions: int = 2) -> List[dict]:
    raw_actions: List[dict] = []

    def add_action(text: str, priority: int, key: str, tag: Optional[str] = None):
        raw_actions.append({
            "text": text,
            "priority": priority,
            "key": key,
            "tag": tag
        })

    # 0) Collections (overdue > 0 becomes absolute first)
    raw_actions.extend(generate_collections_nudges(dealer))

    # Basic flags
    is_new_flag = U.to_int(U.safe_get(dealer, "is_new_dealer", 0), 0)
    has_no_orders_flag = U.to_int(U.safe_get(dealer, "has_no_orders", 0), 0)
    total_orders_lifetime = U.to_int(U.safe_get(dealer, "total_orders_lifetime", 0), 0)
    tenure_months = U.to_int(U.safe_get(dealer, "tenure_months", 9999), 9999)

    has_no_orders = (has_no_orders_flag == 1) or (total_orders_lifetime == 0)
    is_new = (is_new_flag == 1) or (tenure_months <= 1)

    dsl = U.to_int(U.safe_get(dealer, "days_since_last_order", 0), 0)

    # Trends
    rev_30 = U.to_float(U.safe_get(dealer, "total_revenue_last_30d", 0.0), 0.0)
    prev_30 = U.to_float(U.safe_get(dealer, "total_revenue_prev_30d", 0.0), 0.0)
    rev_trend_30 = ((rev_30 - prev_30) / prev_30 * 100) if prev_30 > 0 else U.to_float(
        U.safe_get(dealer, "pct_revenue_trend_30d", 0.0), 0.0
    )

    rev_90 = U.to_float(U.safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    prev_90 = U.to_float(U.safe_get(dealer, "total_revenue_prev_90d", 0.0), 0.0)
    rev_trend_90 = ((rev_90 - prev_90) / prev_90 * 100) if prev_90 > 0 else U.to_float(
        U.safe_get(dealer, "pct_revenue_trend_90d", 0.0), 0.0
    )

    churn_risk = U.to_float(U.safe_get(dealer, "order_churn_risk_score", 0.0), 0.0)
    dropping_off = U.to_int(U.safe_get(dealer, "dealer_is_dropping_off", 0), 0)

    gap_to_cluster = U.to_float(U.safe_get(dealer, "revenue_gap_vs_cluster_avg_monthly_last_90d", 0.0), 0.0)
    cluster_avg_monthly = U.to_float(U.safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", 0.0), 0.0)
    territory_avg_monthly = U.to_float(U.safe_get(dealer, "territory_avg_monthly_revenue_last_90d", 0.0), 0.0)
    avg_monthly_180d = U.to_float(U.safe_get(dealer, "avg_monthly_revenue_180d", 0.0), 0.0)

    baseline_monthly = max(
        (rev_90 / 3.0) if rev_90 > 0 else 0.0,
        (prev_90 / 3.0) if prev_90 > 0 else 0.0,
        avg_monthly_180d,
        territory_avg_monthly,
        cluster_avg_monthly,
        45000.0
    )

    # 1) Ordering Pattern rules (your table)
    if is_new and has_no_orders:
        potential = max(cluster_avg_monthly, territory_avg_monthly, 0.0)
        add_action(
            text=(
                "New dealer onboarded - but no orders yet. "
                f"Start with territory hero products (Premium Emulsion, Exterior Weathercoat, Interior Primer) "
                f"+ early-bird scheme; target first invoice this week (peer potential ~{U.fmt_rs(potential)}/month)."
            ),
            priority=800,
            key="OP_NEW_NO_ORDERS",
            tag=None
        )
    elif dsl >= 90:
        months_lost = min(3, max(1, math.ceil(dsl / 30)))
        lost_sales = baseline_monthly * months_lost
        add_action(
            text=(
                f"Dealer inactive for {dsl} days—no orders placed. "
                f"Call/visit today, diagnose (stock stuck vs competitor vs pipeline), "
                f"and book a restart order (at risk ~{U.fmt_rs(lost_sales)})."
            ),
            priority=750 + (50 if churn_risk > 1.0 or dropping_off == 1 else 0),
            key="OP_INACTIVE_90D",
            tag=None
        )
    else:
        # Underperformer upsell (growth lagging)
        if rev_trend_30 <= -20:
            add_action(
                text=(
                    f"Billing down {abs(rev_trend_30):.0f}% vs last month. "
                    "Visit this week, check competitor switch/stock issues, "
                    "and close one replenishment order with hero SKUs."
                ),
                priority=650,
                key="OP_UNDERPERFORMER_DROP_30D",
                tag=None
            )

        # Gap-to-peers upsell (only if not crashing badly)
        if gap_to_cluster > 5000 and rev_trend_30 > -25:
            add_action(
                text=(
                    f"Billing is {U.fmt_rs(abs(gap_to_cluster))} below peer avg. "
                    "Compare peer basket and push 2 missing fast movers to close gap this month."
                ),
                priority=600,
                key="OP_GAP_TO_PEERS",
                tag=None
            )

        # Good performer cross/upsell
        if rev_trend_90 > 20 and gap_to_cluster <= 0:
            add_action(
                text=(
                    f"Up {rev_trend_90:.0f}% vs previous 90 days and above peers. "
                    "Appreciate + introduce waterproofing/premium line to expand wallet share."
                ),
                priority=520,
                key="OP_GOOD_PERFORMER",
                tag=None
            )

    # 2) Sub-brand nudges (only when not in activation/inactive/decline mode)
    enable_subbrand = (not has_no_orders) and (dsl < 60) and (rev_trend_30 > -15)
    raw_actions.extend(get_subbrand_nudges(dealer, enabled=enable_subbrand))

    # Fallback if nothing
    if not raw_actions:
        add_action(
            text="Visit the dealer to identify gaps, preferences and competition.",
            priority=10,
            key="GENERIC_VISIT",
            tag="CROSS_SELL_CATEGORY"
        )

    # Rank + dedupe + cap (keep top max_actions, BUT if collections overdue exists, it stays)
    raw_actions = sorted(raw_actions, key=lambda x: x.get("priority", 0), reverse=True)

    # Always keep the first action if it's the overdue alert
    must_keep_key = "COLLECTIONS_OVERDUE" if raw_actions and raw_actions[0].get("key") == "COLLECTIONS_OVERDUE" else None

    seen = set()
    final_raw: List[dict] = []
    for a in raw_actions:
        k = a.get("key") or a.get("tag") or a.get("text")
        if k in seen:
            continue
        seen.add(k)
        final_raw.append(a)

        if must_keep_key and a.get("key") == must_keep_key:
            continue  # don't count against cap for the overdue slot

        # cap rule actions excluding mandatory overdue slot
        effective_len = len([x for x in final_raw if x.get("key") != must_keep_key])
        if effective_len >= max_actions:
            break

    # Tagging + normalization to standard schema (fill LLM fields even for RULE)
    tagged_actions: List[dict] = []
    for item in final_raw:
        action_text = item.get("text", "")
        tag = item.get("tag")

        if not tag or tag not in TAG_SCHEMA:
            rule_tag, rule_conf = assign_rule_tag_v2(action_text, dealer)
            tag = rule_tag
        else:
            rule_conf = 0.90

        do = action_text
        why = _why_from_tag(dealer, tag)
        impact = _estimate_rule_impact(dealer, tag)

        tagged_actions.append({
            "do": do,
            "why": why,
            "impact": impact,

            "tag": tag,
            "tag_family": get_tag_family(tag),
            "priority_base": TAG_SCHEMA.get(tag, TAG_SCHEMA.get("LLM_GENERAL", {})).get("priority_base", 0),
            "strength_score": get_strength_for_tag(tag),

            "llm_primary_tag": tag,  # filled for rule too (schema consistency)
            "llm_tag_confidence": U.to_float(rule_conf, 0.0),
            "llm_tag_basis": f"rule_engine; tag={tag}",
        })

    return tagged_actions


# --------------------------------------------------------------------------------------
# LLM Nudges
# --------------------------------------------------------------------------------------
ALLOWED_LLM_PRIMARY_TAGS = {
    "LLM_REPURCHASE_DUE",
    "LLM_INACTIVE_CATEGORY",
    "LLM_CROSS_SELL",
    "LLM_TERRITORY_HERO",
    "LLM_GENERAL",
}


def get_context(dealer: dict) -> str:
    is_new = U.to_int(U.safe_get(dealer, "is_new_dealer", 0), 0)
    has_no_orders = U.to_int(U.safe_get(dealer, "has_no_orders", 0), 0)
    days_since_last_order = U.to_int(U.safe_get(dealer, "days_since_last_order", 9999), 9999)
    days_until_expected_order = U.to_int(U.safe_get(dealer, "days_until_expected_order", 9999), 9999)
    trend_90d = U.to_float(U.safe_get(dealer, "pct_revenue_trend_90d", 0.0), 0.0)
    # Expose trend 30d (if available)
    trend_30d = U.to_float(U.safe_get(dealer, "pct_revenue_trend_30d", 0.0), 0.0) 
    dropping_off = U.to_int(U.safe_get(dealer, "dealer_is_dropping_off", 0), 0)
    churn_risk = U.to_float(U.safe_get(dealer, "order_churn_risk_score", 0.0), 0.0)

    dealer_top = U.ensure_list(dealer.get("llm_dealer_top_products_90d"))
    terr_hero = U.ensure_list(dealer.get("llm_territory_top_products_90d"))
    cross_sell = U.ensure_list(dealer.get("llm_territory_products_in_dealer_categories"))
    repurchase = U.ensure_list(dealer.get("llm_repurchase_recommendations"))
    inactive_cats = U.ensure_list(dealer.get("llm_inactive_categories_90d"))

    total_rev_90d = U.to_float(U.safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    total_orders_90d = U.to_int(U.safe_get(dealer, "total_orders_last_90d", 0), 0)
    # Expose Zero Activity Flag
    flag_zero_activity_90d = U.to_int(U.safe_get(dealer, "flag_zero_activity_90d", 0), 0)

    baseline_monthly_sales = (total_rev_90d / 3.0) if total_rev_90d > 0 else 0.0
    baseline_orders_per_month = (total_orders_90d / 3.0) if total_orders_90d > 0 else 0.0

    avg_order_value_90d = U.to_float(U.safe_get(dealer, "avg_order_value_last_90d", 0.0), 0.0)
    typical_invoice = avg_order_value_90d if avg_order_value_90d > 0 else (
        (total_rev_90d / total_orders_90d) if total_orders_90d > 0 else 0.0
    )

    cluster_avg_monthly = U.to_float(U.safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", 0.0), 0.0)
    territory_avg_monthly = U.to_float(U.safe_get(dealer, "territory_avg_monthly_revenue_last_90d", 0.0), 0.0)

    dealer_type = "NEW DEALER (Last 30 days)" if is_new == 1 else "EXISTING DEALER"
    order_status = "NO ORDERS YET" if has_no_orders == 1 else f"{total_orders_90d} orders in 90d"

    summary_block = f"""
DEALER TYPE: {dealer_type}
ORDER STATUS: {order_status}

DEALER BASICS
- Name: {dealer.get('customer_name', 'N/A')}
- Location: {dealer.get('city_name','')}, {dealer.get('state_name','')}
- Segment (OP): {dealer.get('dealer_segment_OP', 'N/A')}
- Segment (BG): {dealer.get('dealer_segment_BG', 'N/A')}
- Tenure: {U.to_int(U.safe_get(dealer, 'tenure_months', 0), 0)} months

BASELINE (MONTHLY)
- Sales / month (last 90d avg): {U.fmt_rs(baseline_monthly_sales)}
- Orders / month (last 90d avg): {baseline_orders_per_month:.1f}
- Typical invoice size: {U.fmt_rs(typical_invoice)}
- Days since last order: {days_since_last_order if has_no_orders == 0 else "N/A"}
- Expected next order in: {days_until_expected_order} days
- Orders in last 90d: {total_orders_90d}
- Zero activity flag (90d): {U.flag_text(flag_zero_activity_90d)}
- Revenue trend (90d): {trend_90d:.0f}%
- Revenue trend (30d): {trend_30d:.0f}%

BENCHMARKS (context only)
- Cluster avg monthly: {U.fmt_rs(cluster_avg_monthly)}
- Territory avg monthly: {U.fmt_rs(territory_avg_monthly)}

RISK
- Churn risk: {churn_risk:.2f}
- Dropping off: {U.flag_text(dropping_off)}
"""

    def format_candidates(items, kind: str) -> str:
        lines = []
        for p in (items or [])[:3]:  # was [:5] → save tokens
            name = p.get("product") or p.get("base_product") or "N/A"
            brand = p.get("brand") or p.get("sub_brand") or "General"
            cat = p.get("category", "")
            sub = p.get("sub_category", "")

            if kind == "repurchase":
                lines.append(
                    f"- {name}|{brand}|{cat}/{sub}|{p.get('action','')} {p.get('urgency_level','')}|"
                    f"dsl={p.get('days_since_last_purchase','?')}|cycle={p.get('typical_cycle_days','?')}|"
                    f"aov={p.get('typical_order_value','?')}|rc={p.get('reason_code','')}"
                )

            elif kind == "terr":
                lines.append(
                    f"- {name}|{brand}|{cat}/{sub}|{p.get('recommendation_type','')}|"
                    f"lift={p.get('estimated_revenue_lift','?')}|bench={p.get('benchmark_monthly_sales','?')}|"
                    f"peers={p.get('percent_peers_stocking','?')}%|rc={p.get('reason_code','')}"
                )

            elif kind == "cross":
                lines.append(
                    f"- {name}|{brand}|{cat}/{sub}|bench={p.get('benchmark_monthly_sales','?')}|"
                    f"peers={p.get('percent_peers_stocking','?')}%|rc={p.get('reason_code','')}"
                )

            elif kind == "inactive":
                lines.append(
                    f"- {cat}/{sub}|dsl={p.get('days_since_last_purchase','?')}|"
                    f"past_mo={p.get('dealer_past_monthly_sales','?')}|peer_mo={p.get('peer_typical_monthly_sales','?')}|"
                    f"rc={p.get('reason_code','')}"
                )

            else:  # dealer_top
                lines.append(
                    f"- {name}|{brand}|{cat}/{sub}|mo={p.get('avg_monthly_sales','?')}|"
                    f"share={p.get('revenue_share_pct','?')}%|rc={p.get('reason_code','')}"
                )

        return "\n".join(lines) if lines else "None"

    product_block = f"""
PRODUCT CANDIDATES (use names exactly; do NOT invent products)

REPURCHASE (existing, due/overdue):
{format_candidates(repurchase, "repurchase")}

CROSS-SELL (new, inside dealer's strong categories):
{format_candidates(cross_sell, "cross")}

INACTIVE CATEGORY (reactivation) (NOTE: may be category-only, no product name):
{format_candidates(inactive_cats, "inactive")}

TERRITORY HERO (activation / expansion / defend share):
{format_candidates(terr_hero, "terr")}

CORE PRODUCTS (dealer already buys a lot):
{format_candidates(dealer_top, "dealer_top")}
"""

    instructions = """
You are writing for a Territory Sales Manager (TSM). Tone: simple, spoken, direct.

Return ONLY valid JSON matching the schema below. (no extra text)

TASK
Pick 2-3 actions (highest priority first). **Exception: If Dormant override triggers, return exactly 1 action.**

TAG RULES (STRICT)
- Each action MUST have exactly ONE primary_tag from:
  LLM_REPURCHASE_DUE, LLM_INACTIVE_CATEGORY, LLM_CROSS_SELL, LLM_TERRITORY_HERO, LLM_GENERAL
- MAX 1 action per primary_tag (no duplicates).
- CRITICAL BUNDLING: If you select LLM_REPURCHASE_DUE, group all available items (e.g., SEALER BASE + HARDENER) into a single, high-impact action. Bundle up to 2-3 related items for other tags.
- Prefer using at least 2 different tags when multiple buckets have good candidates (unless dealer is clearly retention-risk).
- NO OVERLAP RULE (CRITICAL):
  - Do not repeat the same category/sub-category theme across actions.
  - If you use the LLM_REPURCHASE_DUE tag for a product, you CANNOT also use the LLM_INACTIVE_CATEGORY tag for that product's category/sub-category (and vice versa). Choose the framing that yields the highest impact.
  - **CRITICAL NO OVERLAP REFINEMENT:** If you select **LLM_INACTIVE_CATEGORY**, you **MUST NOT** reference any specific product that is also flagged for **DUE_FOR_WINBACK** or **DUE_FOR_REORDER** in the `PRODUCT CANDIDATES` list within the action's `do` or `why` fields. Focus only on the category theme.

DORMANT / ZERO-ACTIVITY OVERRIDE (STRICT)
- **Check based on Summary Block fields:** If Orders in last 90d = 0 OR Days since last order >= 120 OR Zero activity flag (90d) is YES:
  - Return **EXACTLY ONE** action only.
  - primary_tag **MUST** be **LLM_GENERAL**.
  - That ONE action must include a “starter basket” (2-3 items) pulled from TERRITORY HERO and/or REPURCHASE candidates (if any).
  - Do **NOT** output **LLM_INACTIVE_CATEGORY / LLM_TERRITORY_HERO / LLM_CROSS_SELL** as separate actions for dormant dealers.

CANDIDATE FIDELITY
- Use ONLY product/category names from PRODUCT CANDIDATES. Never invent names.
- Don't recompute metrics (don't recalc % or lift). Use fields as given.

PRIORITY (HIGH-IMPACT ORDER)
1. **CRITICAL SECURITY (OVERRIDE):** If the dealer is DECLINING or CHURN RISK is high, you MUST prioritize **HIGH-URGENCY REPURCHASE** or a **DEFEND SHARE** action as Action 1.
1a. **DEFEND CORE REVENUE (REQUIRED ACTION 1 or 2):** For declining or high-churn dealers, Action 1 or 2 **MUST** be a **DEFEND SHARE** action (Securing *LLM_DEALER_TOP_PRODUCTS* or *LLM_TERRITORY_HERO* with lift = 0). Frame this using **LLM_TERRITORY_HERO** or **LLM_GENERAL**.
2. **SECURE/RECOVER:** If REPURCHASE has WINBACK/HIGH/overdue, or INACTIVE CATEGORY has a high peer gap, prioritize these (highest impact first).
3. **DECLINING / HIGH-RISK GUARDRAIL:** If Revenue trend (30d) <= -20% OR Churn risk > 1.0 OR Dropping off is YES: Do **NOT** use **LLM_CROSS_SELL** unless no repurchase/defend candidates exist.
4. **ACTIVATE/EXPAND:** For others, use CROSS-SELL / TERRITORY HERO for expansion only after "secure/recover" is covered.
5. New/no-orders: focus ACTIVATE first (hero starter basket).

DEFEND / ZERO-LIFT
- If recommendation_type implies DEFEND/MAINTAIN OR lift = 0:
  action must be “secure/defend” (availability, scheme, shelf share, ensure next invoice),
  and impact must be **“secured revenue”**, NOT incremental uplift.

NO UNSUPPORTED CLAIMS
Don't say “booming/growing/weak” unless you reference a signal (trend/churn/urgency/baseline). Avoid exaggerated claims (e.g., 'strong hero' for low peer adoption).

IMPACT (realistic, next 30d)
- Repurchase: use typical_order_value (sum of bundled items) as basis.
- Inactive category: partial recovery only; cap at <= past_mo and usually <= 50% of peer_mo.
- Cross/territory hero new product: trial add-on; keep conservative.
- **IMPACT FORMAT STRICT:** impact must **ALWAYS** be a range "~₹X-₹Y". If you only have one calculated value V, output "~₹(0.8V)-₹(1.2V)".
- **IMPACT FOR GENERAL/DROPPED OFF (CRITICAL):** Must provide a **numeric range** (~₹X-₹Y) based on the dealer's **Typical Invoice Size** or their **Baseline Monthly Sales** to represent the revenue secured from the first re-activation order.
- **DEFEND_SHARE IMPACT RULE (NO GUESSING):** If recommendation_type is DEFEND_SHARE or lift = 0: impact MUST be "~₹X-₹Y" and computed from **ONE** provided field only: **benchmark_monthly_sales** OR **avg_monthly_sales** (from CORE PRODUCTS) OR **typical_invoice**. tag_basis MUST include the exact field used (e.g., "bench=10230" or "dealer_top_mo=80000").

STYLE (TSM SCRIPT FORMAT MANDATORY)
- "do" must contain:
  1) a specific call/visit timing (today/this week),
  2) one diagnostic question (stock stuck? competitor? project pipeline?),
  3) one clear close (book invoice / order ₹X / 2 SKUs).
- Avoid vague verbs: "discuss", "highlight", "explore" unless paired with a specific close.
- "why" max 2 sentences; must cite 1-2 facts (days since last order/cycle/urgency/lift/rc - in simple terms).
- tag_confidence 0.60-0.95; tag_basis should include rc=...

OUTPUT JSON (STRICT)
{{
  "actions": [
    {{
      "do": "TSM-ready instruction (max 2 sentences).",
      "why": "One-line reason tied ONLY to the chosen tag and signals.",
      "impact": "~₹X-₹Y this month (basis 3-6 words)",
      "primary_tag": "LLM_...",
      "tag_confidence": 0.60,
      "tag_basis": "short basis (include reason_code if present)"
    }}
  ]
}}
"""
    return summary_block + "\n" + product_block + "\n" + instructions


# def _redact_dealer_for_llm(dealer: dict) -> dict:
#     """Return a shallow copy of dealer with PII redacted before sending to LLM.
#     Removes customer_name, city/state, asm_name and dealer ids; keeps numeric signals."""
#     if not isinstance(dealer, dict):
#         return dealer
#     d = copy.deepcopy(dealer)
#     for k in [
#         'customer_name', 'city_name', 'state_name', 'asm_name', 'dealer_composite_id', 'dealer_id', 'first_order_date', 'last_order_date'
#     ]:
#         if k in d:
#             d[k] = 'REDACTED'
#     return d


def generate_ai_nudges(dealer: dict, model=None) -> List[dict]:
    """
    Generates LLM nudges. If LLM fails, returns fallback actions (but normalized & tagged).
    """
    # Redact PII before building context sent to the LLM
    # redacted = _redact_dealer_for_llm(dealer)
    context = get_context(dealer)

    try:
        if ChatGoogleGenerativeAI is None:
            logger.warning("ChatGoogleGenerativeAI not available; using fallback actions.")
            actions = fallback_actions(dealer)
            return _tag_llm_actions(actions, dealer)

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY missing; using fallback actions.")
            actions = fallback_actions(dealer)
            return _tag_llm_actions(actions, dealer)

        if model is None:
            model = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=api_key,
                temperature=0.1,
            )

        response = model.invoke(context)
        response_text = response.content if hasattr(response, "content") else str(response)

        json_blob = _extract_json_object(response_text)
        if not json_blob:
            logger.warning("LLM response had no JSON object; saving raw and using fallback actions.")
            try:
                raw_dir = os.path.join("data", "nudges", "llm_raw")
                os.makedirs(raw_dir, exist_ok=True)
                dealer_id = str(dealer.get("dealer_composite_id") or dealer.get("dealer_id") or "unknown")
                fname = f"raw_{dealer_id}_{int(time.time())}.txt"
                with open(os.path.join(raw_dir, fname), "w", encoding="utf-8") as fh:
                    fh.write(response_text)
            except Exception:
                logger.exception("Failed to write raw LLM response")

            actions = fallback_actions(dealer)
            return _tag_llm_actions(actions, dealer)

        insights = U.parse_json_relaxed(json_blob)
        # Prefer strict jsonschema validation if available
        schema_ok = False
        if insights and isinstance(insights, dict):
            if _HAS_JSONSCHEMA:
                try:
                    # schema: top-level dict with 'actions' as array of objects with required fields
                    LLM_ACTIONS_SCHEMA = {
                        "type": "object",
                        "properties": {
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "do": {"type": "string"},
                                        "why": {"type": "string"},
                                        "impact": {"type": "string"},
                                        "primary_tag": {"type": "string"},
                                        "tag_confidence": {"type": ["number", "null"]},
                                        "tag_basis": {"type": ["string", "null"]}
                                    },
                                    "required": ["do", "primary_tag"]
                                }
                            }
                        },
                        "required": ["actions"]
                    }
                    jsonschema.validate(instance=insights, schema=LLM_ACTIONS_SCHEMA)
                    schema_ok = True
                except Exception:
                    schema_ok = False
            else:
                schema_ok = _validate_llm_insights(insights)

        if not schema_ok:
            logger.warning("LLM JSON parsed but schema invalid; saving raw and using fallback actions.")
            try:
                raw_dir = os.path.join("data", "nudges", "llm_raw")
                os.makedirs(raw_dir, exist_ok=True)
                dealer_id = str(dealer.get("dealer_composite_id") or dealer.get("dealer_id") or "unknown")
                fname = f"invalid_{dealer_id}_{int(time.time())}.txt"
                with open(os.path.join(raw_dir, fname), "w", encoding="utf-8") as fh:
                    fh.write(response_text)
            except Exception:
                logger.exception("Failed to write raw invalid LLM response")

            actions = fallback_actions(dealer)
            return _tag_llm_actions(actions, dealer)

        actions = (insights.get("actions") or [])[:3]
        return _tag_llm_actions(actions, dealer)

    except Exception as e:
        logger.exception("LLM generation failed; using fallback actions. err=%s", e)
        actions = fallback_actions(dealer)
        return _tag_llm_actions(actions, dealer)


def _tag_llm_actions(actions: List[dict], dealer: dict) -> List[dict]:
    tagged_actions: List[dict] = []

    for action in (actions or [])[:3]:
        if not isinstance(action, dict):
            action = {"do": str(action), "why": "", "impact": ""}

        llm_primary = action.get("primary_tag")
        if llm_primary not in ALLOWED_LLM_PRIMARY_TAGS:
            llm_primary = None

        # Final tag for schema (your system)
        try:
            tag = llm_primary or assign_llm_tag(action, dealer)
        except Exception:
            logger.exception("assign_llm_tag failed; falling back to LLM_GENERAL")
            tag = "LLM_GENERAL"

        if tag not in TAG_SCHEMA:
            logger.warning("Resolved tag '%s' not in TAG_SCHEMA; falling back to LLM_GENERAL", tag)
            tag = "LLM_GENERAL"

        # Coerce confidence
        try:
            conf = float(action.get("tag_confidence") or 0.0)
        except Exception:
            conf = 0.0
        conf = max(0.0, min(1.0, conf))

        tagged_actions.append({
            "do": action.get("do", ""),
            "why": action.get("why", ""),
            "impact": _safe_llm_impact(dealer, action),

            "tag": tag,
            "tag_family": get_tag_family(tag),
            "priority_base": TAG_SCHEMA.get(tag, TAG_SCHEMA.get("LLM_GENERAL", {})).get("priority_base", 0),
            "strength_score": get_strength_for_tag(tag),

            "llm_primary_tag": action.get("primary_tag"),
            "llm_tag_confidence": conf,
            "llm_tag_basis": action.get("tag_basis") or action.get("tag_basis") or "",
        })

    return tagged_actions


def fallback_actions(dealer: dict) -> List[dict]:
    is_new = U.to_int(U.safe_get(dealer, "is_new_dealer", 0), 0)
    has_no_orders = U.to_int(U.safe_get(dealer, "has_no_orders", 0), 0)
    dsl = U.to_int(U.safe_get(dealer, "days_since_last_order", 0), 0)
    opp_value, _ = U.calculate_opportunity(dealer)

    actions: List[dict] = []
    if is_new == 1 and has_no_orders == 1:
        actions.append({
            "do": "Call dealer today to activate and book the first order; ask if any onboarding/stock issue is blocking.",
            "why": "New dealer onboarded but hasn't placed first order.",
            "impact": f"{_impact_range(max(8000.0, U.to_float(opp_value, 0.0)))} this month (basis peers)"
        })
    elif dsl > 30:
        actions.append({
            "do": f"Call/visit this week (no order for {dsl} days); ask competitor/stock issue and close a restart invoice.",
            "why": "Re-engage before dealer becomes inactive.",
            "impact": f"{_impact_range(8000.0)} this month (basis conservative)"
        })

    if U.to_float(opp_value, 0.0) > 0:
        actions.append({
            "do": "This week, compare peer basket and close 2 missing fast movers; target one incremental invoice.",
            "why": "Dealer has capacity to grow vs similar dealers.",
            "impact": f"{_impact_range(U.to_float(opp_value, 0.0))} this month (basis gap)"
        })

    products = U.to_int(U.safe_get(dealer, "count_base_product_last_90d", 0), 0)
    if products < 15:
        actions.append({
            "do": "Visit this week; ask which categories are being bought from competitors and close 2 trial SKUs.",
            "why": "Limited product range restricts order size.",
            "impact": f"{_impact_range(8000.0)} this month (basis trial add-on)"
        })

    return actions[:3]


# --------------------------------------------------------------------------------------
# Combine: RULE first immediately, then AI appended; AI wins on overlap (except collections)
# --------------------------------------------------------------------------------------
def _normalize_action(a: dict, source: str) -> dict:
    """Ensure both RULE + AI actions share the same schema used by app.py."""
    if a is None:
        a = {}

    # Common fallbacks if older rule nudges used different keys
    do = a.get("do") or a.get("action") or a.get("text") or ""
    why = a.get("why") or a.get("reason") or a.get("context") or ""
    impact = a.get("impact") or a.get("expected_impact") or ""
    tag = a.get("tag") or a.get("tag_id") or a.get("nudge_tag") or ""

    out = {
        "do": str(do).strip(),
        "why": str(why).strip(),
        "impact": str(impact).strip(),
        "tag": str(tag).strip(),
        "source": source,
    }

    # Preserve useful scoring fields if present
    for k in ["final_score", "priority", "strength_score", "confidence", "lift"]:
        if k in a:
            out[k] = a[k]

    return out


def _theme_from_action(a: dict) -> str:
    """
    Collapse tags into a few "themes" so rule & LLM don't nudge same type.
    AI wins on overlap.
    """
    tag = (a.get("tag") or "") if isinstance(a, dict) else ""
    fam = (a.get("tag_family") or "") if isinstance(a, dict) else ""
    llm_primary = (a.get("llm_primary_tag") or "") if isinstance(a, dict) else ""

    # Collections theme (keep rule)
    if "OVERDUE" in tag or "COLLECTION" in tag or "PAYMENT" in tag or "CEI" in tag:
        return "PAYMENTS"

    # LLM primaries
    if llm_primary in {"LLM_REPURCHASE_DUE"}:
        return "REPURCHASE"
    if llm_primary in {"LLM_INACTIVE_CATEGORY"}:
        return "INACTIVE_CATEGORY"
    if llm_primary in {"LLM_CROSS_SELL"}:
        return "CROSS_SELL"
    if llm_primary in {"LLM_TERRITORY_HERO"}:
        return "TERRITORY_HERO"

    # Families / heuristics (fallback)
    fam_u = str(fam).upper()
    if "CHURN" in fam_u or "INACTIVE" in fam_u:
        return "RETENTION"
    if "CROSS" in fam_u:
        return "CROSS_SELL"
    if "GROWTH" in fam_u or "UPSELL" in fam_u:
        return "UPSELL"
    if "PRODUCT" in fam_u or "MIX" in fam_u:
        return "MIX"

    # Text heuristic
    do = (a.get("do") or "").lower()
    if "reactivation" in do or "inactive" in do:
        return "RETENTION"
    if "cross-sell" in do:
        return "CROSS_SELL"
    if "upsell" in do or "growth gap" in do:
        return "UPSELL"

    return "GENERAL"

def combine_rule_and_ai_actions(
    rule_actions: List[dict],
    ai_actions: List[dict],
    max_rule: int = 2,
    max_ai: int = 3,
) -> List[dict]:
    rule_actions = rule_actions or []
    ai_actions = ai_actions or []

    # Normalize + cap
    rule_norm_all = [_normalize_action(a, "RULE") for a in rule_actions]
    ai_norm = [_normalize_action(a, "AI") for a in ai_actions[:max_ai]]  # use "AI" not "LLM"

    # Force overdue first if present (doesn't count against max_rule)
    overdue_rule = None
    for ra in rule_norm_all:
        if ra.get("tag") and "OVERDUE" in str(ra.get("tag")):
            overdue_rule = ra
            break

    # Take top rule actions (excluding overdue slot)
    rule_norm_capped = []
    for ra in rule_norm_all:
        if overdue_rule and ra is overdue_rule:
            continue
        rule_norm_capped.append(ra)
        if len(rule_norm_capped) >= max_rule:
            break

    combined = []
    seen = set()

    # Overdue first
    if overdue_rule:
        k = (overdue_rule.get("tag"), overdue_rule.get("do"))
        if k not in seen:
            seen.add(k)
            combined.append(overdue_rule)

    # Then rules
    for ra in rule_norm_capped:
        k = (ra.get("tag"), ra.get("do"))
        if k in seen:
            continue
        seen.add(k)
        combined.append(ra)

    # Then AI appended
    for aa in ai_norm:
        k = (aa.get("tag"), aa.get("do"))
        if k in seen:
            continue
        seen.add(k)
        combined.append(aa)

    return combined