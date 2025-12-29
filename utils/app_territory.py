# utils/app_territory.py 

import pandas as pd
from utils import app_utils as U

def calculate_territory_health(territory_df: pd.DataFrame) -> dict:
    """Calculate territory-level health metrics"""
    
    total_dealers = len(territory_df)
    
    # Active dealers (ordered in last 90d)
    active_dealers = (territory_df['total_orders_last_90d'] > 0).sum()
    
    # High churn risk
    high_churn = (territory_df['order_churn_risk_score'] > 1.5).sum()
    
    # Declining dealers
    declining = (territory_df['pct_revenue_trend_90d'] < -20).sum()
    
    # # Inactive 90d+
    # inactive_90d = (territory_df['days_since_last_order'] >= 90).sum()
    
    # Total revenue
    total_revenue_90d = territory_df['total_revenue_last_90d'].sum()
    prev_revenue_90d = territory_df['total_revenue_prev_90d'].sum()
    
    # Revenue trend
    if prev_revenue_90d > 0:
        revenue_trend = ((total_revenue_90d - prev_revenue_90d) / prev_revenue_90d) * 100
    else:
        revenue_trend = 0.0
    
    return {
        'total_dealers': total_dealers,
        'active_dealers': active_dealers,
        'high_churn_count': high_churn,
        'declining_count': declining,
        # 'inactive_90d_count': inactive_90d,
        'total_revenue_90d': total_revenue_90d,
        'prev_revenue_90d': prev_revenue_90d,
        'revenue_trend_pct': revenue_trend,
        'active_rate': (active_dealers / total_dealers) * 100 if total_dealers > 0 else 0,
    }

def calculate_territory_collections(territory_df: pd.DataFrame) -> dict:
    """Calculate territory-level collections metrics"""
    
    # Total collections metrics
    total_overdue = territory_df['overdue_amt_total'].sum()
    total_os = territory_df['os_amt_total'].sum()
    total_due_today = territory_df['due_today_total'].sum()
    total_due_today_only = territory_df['due_today_only_total'].sum()
    total_due_tomorrow = territory_df['due_tomorrow_total'].sum()
    total_due_in7 = territory_df['due_in7_total'].sum()
    
    # Dealers with overdues
    dealers_with_overdue = (territory_df['overdue_amt_total'] > 0).sum()
    dealers_with_due_today = (territory_df['due_today_total'] > 0).sum()
    
    # Overdue concentration (top 10 dealers)
    top_10_overdue = territory_df.nlargest(10, 'overdue_amt_total')['overdue_amt_total'].sum()
    overdue_concentration = (top_10_overdue / total_overdue * 100) if total_overdue > 0 else 0
    
    return {
        'total_overdue': total_overdue,
        'total_os': total_os,
        'total_due_today': total_due_today,
        'total_due_today_only': total_due_today_only,
        'total_due_tomorrow': total_due_tomorrow,
        'total_due_in7': total_due_in7,
        'dealers_with_overdue': dealers_with_overdue,
        'dealers_with_due_today': dealers_with_due_today,
        'overdue_concentration_pct': overdue_concentration,
    }

