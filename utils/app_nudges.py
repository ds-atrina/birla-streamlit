# utils/app_nudges.py
from __future__ import annotations

import math
import re
import hashlib
import random
from typing import Any, List, Optional, Tuple

from nudge_tag import TAG_SCHEMA, get_tag_family, get_strength_for_tag, assign_rule_tag_v2
from utils import app_utils as U

# ----------------------------
# Stable variation per dealer
# ----------------------------
def _dealer_key(dealer: dict) -> str:
    return str(
        (dealer or {}).get("dealer_composite_id") or (dealer or {}).get("dealer_id") or (dealer or {}).get("customer_name") or "unknown"
    )

def _pick_variant(dealer: dict, nudge_key: str, variants: List[str]) -> str:
    """
    Stable phrasing for the same dealer+condition:
      - Same dealer + same nudge_key => same chosen variant (no flicker)
      - Different dealers can get different variants
    """
    if not variants:
        return ""
    seed_raw = f"{_dealer_key(dealer)}|{nudge_key}"
    seed = int(hashlib.md5(seed_raw.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    return rng.choice(list(variants))

# ----------------------------
# Impact helpers
# ----------------------------
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

def _impact_score(action: dict) -> float:
    """
    Extract numeric score from impact string like "~₹8,000-₹12,000 ...".
    Uses the HIGH value if a range exists; else max value found.
    """
    if not isinstance(action, dict):
        return 0.0
    s = str(action.get("impact") or "")
    nums = re.findall(r"₹\s*([\d,]+)", s)
    if not nums:
        nums = re.findall(r"([\d,]+)", s)
    if not nums:
        return 0.0

    def to_num(x: str) -> float:
        try:
            return float(x.replace(",", ""))
        except Exception:
            return 0.0

    vals = [to_num(x) for x in nums]
    vals = [v for v in vals if v > 0]
    return max(vals) if vals else 0.0

# ----------------------------
# Dealer signal helpers
# ----------------------------
def _ensure_list(x: Any) -> List[dict]:
    return U.ensure_list(x) if hasattr(U, "ensure_list") else (x if isinstance(x, list) else [])

def _typical_invoice(dealer: dict) -> float:
    total_rev_90d = U.to_float(U.safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    total_orders_90d = U.to_int(U.safe_get(dealer, "total_orders_last_90d", 0), 0)
    aov_90d = U.to_float(U.safe_get(dealer, "avg_order_value_last_90d", 0.0), 0.0)
    if aov_90d > 0:
        return aov_90d
    if total_orders_90d > 0:
        return total_rev_90d / total_orders_90d
    return 0.0

def _baseline_monthly_sales(dealer: dict) -> float:
    total_rev_90d = U.to_float(U.safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    return (total_rev_90d / 3.0) if total_rev_90d > 0 else 0.0

def _is_dormant(dealer: dict) -> bool:
    orders_90d = U.to_int(U.safe_get(dealer, "total_orders_last_90d", 0), 0)
    dsl = U.to_int(U.safe_get(dealer, "days_since_last_order", 9999), 9999)
    zero_flag = U.to_int(U.safe_get(dealer, "flag_zero_activity_90d", 0), 0)
    return (orders_90d == 0) or (dsl >= 120) or (zero_flag == 1)

def _is_high_risk(dealer: dict) -> bool:
    trend_30d = U.to_float(U.safe_get(dealer, "pct_revenue_trend_30d", 0.0), 0.0)
    churn = U.to_float(U.safe_get(dealer, "order_churn_risk_score", 0.0), 0.0)
    dropping_off = U.to_int(U.safe_get(dealer, "dealer_is_dropping_off", 0), 0)
    return (trend_30d <= -20.0) or (churn > 1.0) or (dropping_off == 1)

def _theme_key(cat: str, sub: str) -> str:
    c = (cat or "").strip().lower()
    s = (sub or "").strip().lower()
    return f"{c}/{s}".strip("/")

def _pick_names(items: List[dict], k1: str, k2: str, limit: int = 3) -> List[str]:
    out: List[str] = []
    for it in items[:limit]:
        name = (it.get(k1) or it.get(k2) or "").strip()
        if name and name not in out:
            out.append(name)
    return out

def _sum_numeric(items: List[dict], key: str) -> float:
    s = 0.0
    for it in items:
        s += U.to_float(it.get(key), 0.0)
    return s

# ----------------------------
# WHY + Impact for RULE tags (keep tags same)
# ----------------------------
def _why_from_tag(dealer: dict, tag: str) -> str:
    # collections context
    overdue = U.to_float(dealer.get("overdue_amt_total", 0), 0.0)
    due_today = U.to_float(dealer.get("due_today_total", 0), 0.0)
    due_tom = U.to_float(dealer.get("due_tomorrow_total", 0), 0.0)
    due_in7 = U.to_float(dealer.get("due_in7_total", 0), 0.0)
    os_amt = U.to_float(dealer.get("os_amt_total", 0), 0.0)

    if tag == "OVERDUE_HIGH_AMOUNT":
        return f"Overdue pending: {U.fmt_rs(overdue)}. Need commitment + closure."
    if tag == "OVERDUE_DUE_TODAY":
        return f"Payment due today: {U.fmt_rs(due_today)}. Prevent slip."
    if tag == "OVERDUE_DUE_TOMORROW":
        return f"Payment due tomorrow: {U.fmt_rs(due_tom)}. Proactive reminder helps."
    if tag == "OVERDUE_DUE_IN_7_DAYS":
        return f"Payment due within 7 days: {U.fmt_rs(due_in7)}. Reduce risk of delay."
    if tag == "OVERDUE_OS_HIGH":
        return f"High outstanding: {U.fmt_rs(os_amt)}. Keep payment cadence healthy."

    # sales context
    dsl = U.to_int(dealer.get("days_since_last_order") or 0, 0)
    churn = U.to_float(dealer.get("order_churn_risk_score") or 0, 0.0)
    trend = U.to_float(dealer.get("pct_revenue_trend_90d") or 0, 0.0)

    if tag == "CHURN_RISK_INACTIVE_90D":
        return f"Dealer inactive for {dsl} days; high churn risk."
    if tag == "CHURN_RISK_HIGH_SCORE":
        return f"High churn risk score ({churn:.2f}); needs immediate follow-up."
    if tag == "SALES_DROP_SHARP":
        return f"Revenue trend is down {abs(trend):.0f}% (90d); needs correction."
    if tag == "PRODUCT_VARIETY_LOW":
        return "Limited product variety vs peers; expanding range can lift invoice value."

    return "Rule trigger matched based on dealer performance signals."

def _estimate_rule_impact(dealer: dict, tag: str) -> str:
    # Collections-based tags: impact should reflect real due amounts
    overdue = U.to_float(dealer.get("overdue_amt_total", 0), 0.0)
    due_today = U.to_float(dealer.get("due_today_total", 0), 0.0)
    due_tom = U.to_float(dealer.get("due_tomorrow_total", 0), 0.0)
    due_in7 = U.to_float(dealer.get("due_in7_total", 0), 0.0)
    os_amt = U.to_float(dealer.get("os_amt_total", 0), 0.0)

    if tag == "OVERDUE_HIGH_AMOUNT" and overdue > 0:
        return f"{_impact_range(overdue)} this month (basis overdue_amt)"
    if tag == "OVERDUE_DUE_TODAY" and due_today > 0:
        return f"{_impact_range(due_today)} this month (basis due_today)"
    if tag == "OVERDUE_DUE_TOMORROW" and due_tom > 0:
        return f"{_impact_range(due_tom)} this month (basis due_tomorrow)"
    if tag == "OVERDUE_DUE_IN_7_DAYS" and due_in7 > 0:
        return f"{_impact_range(due_in7)} this month (basis due_in7)"
    if tag == "OVERDUE_OS_HIGH" and os_amt > 0:
        return f"{_impact_range(os_amt)} this month (basis outstanding)"

    # Sales impacts (same logic you had)
    tiv = U.to_float(dealer.get("avg_invoice_value_90d") or dealer.get("typical_invoice_size") or 0, 0.0)
    monthly_rev = U.to_float(dealer.get("total_revenue_last_90d") or 0, 0.0) / 3.0
    gap_to_cluster = U.to_float(dealer.get("revenue_gap_vs_cluster_avg_monthly_last_90d") or 0, 0.0)

    if tag in {"CHURN_RISK_INACTIVE_90D", "CHURN_RISK_HIGH_SCORE", "NEW_DEALER_NO_ORDERS"}:
        basis = tiv if tiv > 0 else max(5000.0, 0.2 * monthly_rev)
        return f"{_impact_range(basis)} this month (basis reactivation)"

    if tag in {"GROWTH_OPPORTUNITY_BELOW_CLUSTER", "GROWTH_GAP_TO_CLUSTER"} and gap_to_cluster > 0:
        basis = min(gap_to_cluster, monthly_rev * 0.3 if monthly_rev > 0 else gap_to_cluster)
        return f"{_impact_range(basis)} this month (basis partial_gap)"

    basis = tiv if tiv > 0 else 8000.0
    return f"{_impact_range(basis)} this month (basis conservative)"

# ----------------------------
# Normalized action (shared schema)
# ----------------------------
def _tagged_action(
    primary_tag: str,
    do: str,
    why: str,
    impact: str,
    confidence: float,
    tag_basis: str,
    source: str,
) -> dict:
    tag = primary_tag if primary_tag in TAG_SCHEMA else "LLM_GENERAL"
    conf = max(0.60, min(0.95, float(confidence)))

    return {
        "do": do.strip(),
        "why": why.strip(),
        "impact": impact.strip(),

        "tag": tag,
        "tag_family": get_tag_family(tag),
        "priority_base": TAG_SCHEMA.get(tag, TAG_SCHEMA.get("LLM_GENERAL", {})).get("priority_base", 0),
        "strength_score": get_strength_for_tag(tag),

        "llm_primary_tag": primary_tag,          # keeps existing field name (tags unchanged)
        "llm_tag_confidence": conf,
        "llm_tag_basis": tag_basis.strip(),
        "source": source,
    }

# ======================================================================================
# 1) RULE NUDGES (Collections + OP + Subbrand) WITH VARIANTS
# ======================================================================================
def generate_collections_nudges(dealer: dict) -> List[dict]:
    actions: List[dict] = []

    due_today = U.to_float(dealer.get("due_today_total", 0), 0.0)
    due_tomorrow = U.to_float(dealer.get("due_tomorrow_total", 0), 0.0)
    due_in7 = U.to_float(dealer.get("due_in7_total", 0), 0.0)
    overdue_amt = U.to_float(dealer.get("overdue_amt_total", 0), 0.0)
    os_amt = U.to_float(dealer.get("os_amt_total", 0), 0.0)

    # ABSOLUTE PRIORITY: Overdue
    if overdue_amt > 0:
        variants = [
            (
                f"Collections Alert: ₹{overdue_amt:,.0f} OVERDUE. "
                "Visit dealer today - understand reason (dispute/cash flow/missed reminder), "
                "negotiate partial payment if needed, lock payment date."
            ),
            (
                f"Priority Collections: ₹{overdue_amt:,.0f} overdue. "
                "Visit today; ask what’s blocking payment (dispute/cash flow/forgot reminder) and lock a firm payment date."
            ),
            (
                f"Overdue Follow-up: ₹{overdue_amt:,.0f} pending. "
                "Call now, then visit today; resolve blocker and close partial payment + commitment date."
            ),
            (
                f"Collections Escalation: ₹{overdue_amt:,.0f} overdue. "
                "Meet dealer today; confirm mode (NEFT/cheque) and exact time, and document the commitment."
            ),
        ]
        actions.append({
            "text": _pick_variant(dealer, "COLLECTIONS_OVERDUE", variants),
            "priority": 10_000,
            "key": "COLLECTIONS_OVERDUE",
            "tag": "OVERDUE_HIGH_AMOUNT",
        })
        return actions

    if due_today > 0:
        variants = [
            (
                f"Collections URGENT: ₹{due_today:,.0f} payment due TODAY. "
                "Call dealer immediately - confirm payment status and mode (NEFT/cheque/cash). "
                "If delayed, get commitment for tomorrow with exact time."
            ),
            (
                f"Payment Due Today: ₹{due_today:,.0f}. "
                "Call now; confirm mode + exact time. If stuck, lock a clear commitment for tomorrow morning."
            ),
            (
                f"Today’s Collection: ₹{due_today:,.0f} due. "
                "Call dealer and confirm proof/timeline; if delayed, fix next-day payment with a specific hour."
            ),
        ]
        actions.append({
            "text": _pick_variant(dealer, "COLLECTIONS_DUE_TODAY", variants),
            "priority": 200,
            "key": "COLLECTIONS_DUE_TODAY",
            "tag": "OVERDUE_DUE_TODAY",
        })
    elif due_tomorrow > 0:
        variants = [
            (
                f"Collections Reminder: ₹{due_tomorrow:,.0f} due tomorrow. "
                "Call dealer today for proactive reminder - confirm they have funds ready."
            ),
            (
                f"Proactive Reminder: ₹{due_tomorrow:,.0f} due tomorrow. "
                "Call today; confirm funds + payment mode so it doesn’t slip."
            ),
            (
                f"Due Tomorrow: ₹{due_tomorrow:,.0f}. "
                "Call today and lock mode + time to avoid delay."
            ),
        ]
        actions.append({
            "text": _pick_variant(dealer, "COLLECTIONS_DUE_TOMORROW", variants),
            "priority": 150,
            "key": "COLLECTIONS_DUE_TOMORROW",
            "tag": "OVERDUE_DUE_TOMORROW",
        })
    elif due_in7 > 0:
        variants = [
            (
                f"Collections Watch: ₹{due_in7:,.0f} due within 7 days. "
                "Courtesy call - remind dealer of upcoming payment, ask if any issues expected."
            ),
            (
                f"Upcoming Payment: ₹{due_in7:,.0f} due this week. "
                "Quick courtesy call; check if any dispute/cash-flow issue is expected."
            ),
            (
                f"Collections Prep: ₹{due_in7:,.0f} due in the next 7 days. "
                "Call today; confirm no blockers and keep payment cadence clean."
            ),
        ]
        actions.append({
            "text": _pick_variant(dealer, "COLLECTIONS_DUE_IN_7", variants),
            "priority": 50,
            "key": "COLLECTIONS_DUE_IN_7",
            "tag": "OVERDUE_DUE_IN_7_DAYS",
        })
    elif os_amt > 100000:
        variants = [
            (
                f"High Outstanding: ₹{os_amt:,.0f} total OS (not yet overdue). "
                "Regular follow-up call - maintain relationship, ensure timely payment culture."
            ),
            (
                f"High OS Watch: ₹{os_amt:,.0f} outstanding (not overdue). "
                "Touch base this week to confirm schedule and prevent it turning overdue."
            ),
            (
                f"Outstanding Balance: ₹{os_amt:,.0f} (not overdue yet). "
                "Call this week; confirm next payment plan and keep the account healthy."
            ),
        ]
        actions.append({
            "text": _pick_variant(dealer, "COLLECTIONS_HIGH_OS", variants),
            "priority": 50,
            "key": "COLLECTIONS_HIGH_OS",
            "tag": "OVERDUE_OS_HIGH",
        })

    return actions

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
        variants = [
            f"Mix Upgrade: {dominant_pct:.0f}% sales are 'Style'. Pitch 'Calista' as a longer-lasting finish for upgrade buyers.",
            f"Upgrade play: 'Style' is ~{dominant_pct:.0f}% of sales. Show 'Calista' to premium finish buyers and close a trial add-on invoice.",
            f"Premium step-up: dealer is heavy on 'Style' (~{dominant_pct:.0f}%). Push 'Calista' for longer-lasting finish and lock a trial order.",
        ]
        actions.append({"key": "SUBBRAND_DOMINANT_STYLE", "priority": 30, "text": _pick_variant(dealer, "SUBBRAND_DOMINANT_STYLE", variants), "tag": "SUBBRAND_DOMINANT_STYLE"})
    elif dominant_brand == "Calista":
        variants = [
            f"Premium Push: 'Calista' is ~{dominant_pct:.0f}% of revenue. Show 'One' shade cards to premium clients for top-tier projects.",
            f"Premium expansion: 'Calista' contributes ~{dominant_pct:.0f}%. Pitch 'One' for premium projects and close 1 trial invoice this week.",
            f"Protect & upsell: strong 'Calista' mix (~{dominant_pct:.0f}%). Introduce 'One' range and close a premium add-on order.",
        ]
        actions.append({"key": "SUBBRAND_DOMINANT_CALISTA", "priority": 30, "text": _pick_variant(dealer, "SUBBRAND_DOMINANT_CALISTA", variants), "tag": "SUBBRAND_DOMINANT_CALISTA"})
    elif dominant_brand == "One":
        variants = [
            f"Protect Premium: 'One' is {dominant_pct:.0f}% of sales. Ensure full SKU range availability so they don't switch brands.",
            f"Defend premium share: 'One' is ~{dominant_pct:.0f}% of revenue. Ensure full range + on-time supply to prevent switching.",
            f"Keep premium locked: heavy 'One' mix ({dominant_pct:.0f}%). Confirm stock depth and close the next premium replenishment invoice.",
        ]
        actions.append({"key": "SUBBRAND_DOMINANT_ONE", "priority": 30, "text": _pick_variant(dealer, "SUBBRAND_DOMINANT_ONE", variants), "tag": "SUBBRAND_DOMINANT_ONE"})
    else:
        variants = [
            f"Mix Risk: ~{dominant_pct:.0f}% revenue depends on {dominant_brand}. Use this strength to open 1-2 more sub-brands (reduce dependency).",
            f"Reduce dependency: {dominant_brand} drives ~{dominant_pct:.0f}% of revenue. Introduce 1-2 additional sub-brands to balance mix.",
            f"Mix diversification: strong reliance on {dominant_brand} (~{dominant_pct:.0f}%). Push 1 new sub-brand this month to spread risk.",
        ]
        actions.append({"key": "SUBBRAND_DOMINANT_OTHER", "priority": 25, "text": _pick_variant(dealer, "SUBBRAND_DOMINANT_OTHER", variants), "tag": "SUBBRAND_DOMINANT_OTHER"})

    return actions

def generate_rule_nudges(dealer: dict, max_actions: int = 2) -> List[dict]:
    raw_actions: List[dict] = []

    def add_action(text: str, priority: int, key: str, tag: Optional[str] = None):
        raw_actions.append({"text": text, "priority": priority, "key": key, "tag": tag})

    # 0) Collections first (overdue returns immediately)
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
    rev_trend_30 = ((rev_30 - prev_30) / prev_30 * 100) if prev_30 > 0 else U.to_float(U.safe_get(dealer, "pct_revenue_trend_30d", 0.0), 0.0)

    rev_90 = U.to_float(U.safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    prev_90 = U.to_float(U.safe_get(dealer, "total_revenue_prev_90d", 0.0), 0.0)
    rev_trend_90 = ((rev_90 - prev_90) / prev_90 * 100) if prev_90 > 0 else U.to_float(U.safe_get(dealer, "pct_revenue_trend_90d", 0.0), 0.0)

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

    # 1) OP rules with variants
    if is_new and has_no_orders:
        potential = max(cluster_avg_monthly, territory_avg_monthly, 0.0)
        variants = [
            (
                "New dealer onboarded - but no orders yet. "
                "Start with territory hero products (Premium Emulsion, Exterior Weathercoat, Interior Primer) "
                f"+ early-bird scheme; target first invoice this week (peer potential ~{U.fmt_rs(potential)}/month)."
            ),
            (
                "Activation needed: dealer onboarded but no first order. "
                "Call today; ask if onboarding/credit/stock is blocking. "
                f"Close a starter invoice this week with hero SKUs (peer potential ~{U.fmt_rs(potential)}/month)."
            ),
            (
                "First-order push: new dealer hasn’t started ordering. "
                "Visit this week; ask if competitor influence or stock placement is the blocker. "
                f"Close first invoice with hero products + scheme (peer potential ~{U.fmt_rs(potential)}/month)."
            ),
        ]
        add_action(_pick_variant(dealer, "OP_NEW_NO_ORDERS", variants), 800, "OP_NEW_NO_ORDERS", None)

    elif dsl >= 90:
        months_lost = min(3, max(1, math.ceil(dsl / 30)))
        lost_sales = baseline_monthly * months_lost
        variants = [
            (
                f"Dealer inactive for {dsl} days—no orders placed. "
                "Call/visit today, diagnose (stock stuck vs competitor vs pipeline), "
                f"and book a restart order (at risk ~{U.fmt_rs(lost_sales)})."
            ),
            (
                f"No orders for {dsl} days. "
                "Visit today; ask what blocked ordering (stock/credit/competition/projects) and close a restart invoice. "
                f"Revenue at risk ~{U.fmt_rs(lost_sales)}."
            ),
            (
                f"Dealer silent for {dsl} days. "
                "Call now + fix the blocker; then book a restart order this week with 2 hero SKUs. "
                f"Potential leakage ~{U.fmt_rs(lost_sales)}."
            ),
        ]
        add_action(
            _pick_variant(dealer, "OP_INACTIVE_90D", variants),
            750 + (50 if churn_risk > 1.0 or dropping_off == 1 else 0),
            "OP_INACTIVE_90D",
            None,
        )
    else:
        if rev_trend_30 <= -20:
            variants = [
                (
                    f"Billing down {abs(rev_trend_30):.0f}% vs last month. "
                    "Visit this week, check competitor switch/stock issues, "
                    "and close one replenishment order with hero SKUs."
                ),
                (
                    f"Sales dip: {abs(rev_trend_30):.0f}% down vs last month. "
                    "Visit this week; ask if stock is stuck or competitor schemes are active, and close a replenishment invoice."
                ),
                (
                    f"Revenue falling ({abs(rev_trend_30):.0f}% down). "
                    "Call today; confirm issue (credit/stock/competition), then visit and close one hero-SKU replenishment order."
                ),
            ]
            add_action(_pick_variant(dealer, "OP_UNDERPERFORMER_DROP_30D", variants), 650, "OP_UNDERPERFORMER_DROP_30D", None)

        if gap_to_cluster > 5000 and rev_trend_30 > -25:
            variants = [
                (
                    f"Billing is {U.fmt_rs(abs(gap_to_cluster))} below peer avg. "
                    "Compare peer basket and push 2 missing fast movers to close gap this month."
                ),
                (
                    f"Gap vs peers: short by {U.fmt_rs(abs(gap_to_cluster))}. "
                    "Check peer basket and close 2 missing fast movers in the next invoice."
                ),
                (
                    f"Under peer average by {U.fmt_rs(abs(gap_to_cluster))}. "
                    "Visit this week; identify 2 fast movers missing vs peers and close one incremental order."
                ),
            ]
            add_action(_pick_variant(dealer, "OP_GAP_TO_PEERS", variants), 600, "OP_GAP_TO_PEERS", None)

        if rev_trend_90 > 20 and gap_to_cluster <= 0:
            variants = [
                (
                    f"Up {rev_trend_90:.0f}% vs previous 90 days and above peers. "
                    "Appreciate + introduce waterproofing/premium line to expand wallet share."
                ),
                (
                    f"Strong growth: +{rev_trend_90:.0f}% vs last 90 days (above peers). "
                    "Appreciate and pitch 1 premium/waterproofing add-on to increase wallet share."
                ),
                (
                    f"Dealer is growing (+{rev_trend_90:.0f}% in 90d). "
                    "Use this momentum: introduce a premium line + ensure full range availability for the next big project."
                ),
            ]
            add_action(_pick_variant(dealer, "OP_GOOD_PERFORMER", variants), 520, "OP_GOOD_PERFORMER", None)

    # 2) Sub-brand nudges (only when not in activation/inactive/decline mode)
    enable_subbrand = (not has_no_orders) and (dsl < 60) and (rev_trend_30 > -15)
    raw_actions.extend(get_subbrand_nudges(dealer, enabled=enable_subbrand))

    # Fallback
    if not raw_actions:
        variants = [
            "Visit the dealer to identify gaps, preferences and competition.",
            "Visit this week; ask what’s blocking growth (stock/competition/painter demand) and close one clear next invoice.",
            "Call first, then visit; diagnose the gap and lock one specific order commitment for the next 7 days.",
        ]
        add_action(_pick_variant(dealer, "GENERIC_VISIT", variants), 10, "GENERIC_VISIT", "CROSS_SELL_CATEGORY")

    # Rank + dedupe + cap (overdue slot doesn't count)
    raw_actions = sorted(raw_actions, key=lambda x: x.get("priority", 0), reverse=True)
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
            continue

        effective_len = len([x for x in final_raw if x.get("key") != must_keep_key])
        if effective_len >= max_actions:
            break

    # Normalize output schema
    out: List[dict] = []
    for item in final_raw:
        text = item.get("text", "")
        tag = item.get("tag")

        if not tag or tag not in TAG_SCHEMA:
            rule_tag, rule_conf = assign_rule_tag_v2(text, dealer)
            tag = rule_tag
            conf = U.to_float(rule_conf, 0.0)
        else:
            conf = 0.90

        out.append({
            "do": str(text).strip(),
            "why": _why_from_tag(dealer, tag),
            "impact": _estimate_rule_impact(dealer, tag),

            "tag": tag,
            "tag_family": get_tag_family(tag),
            "priority_base": TAG_SCHEMA.get(tag, TAG_SCHEMA.get("LLM_GENERAL", {})).get("priority_base", 0),
            "strength_score": get_strength_for_tag(tag),

            # RULE => keep fields but don't pretend it's LLM
            "llm_primary_tag": "",
            "llm_tag_confidence": conf,
            "llm_tag_basis": "rule_engine",
            "source": "rule",
        })

    return out

# ======================================================================================
# 2) “AI” NUDGES (LLM-FREE, deterministic from candidate lists) WITH VARIANTS
# ======================================================================================
def _build_dormant_general(dealer: dict) -> dict:
    repurchase = _ensure_list(dealer.get("llm_repurchase_recommendations"))
    terr_hero = _ensure_list(dealer.get("llm_territory_top_products_90d"))

    basket: List[str] = []
    basket.extend(_pick_names(terr_hero, "product", "base_product", limit=2))
    if len(basket) < 3:
        basket.extend([x for x in _pick_names(repurchase, "product", "base_product", limit=3) if x not in basket])
    basket = basket[:3]

    tiv = _typical_invoice(dealer)
    base_mo = _baseline_monthly_sales(dealer)
    basis = tiv if tiv > 0 else max(8000.0, 0.2 * base_mo)

    dsl = U.to_int(U.safe_get(dealer, "days_since_last_order", 9999), 9999)
    orders_90d = U.to_int(U.safe_get(dealer, "total_orders_last_90d", 0), 0)

    items_txt = ", ".join(basket) if basket else "territory hero SKUs from your list"

    variants = [
        f"Visit today; ask what’s blocking orders (stock stuck / competitor / project pipeline?). Close a restart invoice {_impact_range(basis)} with starter basket: {items_txt}.",
        f"Call now, then visit today; diagnose blocker (credit/stock/competition) and close restart invoice {_impact_range(basis)} using: {items_txt}.",
        f"Today: go in-person; ask what changed (stock/cashflow/competitor). Close 1 restart order {_impact_range(basis)} with: {items_txt}.",
    ]
    do = _pick_variant(dealer, "AI_DORMANT_GENERAL", variants)

    why = f"Dormant signal: {orders_90d} orders in 90d or last order {dsl} days ago; restart needed."
    impact = f"{_impact_range(basis)} this month (basis typical_invoice)"
    tag_basis = f"dormant_override; basis={'typical_invoice' if tiv > 0 else 'baseline_monthly'}"

    return _tagged_action("LLM_GENERAL", do, why, impact, 0.82, tag_basis, "ai")

def _build_repurchase_bundle(dealer: dict, used_themes: set) -> Optional[Tuple[dict, set]]:
    repurchase = _ensure_list(dealer.get("llm_repurchase_recommendations"))
    if not repurchase:
        return None

    def urgency_score(it: dict) -> float:
        urg = str(it.get("urgency_level") or "").upper()
        act = str(it.get("action") or "").upper()
        score = 0.0
        if "WINBACK" in urg or "WINBACK" in act:
            score += 100
        if "HIGH" in urg or "HIGH" in act:
            score += 50
        if "DUE" in urg or "DUE" in act or "REORDER" in act:
            score += 20
        dsl = U.to_float(it.get("days_since_last_purchase"), 0.0)
        score += min(15.0, dsl / 10.0)
        return score

    rep_sorted = sorted(repurchase, key=urgency_score, reverse=True)

    rep_themes = set(_theme_key(it.get("category", ""), it.get("sub_category", "")) for it in rep_sorted)
    names = _pick_names(rep_sorted, "product", "base_product", limit=3)
    names_txt = ", ".join(names) if names else "due repurchase items from your list"

    tov_sum = _sum_numeric(rep_sorted, "typical_order_value")
    tiv = _typical_invoice(dealer)
    basis = tov_sum if tov_sum > 0 else (tiv if tiv > 0 else 8000.0)

    variants = [
        f"Call today; ask if stock is stuck or competitor is pushing schemes. Close a bundled repurchase invoice {_impact_range(basis)} for: {names_txt} (bundle due items).",
        f"Today: call + confirm demand/stock. Close one bundled repurchase order {_impact_range(basis)} covering: {names_txt}.",
        f"Visit this week; ask what delayed repeat buying. Close a single bundled invoice {_impact_range(basis)} for: {names_txt}.",
    ]
    do = _pick_variant(dealer, "AI_REPURCHASE_BUNDLE", variants)

    why = "These items are due/overdue by cycle signals; bundling prevents churn and secures next invoice."
    impact = f"{_impact_range(basis)} this month (basis repurchase_bundle)"
    tag_basis = f"basis={'sum_typical_order_value' if tov_sum > 0 else 'typical_invoice'}"

    a = _tagged_action("LLM_REPURCHASE_DUE", do, why, impact, 0.86, tag_basis, "ai")
    return a, (used_themes | rep_themes)

def _build_defend_share(dealer: dict, used_themes: set) -> Optional[Tuple[dict, set]]:
    dealer_top = _ensure_list(dealer.get("llm_dealer_top_products_90d"))
    terr_hero = _ensure_list(dealer.get("llm_territory_top_products_90d"))

    anchor_name = None
    basis = 0.0
    basis_field = ""
    theme = ""

    if dealer_top:
        top = sorted(dealer_top, key=lambda x: U.to_float(x.get("avg_monthly_sales"), 0.0), reverse=True)[0]
        anchor_name = (top.get("product") or top.get("base_product") or "core SKUs").strip()
        basis = U.to_float(top.get("avg_monthly_sales"), 0.0)
        basis_field = f"dealer_top_mo={basis:.0f}"
        theme = _theme_key(top.get("category", ""), top.get("sub_category", ""))

    if (not anchor_name) and terr_hero:
        th = sorted(terr_hero, key=lambda x: U.to_float(x.get("benchmark_monthly_sales"), 0.0), reverse=True)[0]
        anchor_name = (th.get("product") or th.get("base_product") or "territory hero SKUs").strip()
        b = U.to_float(th.get("benchmark_monthly_sales"), 0.0)
        if b > 0:
            basis = b
            basis_field = f"bench={b:.0f}"
        theme = _theme_key(th.get("category", ""), th.get("sub_category", ""))

    tiv = _typical_invoice(dealer)
    if basis <= 0:
        basis = tiv if tiv > 0 else max(8000.0, 0.2 * _baseline_monthly_sales(dealer))
        basis_field = f"typical_invoice={basis:.0f}"

    variants = [
        f"Visit this week; ask if any competitor is offering credit/scheme to switch. Secure availability and close next invoice {_impact_range(basis)} by defending core: {anchor_name}.",
        f"Call today; ask if stock/credit is the issue. Defend core SKUs ({anchor_name}) and close next invoice {_impact_range(basis)}.",
        f"This week: check shelf share and stock depth. Defend {anchor_name} and lock next invoice {_impact_range(basis)}.",
    ]
    do = _pick_variant(dealer, "AI_DEFEND_SHARE", variants)

    why = "For high-risk dealers, defending core SKUs prevents immediate revenue leakage."
    impact = f"{_impact_range(basis)} this month (basis defend_share)"
    tag_basis = f"{basis_field}; defend_share"

    a = _tagged_action("LLM_TERRITORY_HERO", do, why, impact, 0.80, tag_basis, "ai")
    new_used = set(used_themes)
    if theme:
        new_used.add(theme)
    return a, new_used

def _build_inactive_category(dealer: dict, used_themes: set, blocked_themes: set) -> Optional[Tuple[dict, set]]:
    inactive = _ensure_list(dealer.get("llm_inactive_categories_90d"))
    if not inactive:
        return None

    def gap_score(it: dict) -> float:
        peer = U.to_float(it.get("peer_typical_monthly_sales"), 0.0)
        past = U.to_float(it.get("dealer_past_monthly_sales"), 0.0)
        dsl = U.to_float(it.get("days_since_last_purchase"), 0.0)
        return max(0.0, peer - past) + min(10.0, dsl / 10.0)

    cand = sorted(inactive, key=gap_score, reverse=True)

    for it in cand:
        cat = (it.get("category") or "").strip()
        sub = (it.get("sub_category") or "").strip()
        theme = _theme_key(cat, sub)
        if not theme or theme in used_themes or theme in blocked_themes:
            continue

        peer = U.to_float(it.get("peer_typical_monthly_sales"), 0.0)
        past = U.to_float(it.get("dealer_past_monthly_sales"), 0.0)
        basis = min(past if past > 0 else peer * 0.25, peer * 0.5 if peer > 0 else 8000.0)
        basis = max(8000.0, basis) if basis > 0 else 8000.0

        dsl = U.to_int(it.get("days_since_last_purchase") or 0, 0)
        variants = [
            f"Call today; ask why this category stopped (stock stuck / painter demand / competitor?). Close a restart in {cat}{('/' + sub) if sub else ''} by adding 2 SKUs; target invoice {_impact_range(basis)}.",
            f"Visit this week; ask what blocked {cat}{('/' + sub) if sub else ''}. Close a reactivation order with 2 SKUs; invoice target {_impact_range(basis)}.",
            f"Today: call and confirm demand. Reactivate {cat}{('/' + sub) if sub else ''} with 2 SKUs and close invoice {_impact_range(basis)}.",
        ]
        do = _pick_variant(dealer, f"AI_INACTIVE_CATEGORY|{theme}", variants)

        why = f"Inactive for ~{dsl} days; peers move ~{U.fmt_rs(peer)}/mo while dealer was ~{U.fmt_rs(past)}."
        impact = f"{_impact_range(basis)} this month (basis inactive_category)"
        tag_basis = f"peer_mo={peer:.0f}; past_mo={past:.0f}"

        a = _tagged_action("LLM_INACTIVE_CATEGORY", do, why, impact, 0.78, tag_basis, "ai")
        new_used = set(used_themes)
        new_used.add(theme)
        return a, new_used

    return None

def _build_cross_sell(dealer: dict, used_themes: set, blocked_themes: set) -> Optional[Tuple[dict, set]]:
    cross = _ensure_list(dealer.get("llm_territory_products_in_dealer_categories"))
    if not cross:
        return None

    def score(it: dict) -> float:
        peers = U.to_float(it.get("percent_peers_stocking"), 0.0)
        bench = U.to_float(it.get("benchmark_monthly_sales"), 0.0)
        return peers * 10 + min(50.0, bench / 2000.0)

    cand = sorted(cross, key=score, reverse=True)

    picked: List[dict] = []
    picked_themes: set = set()
    for it in cand:
        theme = _theme_key(it.get("category", ""), it.get("sub_category", ""))
        if not theme or theme in used_themes or theme in blocked_themes or theme in picked_themes:
            continue
        picked.append(it)
        picked_themes.add(theme)
        if len(picked) >= 2:
            break

    if not picked:
        return None

    names = _pick_names(picked, "product", "base_product", limit=2)
    names_txt = ", ".join(names) if names else "2 cross-sell SKUs from your list"

    tiv = _typical_invoice(dealer)
    basis = max(8000.0, 0.6 * tiv) if tiv > 0 else 8000.0

    peers0 = U.to_float(picked[0].get("percent_peers_stocking"), 0.0)
    bench0 = U.to_float(picked[0].get("benchmark_monthly_sales"), 0.0)

    variants = [
        f"Visit this week; ask which related items are being sourced from competitors. Close a trial add-on by adding: {names_txt}; target invoice {_impact_range(basis)}.",
        f"Call today; ask if they stock these add-ons. Close a trial order with {names_txt}; target invoice {_impact_range(basis)}.",
        f"This week: push 2 add-on SKUs ({names_txt}) and close a trial invoice {_impact_range(basis)}.",
    ]
    do = _pick_variant(dealer, "AI_CROSS_SELL", variants)

    why = f"Peer adoption ~{peers0:.0f}% and benchmark ~{U.fmt_rs(bench0)}/mo; trial can lift AOV."
    impact = f"{_impact_range(basis)} this month (basis trial_addon)"
    tag_basis = f"peers={peers0:.0f}; bench={bench0:.0f}"

    a = _tagged_action("LLM_CROSS_SELL", do, why, impact, 0.72, tag_basis, "ai")
    new_used = set(used_themes)
    new_used |= picked_themes
    return a, new_used

def _build_territory_hero_expand(dealer: dict, used_themes: set, blocked_themes: set) -> Optional[Tuple[dict, set]]:
    terr = _ensure_list(dealer.get("llm_territory_top_products_90d"))
    if not terr:
        return None

    def score(it: dict) -> float:
        lift = U.to_float(it.get("estimated_revenue_lift"), 0.0)
        peers = U.to_float(it.get("percent_peers_stocking"), 0.0)
        return lift + peers * 2.0

    cand = sorted(terr, key=score, reverse=True)

    for it in cand:
        theme = _theme_key(it.get("category", ""), it.get("sub_category", ""))
        if theme and (theme in used_themes or theme in blocked_themes):
            continue

        name = (it.get("product") or it.get("base_product") or "").strip()
        if not name:
            continue

        bench = U.to_float(it.get("benchmark_monthly_sales"), 0.0)
        tiv = _typical_invoice(dealer)
        basis = bench * 0.3 if bench > 0 else (max(8000.0, 0.6 * tiv) if tiv > 0 else 8000.0)

        variants = [
            f"Call this week; ask if any project/painter demand is coming up and what stock is missing. Close an expansion invoice by adding territory hero: {name} (2 SKUs); target {_impact_range(basis)}.",
            f"Visit this week; ask what’s moving fast locally. Add territory hero {name} (2 SKUs) and close invoice {_impact_range(basis)}.",
            f"This week: push territory hero {name} and close a trial expansion invoice {_impact_range(basis)} (2 SKUs).",
        ]
        do = _pick_variant(dealer, f"AI_TERRITORY_HERO|{theme or name}", variants)

        why = "Territory hero has strong peer movement; adding it improves conversion and basket."
        impact = f"{_impact_range(basis)} this month (basis territory_hero)"
        tag_basis = f"bench={bench:.0f}"

        a = _tagged_action("LLM_TERRITORY_HERO", do, why, impact, 0.74, tag_basis, "ai")
        new_used = set(used_themes)
        if theme:
            new_used.add(theme)
        return a, new_used

    return None

def generate_llm_free_nudges(dealer: dict) -> List[dict]:
    """
    Deterministic replacement for LLM nudges:
      - Dormant override => exactly 1 action (LLM_GENERAL)
      - Else => 2-3 actions, max 1 per primary tag
      - High-risk => prioritize repurchase / defend share; avoid cross-sell unless needed
      - No overlap across category themes (best-effort)
    """
    if not isinstance(dealer, dict):
        return []

    if _is_dormant(dealer):
        return [_build_dormant_general(dealer)]

    used_themes: set = set()
    actions: List[dict] = []
    used_primary: set = set()

    high_risk = _is_high_risk(dealer)
    rep_blocked_themes: set = set()

    if high_risk:
        rep = _build_repurchase_bundle(dealer, used_themes)
        if rep:
            a, used_themes = rep
            actions.append(a)
            used_primary.add("LLM_REPURCHASE_DUE")

            # block inactive category overlaps with repurchase themes
            for it in _ensure_list(dealer.get("llm_repurchase_recommendations")):
                rep_blocked_themes.add(_theme_key(it.get("category", ""), it.get("sub_category", "")))

        defend = _build_defend_share(dealer, used_themes)
        if defend and "LLM_TERRITORY_HERO" not in used_primary and len(actions) < 2:
            a, used_themes = defend
            actions.append(a)
            used_primary.add("LLM_TERRITORY_HERO")

    blocked_themes = set(rep_blocked_themes)

    if len(actions) < 3 and "LLM_INACTIVE_CATEGORY" not in used_primary:
        x = _build_inactive_category(dealer, used_themes, blocked_themes)
        if x:
            a, used_themes = x
            actions.append(a)
            used_primary.add("LLM_INACTIVE_CATEGORY")

    if len(actions) < 3 and "LLM_TERRITORY_HERO" not in used_primary:
        x = _build_territory_hero_expand(dealer, used_themes, blocked_themes)
        if x:
            a, used_themes = x
            actions.append(a)
            used_primary.add("LLM_TERRITORY_HERO")

    if len(actions) < 3 and "LLM_CROSS_SELL" not in used_primary:
        if (not high_risk) or (high_risk and len(actions) <= 1):
            x = _build_cross_sell(dealer, used_themes, blocked_themes)
            if x:
                a, used_themes = x
                actions.append(a)
                used_primary.add("LLM_CROSS_SELL")

    if len(actions) < 2:
        defend = _build_defend_share(dealer, used_themes)
        if defend and "LLM_TERRITORY_HERO" not in used_primary:
            a, used_themes = defend
            actions.append(a)
            used_primary.add("LLM_TERRITORY_HERO")

    return actions[:3]

# ----------------------------
# Public API used by app.py
# ----------------------------
def generate_ai_nudges(dealer: dict, model=None) -> List[dict]:
    """
    LLM-FREE “AI nudges” built deterministically from candidate lists.
    Keeps signature (model=None) so your app imports don’t break.
    """
    return generate_llm_free_nudges(dealer)

def generate_llm_nudges_unused(dealer: dict, model=None) -> List[dict]:
    """
    UNUSED STUB (kept for future if you re-enable LLM).
    Currently returns empty list on purpose.
    """
    return []

# ======================================================================================
# 3) COMBINE + SORT (impact-sort, overdue first always)
# ======================================================================================
def _normalize_action(a: dict, source: str) -> dict:
    if a is None:
        a = {}
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
    # keep any scoring fields if present
    for k in ["final_score", "priority", "strength_score", "confidence", "lift", "priority_base", "tag_family"]:
        if k in a:
            out[k] = a[k]
    return out

def combine_rule_and_ai_actions(
    rule_actions: List[dict],
    ai_actions: List[dict],
    max_rule: int = 2,
    max_ai: int = 3,
) -> List[dict]:
    rule_actions = rule_actions or []
    ai_actions = ai_actions or []

    rule_norm_all = [_normalize_action(a, "rule") for a in rule_actions]
    ai_norm = [_normalize_action(a, "ai") for a in ai_actions[:max_ai]]

    # find overdue rule (keep first, doesn’t count against max_rule)
    overdue_rule = None
    for ra in rule_norm_all:
        if "OVERDUE" in str(ra.get("tag") or ""):
            overdue_rule = ra
            break

    # cap rule (excluding overdue slot)
    rule_capped: List[dict] = []
    for ra in rule_norm_all:
        if overdue_rule and ra is overdue_rule:
            continue
        rule_capped.append(ra)
        if len(rule_capped) >= max_rule:
            break

    # combine with de-dupe
    combined: List[dict] = []
    seen = set()

    if overdue_rule:
        k = (overdue_rule.get("tag"), overdue_rule.get("do"))
        if k not in seen:
            seen.add(k)
            combined.append(overdue_rule)

    for ra in rule_capped:
        k = (ra.get("tag"), ra.get("do"))
        if k in seen:
            continue
        seen.add(k)
        combined.append(ra)

    for aa in ai_norm:
        k = (aa.get("tag"), aa.get("do"))
        if k in seen:
            continue
        seen.add(k)
        combined.append(aa)

    # final sort: by impact desc, but keep overdue first always
    if combined:
        overdue = None
        rest: List[dict] = []
        for x in combined:
            if overdue is None and "OVERDUE" in str(x.get("tag") or ""):
                overdue = x
            else:
                rest.append(x)

        rest.sort(key=_impact_score, reverse=True)
        combined = ([overdue] if overdue else []) + rest

    return combined
