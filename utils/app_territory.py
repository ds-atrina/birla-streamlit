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
    """Generate single unified action list (sales + collections) with sub-scores for filtering/sorting."""

    df = territory_df.copy()
    
    def _series(col: str) -> pd.Series:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0)
        return pd.Series(0, index=df.index, dtype="float")

    due_today = _series("due_today_total")
    overdue = _series("overdue_amt_total")
    due_tom = _series("due_tomorrow_total")
    due_in7 = _series("due_in7_total")

    dsl = _series("days_since_last_order")
    churn = _series("order_churn_risk_score")
    trend = _series("pct_revenue_trend_90d")
    gap = _series("revenue_gap_vs_cluster_avg_monthly_last_90d")

    # Sub-scores
    df['collections_score'] = 0.0
    df['sales_risk_score'] = 0.0
    df['opportunity_score'] = 0.0

    # Collections factors (highest urgency)
    df.loc[due_today > 0, 'collections_score'] += 100
    df.loc[overdue > 50000, 'collections_score'] += 80
    df.loc[due_tom > 0, 'collections_score'] += 70
    df.loc[due_in7 > 0, 'collections_score'] += 25
    # Small amount-based boost (capped)
    df['collections_score'] += (overdue / 100000).clip(lower=0, upper=50)

    # Sales risk factors
    df.loc[dsl >= 45, 'sales_risk_score'] += 60
    df.loc[churn > 1.5, 'sales_risk_score'] += 60
    df.loc[trend < -20, 'sales_risk_score'] += 50

    # Opportunity factors
    df.loc[gap > 5000, 'opportunity_score'] += 30

    # Unified score
    df['call_score'] = df['collections_score'] + df['sales_risk_score'] + df['opportunity_score']

    # Keep only actionable dealers
    df = df[df['call_score'] > 0].copy()

    if len(df) == 0:
        return pd.DataFrame()

    # Reason chips
    def get_reason_chips(row):
        reasons = []

        if row.get('due_today_total', 0) > 0:
            reasons.append('DUE_TODAY')

        od = row.get('overdue_amt_total', 0)
        try:
            od = float(od) if od is not None else 0.0
        except Exception:
            od = 0.0

        if od > 0:
            reasons.append('OVERDUE')

        if row.get('due_tomorrow_total', 0) > 0:
            reasons.append('DUE_TOMORROW')
        if row.get('due_in7_total', 0) > 0:
            reasons.append('DUE_IN7')

        if row.get('days_since_last_order', 0) >= 45:
            reasons.append('INACTIVE')
        if row.get('order_churn_risk_score', 0) > 1.5:
            reasons.append('CHURN_RISK')
        if row.get('pct_revenue_trend_90d', 0) < -20:
            reasons.append('DECLINING')
        if row.get('revenue_gap_vs_cluster_avg_monthly_last_90d', 0) > 5000:
            reasons.append('GAP_VS_PEERS')

        return ', '.join(reasons)

    df['reason_chips'] = df.apply(get_reason_chips, axis=1)

    # One-line action hint (gives the “collections list” vibe without a second list)
    def get_action_hint(row):
        if row.get('due_today_total', 0) > 0:
            return f"URGENT: Collect {U.fmt_rs(row.get('due_today_total', 0))} due today"
        if row.get('overdue_amt_total', 0) > 0:
            return f"Follow-up on overdue {U.fmt_rs(row.get('overdue_amt_total', 0))}"
        if row.get('due_tomorrow_total', 0) > 0:
            return f"Proactive call: {U.fmt_rs(row.get('due_tomorrow_total', 0))} due tomorrow"
        if row.get('due_in7_total', 0) > 0:
            return f"Reminder: {U.fmt_rs(row.get('due_in7_total', 0))} due this week"
        if row.get('days_since_last_order', 0) >= 45:
            return "Sales risk: Dealer inactive - call & plan visit"
        if row.get('order_churn_risk_score', 0) > 1.5:
            return "Sales risk: High churn - intervene immediately"
        if row.get('pct_revenue_trend_90d', 0) < -20:
            return "Sales risk: Declining - diagnose & recover"
        if row.get('revenue_gap_vs_cluster_avg_monthly_last_90d', 0) > 5000:
            return "Opportunity: Close gap vs peers - upsell/cross-sell"
        return "Action needed"

    df['action_hint'] = df.apply(get_action_hint, axis=1)

    # Default sort by combined urgency
    df = df.sort_values('call_score', ascending=False).head(top_n)

    return df