def generate_combined_call_list(territory_df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    """
    Unified dealer priority list aligned to nudge prioritisation.
    NOTE: We do NOT change any tags:
      - reason_chips values remain: DUE_TODAY, OVERDUE, DUE_TOMORROW, DUE_IN7, INACTIVE, CHURN_RISK, DECLINING, GAP_VS_PEERS
      - nudge tags remain untouched (this function does not touch nudge tags at all)

    Goal: consistent ordering impact with rule nudges:
      OVERDUE absolute top, then sales activation/risk (new-no-orders, inactive 90d, sharp decline),
      then due-today, then gap (with guardrail), then due-tom, due-in7, etc.
    """

    df = territory_df.copy()

    def _series(col: str) -> pd.Series:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0)
        return pd.Series(0, index=df.index, dtype="float")

    due_today = _series("due_today_total")
    overdue = _series("overdue_amt_total")
    due_tom = _series("due_tomorrow_total")
    due_in7 = _series("due_in7_total")
    os_amt = _series("os_amt_total")

    dsl = _series("days_since_last_order")
    churn = _series("order_churn_risk_score")
    gap = _series("revenue_gap_vs_cluster_avg_monthly_last_90d")

    # Prefer 30d decline when available; fallback to 90d
    trend_90 = _series("pct_revenue_trend_90d")
    if "pct_revenue_trend_30d" in df.columns:
        trend_30 = _series("pct_revenue_trend_30d")
    elif "total_revenue_last_30d" in df.columns and "total_revenue_prev_30d" in df.columns:
        rev_30 = _series("total_revenue_last_30d")
        prev_30 = _series("total_revenue_prev_30d")
        trend_30 = pd.Series(0.0, index=df.index, dtype="float")
        m = prev_30 > 0
        trend_30.loc[m] = ((rev_30.loc[m] - prev_30.loc[m]) / prev_30.loc[m]) * 100.0
    else:
        trend_30 = trend_90  # fallback

    # New/no-orders inference (NO new tags added to reason_chips)
    is_new = (_series("is_new_dealer") >= 1) | (_series("tenure_months") <= 1)
    has_no_orders = (_series("has_no_orders") >= 1) | (_series("total_orders_lifetime") <= 0)

    # Sub-scores
    df["collections_score"] = 0.0
    df["sales_risk_score"] = 0.0
    df["opportunity_score"] = 0.0

    # -----------------------------
    # 1) Collections scoring (hierarchical like nudges)
    # -----------------------------
    m_overdue = overdue > 0
    m_due_today = (~m_overdue) & (due_today > 0)
    m_due_tom = (~m_overdue) & (due_today <= 0) & (due_tom > 0)
    m_due_in7 = (~m_overdue) & (due_today <= 0) & (due_tom <= 0) & (due_in7 > 0)
    m_high_os = (~m_overdue) & (due_today <= 0) & (due_tom <= 0) & (due_in7 <= 0) & (os_amt > 100000)

    df.loc[m_overdue, "collections_score"] += 1000
    df.loc[m_due_today, "collections_score"] += 650
    df.loc[m_due_tom, "collections_score"] += 350
    df.loc[m_due_in7, "collections_score"] += 200
    df.loc[m_high_os, "collections_score"] += 150

    # Overdue magnitude boost (keeps big-overdue dealers at the very top)
    df.loc[m_overdue, "collections_score"] += (overdue / 100000).clip(lower=0, upper=200)

    # -----------------------------
    # 2) Sales risk scoring (match nudge intent)
    # -----------------------------
    # New dealer + no orders (strong activation priority)
    df.loc[is_new & has_no_orders, "sales_risk_score"] += 900

    # Inactivity: keep 45d as early warning but 90d as major priority
    df.loc[dsl >= 45, "sales_risk_score"] += 250
    df.loc[dsl >= 90, "sales_risk_score"] += 600  # total = 850 at 90d+

    # Decline: use 30d primarily (like your OP underperformer rule)
    df.loc[trend_30 <= -20, "sales_risk_score"] += 700
    # fallback support: if 30d not present and 90d is bad, still give some points
    df.loc[(trend_30 == trend_90) & (trend_90 < -20), "sales_risk_score"] += 200

    # Churn: keep chip threshold same (>1.5), but add softer bump above 1.0 (does NOT change tags)
    df.loc[churn > 1.0, "sales_risk_score"] += 100
    df.loc[churn > 1.5, "sales_risk_score"] += 150  # total churn bump at >1.5 = 250

    # -----------------------------
    # 3) Opportunity scoring (same guardrail as rule nudges)
    # -----------------------------
    # Rule guardrail: gap only if not crashing badly (trend_30 > -25)
    df.loc[(gap > 5000) & (trend_30 > -25), "opportunity_score"] += 500
    # If gap exists but dealer is crashing, keep it visible but lower than decline/inactive
    df.loc[(gap > 5000) & (trend_30 <= -25), "opportunity_score"] += 150

    # Unified score
    df["call_score"] = df["collections_score"] + df["sales_risk_score"] + df["opportunity_score"]

    # Keep only actionable dealers
    df = df[df["call_score"] > 0].copy()
    if len(df) == 0:
        return pd.DataFrame()

    # -----------------------------
    # Reason chips (UNCHANGED TAG SET; only thresholds aligned)
    # -----------------------------
    def get_reason_chips(row):
        reasons = []

        # keep these tags EXACTLY
        if row.get("due_today_total", 0) > 0:
            reasons.append("DUE_TODAY")

        od = row.get("overdue_amt_total", 0)
        try:
            od = float(od) if od is not None else 0.0
        except Exception:
            od = 0.0
        if od > 0:
            reasons.append("OVERDUE")

        if row.get("due_tomorrow_total", 0) > 0:
            reasons.append("DUE_TOMORROW")
        if row.get("due_in7_total", 0) > 0:
            reasons.append("DUE_IN7")

        # keep INACTIVE chip, but now treat 45 as early warning (same chip tag)
        if row.get("days_since_last_order", 0) >= 45:
            reasons.append("INACTIVE")

        if row.get("order_churn_risk_score", 0) > 1.5:
            reasons.append("CHURN_RISK")

        # DECLINING chip: align to 30d when present, fallback to 90d
        t30 = row.get("pct_revenue_trend_30d", None)
        if t30 is None:
            t30 = row.get("pct_revenue_trend_90d", 0)

        if (t30 is not None and float(t30) < -20) or (row.get("pct_revenue_trend_90d", 0) < -20):
            reasons.append("DECLINING")

        if row.get("revenue_gap_vs_cluster_avg_monthly_last_90d", 0) > 5000:
            reasons.append("GAP_VS_PEERS")

        return ", ".join(reasons)

    df["reason_chips"] = df.apply(get_reason_chips, axis=1)

    # -----------------------------
    # Action hint (optional: ordering aligned; not a "tag")
    # -----------------------------
    def get_action_hint(row):
        # Overdue first (align with nudge absolute priority)
        if row.get("overdue_amt_total", 0) > 0:
            return f"Follow-up on overdue {U.fmt_rs(row.get('overdue_amt_total', 0))}"

        # Sales activation/risk before due_today (align with rule priorities vs collections priorities)
        is_new_row = int(row.get("is_new_dealer", 0) or 0) == 1 or float(row.get("tenure_months", 9999) or 9999) <= 1
        no_orders_row = int(row.get("has_no_orders", 0) or 0) == 1 or float(row.get("total_orders_lifetime", 0) or 0) <= 0
        if is_new_row and no_orders_row:
            return "Sales risk: New dealer - activate & book first invoice"

        if row.get("days_since_last_order", 0) >= 90:
            return "Sales risk: Dealer inactive - call & plan visit"

        # Decline
        t30 = row.get("pct_revenue_trend_30d", None)
        try:
            t30 = float(t30) if t30 is not None else None
        except Exception:
            t30 = None
        t90 = float(row.get("pct_revenue_trend_90d", 0) or 0)
        if (t30 is not None and t30 <= -20) or (t30 is None and t90 <= -20):
            return "Sales risk: Declining - diagnose & recover"

        # Collections due today next
        if row.get("due_today_total", 0) > 0:
            return f"URGENT: Collect {U.fmt_rs(row.get('due_today_total', 0))} due today"

        # Opportunity gap
        if row.get("revenue_gap_vs_cluster_avg_monthly_last_90d", 0) > 5000:
            return "Opportunity: Close gap vs peers - upsell/cross-sell"

        # Remaining collections
        if row.get("due_tomorrow_total", 0) > 0:
            return f"Proactive call: {U.fmt_rs(row.get('due_tomorrow_total', 0))} due tomorrow"
        if row.get("due_in7_total", 0) > 0:
            return f"Reminder: {U.fmt_rs(row.get('due_in7_total', 0))} due this week"
        if row.get("order_churn_risk_score", 0) > 1.5:
            return "Sales risk: High churn - intervene immediately"

        return "Action needed"

    df["action_hint"] = df.apply(get_action_hint, axis=1)

    # Default sort by combined urgency
    df = df.sort_values("call_score", ascending=False).head(top_n)

    return df
