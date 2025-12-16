import os
import re
import json
import math
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from ast import literal_eval

from nudge_tag import (
    TAG_SCHEMA,
    get_tag_family,
    assign_rule_tag_v2,
    assign_llm_tag,
    get_strength_for_tag,
)

load_dotenv()

# -----------------------------
# Page config & Simplified CSS
# -----------------------------
st.set_page_config(page_title="TSM Action Dashboard", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
    }

    .status-healthy {
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 24px rgba(72, 187, 120, 0.25);
        font-size: 1.2rem;
        font-weight: 700;
        border: 2px solid rgba(255,255,255,0.2);
    }
    .status-attention {
        background: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 24px rgba(237, 137, 54, 0.25);
        font-size: 1.2rem;
        font-weight: 700;
        border: 2px solid rgba(255,255,255,0.2);
    }
    .status-risk {
        background: linear-gradient(135deg, #f56565 0%, #c53030 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 24px rgba(245, 101, 101, 0.25);
        font-size: 1.2rem;
        font-weight: 700;
        border: 2px solid rgba(255,255,255,0.2);
    }

    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 5px solid #e2e8f0;
        margin: 0.75rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .metric-card.healthy { border-left-color: #48bb78; }
    .metric-card.attention { border-left-color: #ed8936; }
    .metric-card.risk { border-left-color: #f56565; }

    .metric-label {
        font-size: 0.85rem;
        color: #718096;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        margin: 0.5rem 0;
    }
    .metric-plain {
        font-size: 1.1rem;
        color: #4a5568;
        margin-top: 0.5rem;
        font-weight: 500;
    }

    .nba-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        margin: 1.5rem 0;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
    }
    .nba-title {
        font-size: 1.5rem;
        font-weight: 800;
        margin-bottom: 1rem;
    }
    .nba-action {
        background: rgba(255,255,255,0.2);
        padding: 1rem;
        border-radius: 8px;
        margin: 0.75rem 0;
        font-size: 1.05rem;
        border-left: 4px solid white;
    }

    .action-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 5px solid #667eea;
    }
    .action-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #2d3748;
        margin-bottom: 0.5rem;
    }
    .action-why {
        font-size: 0.95rem;
        color: #4a5568;
        margin: 0.5rem 0;
        line-height: 1.6;
    }
    .action-impact {
        background: #f7fafc;
        padding: 0.75rem;
        border-radius: 6px;
        font-size: 0.9rem;
        color: #2d3748;
        margin-top: 0.5rem;
        font-weight: 600;
    }

    .dealer-header {
        background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 1rem;
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        position: relative;
        overflow: visible;
    }
    .segment-stamp {
        position: absolute;
        top: -20px;
        right: 20px;
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #fefcbf, #ecc94b);
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        font-size: 0.7rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #744210;
        box-shadow: 0 6px 16px rgba(0,0,0,0.25);
        border: 3px solid rgba(0,0,0,0.15);
        transform: rotate(-8deg);
        padding: 0.5rem;
    }
    .segment-stamp span { display: block; line-height: 1.2; }

    .dealer-title {
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    .dealer-subtitle {
        font-size: 1rem;
        opacity: 0.9;
    }

    .badge-row { margin-top: 0.5rem; }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-right: 0.35rem;
        margin-top: 0.35rem;
        background: #edf2f7;
        color: #2d3748;
    }
    .badge-new { background: #c3dafe; color: #2c5282; }
    .badge-reactivated { background: #faf089; color: #744210; }
    .badge-high-freq { background: #9ae6b4; color: #22543d; }
    .badge-low-freq { background: #fbd38d; color: #7c2d12; }
    .badge-dropping { background: #fed7d7; color: #742a2a; }

    .product-gaps-box {
        background: #f7fafc;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        border: 1px solid #e2e8f0;
        margin-top: 0.75rem;
        font-size: 0.95rem;
        color: #2d3748;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Helpers
# -----------------------------


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
    
def safe_get(d, k, default=0):
    if k not in d:
        raise KeyError(
            f"Column '{k}' not found in current row. "
            f"Available keys (sample): {list(d.keys())[:15]}"
        )
    v = d.get(k, default)
    if pd.isna(v):
        return default
    try:
        return to_float(v)
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

def get_dealer_data(df, dealer_id):
    dealer = df[df['dealer_composite_id'] == dealer_id]
    if len(dealer) > 0:
        return dealer.iloc[0].to_dict()
    return None

def create_revenue_benchmark_chart(dealer):
    dealer_90d_average_monthly = safe_get(dealer, 'total_revenue_last_90d', 0) / 3.0
    dealer_180d_average_monthly = safe_get(dealer, 'avg_monthly_revenue_180d', 0)
    dealer_lifetime_average_monthly = safe_get(dealer, 'avg_monthly_revenue_lifetime', 0.0)

    cluster_monthly = safe_get(dealer, 'cluster_avg_monthly_revenue_last_90d', 0)
    cluster_monthly_180d = safe_get(dealer, 'cluster_avg_monthly_revenue_180d', 0)
    cluster_monthly_lifetime = safe_get(dealer, 'cluster_avg_monthly_revenue_lifetime', 0)

    terr_monthly = safe_get(dealer, 'territory_avg_monthly_revenue_last_90d', 0)
    terr_monthly_180d = safe_get(dealer, 'territory_avg_monthly_revenue_180d', 0)
    terr_monthly_lifetime = safe_get(dealer, 'territory_avg_monthly_revenue_lifetime', 0)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='This Dealer',
        x=['3-Mo Avg', '6-Mo Avg', 'Lifetime Avg'],
        y=[dealer_90d_average_monthly, dealer_180d_average_monthly, dealer_lifetime_average_monthly],
        marker_color='#667eea',
        text=[fmt_rs(dealer_90d_average_monthly), fmt_rs(dealer_180d_average_monthly), fmt_rs(dealer_lifetime_average_monthly)],
        textposition='outside',
        textfont_size=10
    ))

    fig.add_trace(go.Scatter(
        name='Cluster Avg',
        x=['3-Mo Avg', '6-Mo Avg', 'Lifetime Avg'],
        y=[cluster_monthly, cluster_monthly_180d, cluster_monthly_lifetime],
        mode='lines+markers',
        line=dict(width=3, dash='dash', color='#48bb78'),
        marker=dict(size=8, color='#48bb78')
    ))

    fig.add_trace(go.Scatter(
        name='Territory Avg',
        x=['3-Mo Avg', '6-Mo Avg', 'Lifetime Avg'],
        y=[terr_monthly, terr_monthly_180d, terr_monthly_lifetime],
        mode='lines+markers',
        line=dict(width=3, dash='dot', color='#ed8936'),
        marker=dict(size=8, color='#ed8936')
    ))

    fig.update_layout(
        title='Monthly Revenue Benchmarking vs Peers',
        height=400,
        showlegend=True,
        template='plotly_white',
        yaxis_title='Avg Monthly Revenue (₹)',
        margin=dict(t=60, b=60, l=60, r=20)
    )
    return fig

def create_order_frequency_benchmark(dealer):
    dealer_orders = safe_get(dealer, 'total_orders_last_90d', 0)
    cluster_avg = safe_get(dealer, 'cluster_avg_orders_last_90d', 0)
    terr_avg = safe_get(dealer, 'territory_avg_orders_last_90d', 0)
    terr_p80 = safe_get(dealer, 'territory_p80_orders_last_90d', 0)

    fig = go.Figure(data=[
        go.Bar(
            x=['This Dealer', 'Cluster Avg', 'Territory Avg', 'Territory Top 20%'],
            y=[dealer_orders, cluster_avg, terr_avg, terr_p80],
            marker_color=['#667eea', '#48bb78', '#48bb78', '#48bb78'],
            text=[int(dealer_orders), f'{cluster_avg:.0f}', f'{terr_avg:.0f}', f'{terr_p80:.0f}'],
            textposition='outside',
            textfont_size=11
        )
    ])
    fig.update_layout(
        title='Order Frequency Comparison (Last 90 Days)',
        height=400,
        template='plotly_white',
        yaxis_title='Number of Orders',
        showlegend=False,
        margin=dict(t=60, b=60, l=60, r=20)
    )
    return fig

def create_subbrand_mix_chart(dealer):
    subbrands = {
        "Allwood":      safe_get(dealer, "share_revenue_allwood_180d", 0.0),
        "Prime":        safe_get(dealer, "share_revenue_prime_180d", 0.0),
        "Allwood Pro":  safe_get(dealer, "share_revenue_allwoodpro_180d", 0.0),
        "One":          safe_get(dealer, "share_revenue_one_180d", 0.0),
        "Calista":      safe_get(dealer, "share_revenue_calista_180d", 0.0),
        "Style":        safe_get(dealer, "share_revenue_style_180d", 0.0),
        "AllDry":       safe_get(dealer, "share_revenue_alldry_180d", 0.0),
        "Artist":       safe_get(dealer, "share_revenue_artist_180d", 0.0),
        "Sample Kit":   safe_get(dealer, "share_revenue_samplekit_180d", 0.0),
        "Collaterals":  safe_get(dealer, "share_revenue_collaterals_180d", 0.0),
    }
    subbrands = {k: v for k, v in subbrands.items() if v and v > 0}
    if not subbrands:
        return None

    fig = go.Figure(data=[go.Pie(
        labels=list(subbrands.keys()),
        values=list(subbrands.values()),
        hole=0.4,
        textinfo="label+percent",
        textposition="inside",
        textfont_size=11,
    )])

    fig.update_layout(
        title="Sub-brand Revenue Mix (Last 6 Months)",
        height=400,
        template="plotly_white",
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
        margin=dict(t=60, b=20, l=20, r=120),
    )
    return fig

def get_dealer_stamp(dealer: dict):
    is_new = safe_get(dealer, 'is_new_dealer', 0)
    has_no_orders = safe_get(dealer, 'has_no_orders', 0)
    if has_no_orders == 1:
        return "No Orders Yet"
    if is_new == 1:
        return "New Dealer"

    prev_90d_rev = safe_get(dealer, 'total_revenue_prev_90d', 0)
    last_90d_rev = safe_get(dealer, 'total_revenue_last_90d', 0)

    if prev_90d_rev == 0 and last_90d_rev == 0:
        return "⚠️ No Activity"
    if safe_get(dealer, 'dealer_is_reactivated', 0) == 1:
        return "🔄 Reactivated"
    if safe_get(dealer, 'dealer_is_dropping_off', 0) == 1:
        return "⚠️ Dropping Off"
    return None

def get_dealer_badges(dealer: dict):
    badges = []
    if safe_get(dealer, 'dealer_is_high_freq', 0) == 1:
        badges.append(("⚡ High Frequency", "badge-high-freq"))
    if safe_get(dealer, 'dealer_is_low_freq', 0) == 1:
        badges.append(("🐌 Low Frequency", "badge-low-freq"))
    if safe_get(dealer, 'is_new_dealer', 0) == 1:
        badges.append(("🆕 New", "badge-new"))
    if safe_get(dealer, 'dealer_is_reactivated', 0) == 1:
        badges.append(("🔄 Reactivated", "badge-reactivated"))
    if safe_get(dealer, 'dealer_is_dropping_off', 0) == 1:
        badges.append(("⚠️ Dropping Off", "badge-dropping"))

    seg_op = dealer.get('dealer_segment_OP')
    if seg_op and not pd.isna(seg_op):
        badges.append((f"🔵 Ordering: {seg_op}", "badge"))
    seg_bg = dealer.get('dealer_segment_BG')
    if seg_bg and not pd.isna(seg_bg):
        badges.append((f"🟢 Billing: {seg_bg}", "badge"))
    return badges

def get_dealer_status(dealer: dict):
    has_no_orders = safe_get(dealer, 'has_no_orders', 0)
    is_new = safe_get(dealer, 'is_new_dealer', 0)

    if has_no_orders == 1 and is_new == 1:
        return "attention", "🟡 NEW DEALER - NO ORDERS YET", "Dealer onboarded but hasn't placed first order"
    if has_no_orders == 1:
        return "risk", "🔴 NO ORDER HISTORY", "Dealer exists in system but has never ordered"

    dsl = safe_get(dealer, 'days_since_last_order', 0)
    trend = safe_get(dealer, 'pct_revenue_trend_90d', 0)
    churn_risk = safe_get(dealer, 'order_churn_risk_score', 0)

    if dsl > 90:
        return "risk", "🚨 INACTIVE", f"No order in {dsl} days - dealer may be lost"
    elif dsl > 45:
        return "risk", "🔴 AT RISK", f"No order in {dsl} days - urgent follow-up needed"

    if churn_risk > 1.5:
        return "risk", "🔴 HIGH CHURN RISK", f"Risk score {churn_risk:.1f} - immediate action required"

    if trend < -10:
        return "attention", "🟡 DECLINING", f"Sales down {abs(trend):.0f}% - needs attention"

    if trend > 10 and dsl < 30:
        return "healthy", "🟢 GROWING", f"Sales up {trend:.0f}% - capitalize on momentum"

    if dsl < 30:
        return "healthy", "🟢 STABLE", "Regular ordering pattern - maintain engagement"
    else:
        return "attention", "🟡 NEEDS FOLLOW-UP", f"Last order {dsl} days ago - schedule visit"

# ----------------------------
# Local safe helpers (robust)
# ----------------------------
def is_nan(x) -> bool:
    try:
        return isinstance(x, float) and math.isnan(x)
    except Exception:
        return False

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

# -----------------------------
# RULE: Sub-brand nudges (pre-tagged) — add gating
# -----------------------------
def get_subbrand_nudges(dealer: dict, enabled: bool = True):
    if not enabled:
        return []

    # Only do mix nudges when dealer has meaningful volume
    total_rev_180d = to_float(safe_get(dealer, "total_revenue_180d", 0.0), 0.0)
    if total_rev_180d < 100000:  # ~₹1L in 180d → too small, dominance is noisy
        return []

    actions = []
    subbrand_shares = {
        "Allwood":      to_float(safe_get(dealer, "share_revenue_allwood_180d", 0.0), 0.0),
        "Prime":        to_float(safe_get(dealer, "share_revenue_prime_180d", 0.0), 0.0),
        "Allwood Pro":  to_float(safe_get(dealer, "share_revenue_allwoodpro_180d", 0.0), 0.0),
        "One":          to_float(safe_get(dealer, "share_revenue_one_180d", 0.0), 0.0),
        "Calista":      to_float(safe_get(dealer, "share_revenue_calista_180d", 0.0), 0.0),
        "Style":        to_float(safe_get(dealer, "share_revenue_style_180d", 0.0), 0.0),
        "AllDry":       to_float(safe_get(dealer, "share_revenue_alldry_180d", 0.0), 0.0),
        "Artist":       to_float(safe_get(dealer, "share_revenue_artist_180d", 0.0), 0.0),
        "Sample Kit":   to_float(safe_get(dealer, "share_revenue_samplekit_180d", 0.0), 0.0),
        "Collaterals":  to_float(safe_get(dealer, "share_revenue_collaterals_180d", 0.0), 0.0),
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
                f"🎨 Mix Upgrade: {dominant_pct:.0f}% sales are 'Style'. "
                "Action: Pitch 'Calista' as a longer-lasting finish for upgrade buyers."
            ),
            "tag": "SUBBRAND_DOMINANT_STYLE"
        })
    elif dominant_brand == "Calista":
        actions.append({
            "key": "SUBBRAND_DOMINANT_CALISTA",
            "priority": 30,
            "text": (
                f"🎨 Premium Push: 'Calista' is ~{dominant_pct:.0f}% of revenue. "
                "Action: Show 'One' shade cards to premium clients for top-tier projects."
            ),
            "tag": "SUBBRAND_DOMINANT_CALISTA"
        })
    elif dominant_brand == "One":
        actions.append({
            "key": "SUBBRAND_DOMINANT_ONE",
            "priority": 30,
            "text": (
                f"💎 Protect Premium: 'One' is {dominant_pct:.0f}% of sales. "
                "Action: Ensure full SKU range availability so they don’t switch brands."
            ),
            "tag": "SUBBRAND_DOMINANT_ONE"
        })
    else:
        actions.append({
            "key": "SUBBRAND_DOMINANT_OTHER",
            "priority": 25,
            "text": (
                f"📦 Mix Risk: ~{dominant_pct:.0f}% revenue depends on {dominant_brand}. "
                "Action: Use this strength to open 1–2 more sub-brands (reduce dependency)."
            ),
            "tag": "SUBBRAND_DOMINANT_OTHER"
        })

    return actions

# -----------------------------
# RULE: Main rule nudges — robust + ranked + deduped
# -----------------------------
def _impact_range(v: float) -> str:
    v = to_float(v or 0)
    lo, hi = 0.8 * v, 1.2 * v
    return f"~₹{lo:,.0f}-₹{hi:,.0f}"

def _estimate_rule_impact(dealer: dict, tag: str) -> str:
    # Prefer typical invoice size, else fallback
    tiv = to_float(dealer.get("avg_invoice_value_90d") or dealer.get("typical_invoice_size") or 0)
    monthly_rev = to_float(dealer.get("total_revenue_last_90d") or 0) / 3.0
    gap_to_cluster = to_float(dealer.get("revenue_gap_vs_cluster_avg_monthly_last_90d") or 0)

    # Dormant / churn: “secure the first restart order”
    if tag in {"CHURN_RISK_INACTIVE_90D", "CHURN_RISK_HIGH_SCORE", "NEW_DEALER_NO_ORDERS"}:
        basis = tiv if tiv > 0 else max(5000, 0.2 * monthly_rev)  # conservative
        return f"{_impact_range(basis)} this month (basis: first reactivation order)"

    # Gap growth: recover part of gap
    if tag in {"GROWTH_OPPORTUNITY_BELOW_CLUSTER", "GROWTH_GAP_TO_CLUSTER"} and gap_to_cluster > 0:
        basis = min(gap_to_cluster, monthly_rev * 0.3 if monthly_rev > 0 else gap_to_cluster)
        return f"{_impact_range(basis)} this month (basis: partial gap recovery)"

    # Default: small conservative add-on
    basis = tiv if tiv > 0 else 8000
    return f"{_impact_range(basis)} this month (basis: conservative add-on)"

def _why_from_tag(dealer: dict, tag: str) -> str:
    dsl = to_int(dealer.get("days_since_last_order") or 0)
    churn = to_float(dealer.get("order_churn_risk_score") or 0)
    trend = to_float(dealer.get("pct_revenue_trend_90d") or 0)

    if tag == "CHURN_RISK_INACTIVE_90D":
        return f"Dealer inactive for {dsl} days; high risk of churn."
    if tag == "CHURN_RISK_HIGH_SCORE":
        return f"High churn risk score ({churn:.2f}); needs immediate follow-up."
    if tag == "SALES_DROP_SHARP":
        return f"Revenue trend is down {abs(trend):.0f}% (90d); needs correction."
    if tag == "PRODUCT_VARIETY_LOW":
        return "Limited product variety vs peers; expanding range can lift invoice value."
    return "Rule trigger matched based on dealer’s recent performance signals."

def generate_rule_nudges(dealer: dict, max_actions: int = 2):
    raw_actions = []

    def add_action(text: str, priority: int, key: str, tag: str = None):
        raw_actions.append({
            "text": text,
            "priority": priority,
            "key": key,
            "tag": tag
        })

    # --- Robust flags / conversions ---
    is_new_flag = to_int(safe_get(dealer, "is_new_dealer", 0), 0)
    has_no_orders_flag = to_int(safe_get(dealer, "has_no_orders", 0), 0)

    total_orders_lifetime = to_int(safe_get(dealer, "total_orders_lifetime", 0), 0)
    tenure_months = to_int(safe_get(dealer, "tenure_months", 9999), 9999)

    # Treat as "activation" if no lifetime orders (even if is_new flag is wrong/missing)
    has_no_orders = (has_no_orders_flag == 1) or (total_orders_lifetime == 0)
    is_new = (is_new_flag == 1) or (tenure_months <= 1)

    dsl = to_int(safe_get(dealer, "days_since_last_order", 0), 0)
    orders_90 = to_int(safe_get(dealer, "total_orders_last_90d", 0), 0)
    prev_orders_90 = to_int(safe_get(dealer, "total_orders_prev_90d", 0), 0)

    churn_risk = to_float(safe_get(dealer, "order_churn_risk_score", 0.0), 0.0)
    dropping_off = to_int(safe_get(dealer, "dealer_is_dropping_off", 0), 0)

    # Revenue trends: use 30d for "last month"
    rev_30 = to_float(safe_get(dealer, "total_revenue_last_30d", 0.0), 0.0)
    prev_30 = to_float(safe_get(dealer, "total_revenue_prev_30d", 0.0), 0.0)
    if prev_30 > 0:
        rev_trend_30 = ((rev_30 - prev_30) / prev_30) * 100
    else:
        rev_trend_30 = to_float(safe_get(dealer, "pct_revenue_trend_30d", 0.0), 0.0)

    rev_90 = to_float(safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    prev_90_rev = to_float(safe_get(dealer, "total_revenue_prev_90d", 0.0), 0.0)
    if prev_90_rev > 0:
        rev_trend_90 = ((rev_90 - prev_90_rev) / prev_90_rev) * 100
    else:
        rev_trend_90 = to_float(safe_get(dealer, "pct_revenue_trend_90d", 0.0), 0.0)

    ticket_size_trend = to_float(safe_get(dealer, "pct_aov_trend_90d", 0.0), 0.0)
    gap_to_cluster = to_float(safe_get(dealer, "revenue_gap_vs_cluster_avg_monthly_last_90d", 0.0), 0.0)  # +ve = below peers

    # Better baselines for inactive / opportunity
    avg_monthly_180d = to_float(safe_get(dealer, "avg_monthly_revenue_180d", 0.0), 0.0)
    terr_avg_monthly = to_float(safe_get(dealer, "territory_avg_monthly_revenue_last_90d", 0.0), 0.0)
    cluster_avg_monthly = to_float(safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", 0.0), 0.0)

    baseline_monthly = max(
        (rev_90 / 3.0) if rev_90 > 0 else 0.0,
        (prev_90_rev / 3.0) if prev_90_rev > 0 else 0.0,
        avg_monthly_180d,
        terr_avg_monthly,
        cluster_avg_monthly,
        45000.0  # last fallback
    )

    # -----------------------------
    # SCENARIO 1: ACTIVATION (no orders)
    # -----------------------------
    if has_no_orders:
        potential = max(cluster_avg_monthly, terr_avg_monthly, 0.0)
        pot_txt = fmt_rs(potential) if potential > 0 else "₹0"
        add_action(
            text=(
                "🚀 Activation (First Order): Dealer has no orders yet. "
                f"Action: Start with Hero Products + a small starter basket; aim for 1st invoice this week (potential ~{pot_txt}/month vs peers)."
            ),
            priority=100,
            key="ACTIVATION_NO_ORDERS",
            tag=None
        )
    else:
        # -----------------------------
        # SCENARIO 2: INACTIVE
        # -----------------------------
        if dsl >= 90:
            # Estimate loss proportional to inactivity window (cap at 3 months for message)
            months_lost = min(3, max(1, math.ceil(dsl / 30)))
            lost_sales = baseline_monthly * months_lost
            add_action(
                text=(
                    f"🚨 Urgent Reactivation: Inactive for {dsl} days (at risk ~{fmt_rs(lost_sales)}). "
                    "Action: Call/visit today, confirm reason (stock stuck vs competitor), and lock next order date."
                ),
                priority=95 + (5 if churn_risk >= 4 or dropping_off == 1 else 0),
                key="INACTIVE_90D",
                tag=None
            )
        else:
            # -----------------------------
            # SCENARIO 3: DECLINE / RISK
            # -----------------------------
            if rev_trend_30 <= -20:
                add_action(
                    text=(
                        f"📉 Sales Drop (30d): Billing down {abs(rev_trend_30):.0f}% vs last month. "
                        "Action: Visit + check competitor share, pending claims, and push one immediate replenishment order."
                    ),
                    priority=85 + (5 if churn_risk >= 4 or dropping_off == 1 else 0),
                    key="SALES_DROP_30D",
                    tag=None
                )

            # AOV drop only if orders are NOT rising sharply (avoid false alarms like “many small orders now”)
            if ticket_size_trend < -10 and orders_90 >= 3:
                orders_growth = ((orders_90 - prev_orders_90) / prev_orders_90 * 100) if prev_orders_90 > 0 else 0.0
                if orders_growth < 25:
                    add_action(
                        text=(
                            "📉 Order Size Shrinking: Average invoice value is down in the last 90 days. "
                            "Action: Check if they’re splitting orders; push bundle deals to lift ticket size."
                        ),
                        priority=65,
                        key="AOV_SHRINKING",
                        tag=None
                    )

            # -----------------------------
            # SCENARIO 4: GAP / GROWTH
            # -----------------------------
            if gap_to_cluster > 5000 and rev_trend_30 > -20:
                add_action(
                    text=(
                        f"💰 Growth Gap: Billing is {fmt_rs(abs(gap_to_cluster))} below peer average. "
                        "Action: Compare with peer basket (missing SKUs/sub-brands) and close the gap this month."
                    ),
                    priority=60,
                    key="GAP_TO_CLUSTER",
                    tag=None
                )

            # -----------------------------
            # SCENARIO 5: HIGH PERFORMER (dedupe “Recovery” vs “High performer”)
            # -----------------------------
            if rev_trend_90 > 20 and gap_to_cluster <= 0:
                add_action(
                    text=(
                        f"🚀 High Performer: Up {rev_trend_90:.0f}% vs previous 90 days and above peers. "
                        "Action: Appreciate + push 1 new premium line / waterproofing to expand wallet share."
                    ),
                    priority=55,
                    key="HIGH_PERFORMER",
                    tag=None
                )
            elif rev_trend_90 > 20 and gap_to_cluster > 0:
                add_action(
                    text=(
                        "📈 Recovery: Trend is up, but still below peers. "
                        "Action: Lock repeat SKUs + add 1 fast-moving add-on to sustain the recovery."
                    ),
                    priority=50,
                    key="RECOVERY_BELOW_PEERS",
                    tag=None
                )

    # Sub-brand nudges: only when NOT in activation/inactive/decline mode
    enable_subbrand = (
        (not has_no_orders) and (dsl < 60) and (rev_trend_30 > -15)
    )
    raw_actions.extend(get_subbrand_nudges(dealer, enabled=enable_subbrand))

    if not raw_actions:
        add_action(
            text="🤝 Visit the dealer to identify gaps, preferences and competition.",
            priority=10,
            key="GENERIC_VISIT",
            tag="CROSS_SELL_CATEGORY"
        )

    # --- Rank + dedupe + cap ---
    raw_actions = sorted(raw_actions, key=lambda x: x.get("priority", 0), reverse=True)
    seen = set()
    final_raw = []
    for a in raw_actions:
        k = a.get("key") or a.get("tag") or a.get("text")
        if k in seen:
            continue
        seen.add(k)
        final_raw.append(a)
        if len(final_raw) >= max_actions:
            break

    # --- Tagging (your existing pipeline) ---
    tagged_actions = []
    for item in final_raw:
        action_text = item.get("text", "")
        tag = item.get("tag")

        if not tag or tag not in TAG_SCHEMA:
            rule_tag, rule_conf = assign_rule_tag_v2(action_text, dealer)  # use v2 to get confidence
            tag = rule_tag  # ensures tag exists in schema

            do = action_text  # simplest: keep as-is; or split on "Action:" if you want
            why = _why_from_tag(dealer, tag)
            impact = _estimate_rule_impact(dealer, tag)

            tagged_actions.append({
                "text": do,          # keep text == do (same as LLM normalization)
                "do": do,
                "why": why,
                "impact": impact,

                "tag": tag,
                "tag_family": get_tag_family(tag),
                "priority_base": TAG_SCHEMA[tag]["priority_base"],
                "strength_score": get_strength_for_tag(tag),

                # Fill the LLM columns for rule nudges so CSV never has blanks
                "llm_primary_tag": tag,
                "llm_tag_confidence": to_float(rule_conf),
                "llm_tag_basis": f"rule_engine; tag={tag}",
            })

    return tagged_actions


# -----------------------------
# LLM Prompt + LLM Nudges (PER-ACTION TAG)
# -----------------------------
ALLOWED_LLM_PRIMARY_TAGS = {
    "LLM_REPURCHASE_DUE",
    "LLM_INACTIVE_CATEGORY",
    "LLM_CROSS_SELL",
    "LLM_TERRITORY_HERO",
    "LLM_GENERAL",
}

def get_context(dealer: dict) -> str:
    is_new = to_int(safe_get(dealer, "is_new_dealer", 0), 0)
    has_no_orders = to_int(safe_get(dealer, "has_no_orders", 0), 0)
    days_since_last_order = to_int(safe_get(dealer, "days_since_last_order", 9999), 9999)
    days_until_expected_order = to_int(safe_get(dealer, "days_until_expected_order", 9999), 9999)
    trend_90d = to_float(safe_get(dealer, "pct_revenue_trend_90d", 0.0), 0.0)
    # Expose trend 30d (if available)
    trend_30d = to_float(safe_get(dealer, "pct_revenue_trend_30d", 0.0), 0.0) 
    dropping_off = to_int(safe_get(dealer, "dealer_is_dropping_off", 0), 0)
    churn_risk = to_float(safe_get(dealer, "order_churn_risk_score", 0.0), 0.0)

    dealer_top = ensure_list(dealer.get("llm_dealer_top_products_90d"))
    terr_hero = ensure_list(dealer.get("llm_territory_top_products_90d"))
    cross_sell = ensure_list(dealer.get("llm_territory_products_in_dealer_categories"))
    repurchase = ensure_list(dealer.get("llm_repurchase_recommendations"))
    inactive_cats = ensure_list(dealer.get("llm_inactive_categories_90d"))

    total_rev_90d = to_float(safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    total_orders_90d = to_int(safe_get(dealer, "total_orders_last_90d", 0), 0)
    # Expose Zero Activity Flag
    flag_zero_activity_90d = to_int(safe_get(dealer, "flag_zero_activity_90d", 0), 0)

    baseline_monthly_sales = (total_rev_90d / 3.0) if total_rev_90d > 0 else 0.0
    baseline_orders_per_month = (total_orders_90d / 3.0) if total_orders_90d > 0 else 0.0

    avg_order_value_90d = to_float(safe_get(dealer, "avg_order_value_last_90d", 0.0), 0.0)
    typical_invoice = avg_order_value_90d if avg_order_value_90d > 0 else (
        (total_rev_90d / total_orders_90d) if total_orders_90d > 0 else 0.0
    )

    cluster_avg_monthly = to_float(safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", 0.0), 0.0)
    territory_avg_monthly = to_float(safe_get(dealer, "territory_avg_monthly_revenue_last_90d", 0.0), 0.0)

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
- Tenure: {to_int(safe_get(dealer, 'tenure_months', 0), 0)} months

BASELINE (MONTHLY)
- Sales / month (last 90d avg): {fmt_rs(baseline_monthly_sales)}
- Orders / month (last 90d avg): {baseline_orders_per_month:.1f}
- Typical invoice size: {fmt_rs(typical_invoice)}
- Days since last order: {days_since_last_order if has_no_orders == 0 else "N/A"}
- Expected next order in: {days_until_expected_order} days
- Orders in last 90d: {total_orders_90d}
- Zero activity flag (90d): {flag_text(flag_zero_activity_90d)}
- Revenue trend (90d): {trend_90d:.0f}%
- Revenue trend (30d): {trend_30d:.0f}%

BENCHMARKS (context only)
- Cluster avg monthly: {fmt_rs(cluster_avg_monthly)}
- Territory avg monthly: {fmt_rs(territory_avg_monthly)}

RISK
- Churn risk: {churn_risk:.2f}
- Dropping off: {flag_text(dropping_off)}
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

    instructions = f"""
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
  - **CRITICAL NO OVERLAP REFINEMENT:** If you select **LLM\_INACTIVE\_CATEGORY**, you **MUST NOT** reference any specific product that is also flagged for **DUE\_FOR\_WINBACK** or **DUE\_FOR\_REORDER** in the `PRODUCT CANDIDATES` list within the action's `do` or `why` fields. Focus only on the category theme.

DORMANT / ZERO-ACTIVITY OVERRIDE (STRICT)
- **Check based on Summary Block fields:** If Orders in last 90d = 0 OR Days since last order >= 120 OR Zero activity flag (90d) is YES:
  - Return **EXACTLY ONE** action only.
  - primary_tag **MUST** be **LLM\_GENERAL**.
  - That ONE action must include a “starter basket” (2–3 items) pulled from TERRITORY HERO and/or REPURCHASE candidates (if any).
  - Do **NOT** output **LLM\_INACTIVE\_CATEGORY / LLM\_TERRITORY\_HERO / LLM\_CROSS\_SELL** as separate actions for dormant dealers.

CANDIDATE FIDELITY
- Use ONLY product/category names from PRODUCT CANDIDATES. Never invent names.
- Don't recompute metrics (don't recalc % or lift). Use fields as given.

PRIORITY (HIGH-IMPACT ORDER)
1. **CRITICAL SECURITY (OVERRIDE):** If the dealer is DECLINING or CHURN RISK is high, you MUST prioritize **HIGH-URGENCY REPURCHASE** or a **DEFEND SHARE** action as Action 1.
1a. **DEFEND CORE REVENUE (REQUIRED ACTION 1 or 2):** For declining or high-churn dealers, Action 1 or 2 **MUST** be a **DEFEND SHARE** action (Securing *LLM\_DEALER\_TOP\_PRODUCTS* or *LLM\_TERRITORY\_HERO* with lift = 0). Frame this using **LLM\_TERRITORY\_HERO** or **LLM\_GENERAL**.
2. **SECURE/RECOVER:** If REPURCHASE has WINBACK/HIGH/overdue, or INACTIVE CATEGORY has a high peer gap, prioritize these (highest impact first).
3. **DECLINING / HIGH-RISK GUARDRAIL:** If Revenue trend (30d) <= -20% OR Churn risk > 1.0 OR Dropping off is YES: Do **NOT** use **LLM\_CROSS\_SELL** unless no repurchase/defend candidates exist.
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
- Inactive category: partial recovery only; cap at <= past\_mo and usually <= 50% of peer\_mo.
- Cross/territory hero new product: trial add-on; keep conservative.
- **IMPACT FORMAT STRICT:** impact must **ALWAYS** be a range "~₹X-₹Y". If you only have one calculated value V, output "~₹(0.8V)-₹(1.2V)".
- **IMPACT FOR GENERAL/DROPPED OFF (CRITICAL):** Must provide a **numeric range** (~₹X-₹Y) based on the dealer's **Typical Invoice Size** or their **Baseline Monthly Sales** to represent the revenue secured from the first re-activation order.
- **DEFEND\_SHARE IMPACT RULE (NO GUESSING):** If recommendation\_type is DEFEND\_SHARE or lift = 0: impact MUST be "~₹X-₹Y" and computed from **ONE** provided field only: **benchmark\_monthly\_sales** OR **avg\_monthly\_sales** (from CORE PRODUCTS) OR **typical\_invoice**. tag\_basis MUST include the exact field used (e.g., "bench=10230" or "dealer\_top\_mo=80000").

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

def generate_ai_nudges(dealer: dict, model=None):
    context = get_context(dealer)

    try:
        if model is None:
            model = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                temperature=0.1,
            )

        response = model.invoke(context)
        response_text = response.content if hasattr(response, "content") else str(response)
        insights = parse_json_relaxed(response_text)

        if isinstance(insights, dict) and isinstance(insights.get("actions"), list):
            actions = insights.get("actions", [])[:2]
        else:
            actions = fallback_actions(dealer)[:2]

    except Exception:
        actions = fallback_actions(dealer)[:2]

    tagged_actions = []
    for action in actions:
        if not isinstance(action, dict):
            action = {"do": str(action), "why": "", "impact": ""}

        llm_tag = action.get("primary_tag")
        if llm_tag not in ALLOWED_LLM_PRIMARY_TAGS:
            llm_tag = None

        tag = llm_tag or assign_llm_tag(action, dealer)

        tagged_actions.append({
            "do": action.get("do", ""),
            "why": action.get("why", ""),
            "impact": action.get("impact", ""),
            "tag": tag,
            "tag_family": get_tag_family(tag),
            "priority_base": TAG_SCHEMA[tag]["priority_base"],
            "strength_score": get_strength_for_tag(tag),
            "llm_primary_tag": action.get("primary_tag"),
            "llm_tag_confidence": action.get("tag_confidence"),
            "llm_tag_basis": action.get("tag_basis"),
        })

    return tagged_actions

def fallback_actions(dealer: dict):
    is_new = safe_get(dealer, 'is_new_dealer', 0)
    has_no_orders = safe_get(dealer, 'has_no_orders', 0)
    dsl = safe_get(dealer, 'days_since_last_order', 0)
    opp_value, _ = calculate_opportunity(dealer)

    actions = []
    if is_new == 1 and has_no_orders == 1:
        actions.append({
            "do": "Call dealer immediately to activate account",
            "why": "New dealer onboarded but hasn't placed first order",
            "impact": f"Potential {fmt_rs(opp_value)}/month based on peers"
        })
    elif dsl > 30:
        actions.append({
            "do": f"Call dealer immediately - {dsl} days overdue",
            "why": "Re-engage before dealer becomes inactive",
            "impact": "Resume regular ordering pattern"
        })

    if opp_value > 0:
        actions.append({
            "do": "Close revenue gap to similar dealers",
            "why": "Dealer has capacity to grow",
            "impact": f"{fmt_rs(opp_value)} additional monthly revenue"
        })

    products = safe_get(dealer, 'count_base_product_last_90d', 0)
    if products < 15:
        actions.append({
            "do": f"Introduce {15-int(products)} new product categories",
            "why": "Limited product range restricts order size",
            "impact": "10-15% increase in order value"
        })

    return actions[:3]

def display_simple_metric(label, value, plain_text, status="healthy"):
    st.markdown(f"""
    <div class='metric-card {status}'>
        <div class='metric-label'>{label}</div>
        <div class='metric-value'>{value}</div>
        <div class='metric-plain'>{plain_text}</div>
    </div>
    """, unsafe_allow_html=True)

def get_product_gaps(dealer: dict):
    category_cols = [
        ("Interior", "share_interior_180d"),
        ("Exterior", "share_exterior_180d"),
        ("Enamel", "share_enamel_180d"),
        ("Waterproofing", "share_waterproofing_180d"),
        ("Texture", "share_texture_180d"),
        ("Ancillary", "share_ancillary_180d"),
    ]

    missing = []
    low_share = []
    threshold_low = 0.05

    for label, col in category_cols:
        if col not in dealer:
            continue
        share = safe_get(dealer, col, None)
        if share is None:
            continue
        try:
            share_val = to_float(share)
        except Exception:
            continue
        if share_val <= 0.0001:
            missing.append(label)
        elif share_val < threshold_low:
            low_share.append((label, share_val))

    return missing, low_share

# -----------------------------
# Session State
# -----------------------------
if 'df' not in st.session_state:
    st.session_state.df = None
if 'selected_dealer' not in st.session_state:
    st.session_state.selected_dealer = None

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>🎯 TSM Actions</h1>", unsafe_allow_html=True)
    st.markdown("---")

    st.subheader("📄 Load Data")
    try:
        file_path = 'clustered_dealer_master_improved_with_prodrecs.csv'
        st.session_state.df = pd.read_csv(file_path)
    except Exception:
        # uploaded = st.file_uploader("Upload CSV", type=['csv'])
        # if uploaded:
        #     st.session_state.df = pd.read_csv(uploaded)
        #     st.success(f"✅ {len(st.session_state.df):,} dealers")
        st.error('No data found')

    if st.session_state.df is not None:
        st.markdown("---")
        st.subheader("🔍 Find Dealer")

        search_type = st.radio("Search by:", ["Dealer ID", "Territory", "Area", "Priority"], label_visibility="collapsed")
        df = st.session_state.df

        if search_type == "Dealer ID":
            dealer_list = sorted(df['dealer_composite_id'].dropna().unique())
            selected = st.selectbox("Dealer ID:", dealer_list, key="dealer_select")
            st.session_state.selected_dealer = selected

        elif search_type == "Territory":
            territory = st.selectbox("Territory:", sorted(df['territory_name'].dropna().unique()))
            dealers_in_territory = df[df['territory_name'] == territory]['dealer_composite_id'].dropna().unique()
            selected = st.selectbox("Select Dealer:", dealers_in_territory)
            st.session_state.selected_dealer = selected

        elif search_type == "Area":
            area = st.selectbox("Area:", sorted(df['asm_name'].dropna().unique()))
            dealers_in_area = df[df['asm_name'] == area]['dealer_composite_id'].dropna().unique()
            selected = st.selectbox("Select Dealer:", dealers_in_area)
            st.session_state.selected_dealer = selected

        else:
            priority_col = 'priority_tier_OP'
            priority_tiers = sorted(df[priority_col].dropna().unique(), reverse=True)
            priority_tier = st.selectbox("Priority (Orders):", priority_tiers)
            dealers_priority = df[df[priority_col] == priority_tier]['dealer_composite_id'].dropna().unique()
            selected = st.selectbox("Select Dealer:", dealers_priority)
            st.session_state.selected_dealer = selected
            
# -----------------------------
# Main Content
# -----------------------------
if st.session_state.df is not None and st.session_state.selected_dealer is not None:
    dealer = get_dealer_data(st.session_state.df, st.session_state.selected_dealer)

    if dealer:
        # Header
        segment_label = get_dealer_stamp(dealer)
        if segment_label:
            st.markdown(f"""
            <div class='dealer-header'>
                <div class='segment-stamp'>
                    <span>{segment_label}</span>
                </div>
                <div class='dealer-title'>
                    🏪 {dealer.get('customer_name', dealer.get('dealer_composite_id',''))}
                </div>
                <div class='dealer-subtitle'>
                    📍 {dealer.get('city_name','')}, {dealer.get('state_name','')} • 
                    Territory: {dealer.get('territory_name','')} • 
                    Area: {dealer.get('asm_name','')}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='dealer-header'>
                <div class='dealer-title'>
                    🏪 {dealer.get('customer_name', dealer.get('dealer_composite_id',''))}
                </div>
                <div class='dealer-subtitle'>
                    📍 {dealer.get('city_name','')}, {dealer.get('state_name','')} • 
                    Territory: {dealer.get('territory_name','')} • 
                    Area: {dealer.get('asm_name','')}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Persona badges
        badges = get_dealer_badges(dealer)
        if badges:
            badge_html = "<div class='badge-row'>"
            for text, cls in badges:
                badge_html += f"<span class='badge {cls}'>{text}</span>"
            badge_html += "</div>"
            st.markdown(badge_html, unsafe_allow_html=True)
        
        # Status banner
        status_level, status_text, status_msg = get_dealer_status(dealer)
        st.markdown(
            f"<div class='status-{status_level}'>{status_text}<br><small>{status_msg}</small></div>",
            unsafe_allow_html=True
        )
        
        # NEXT BEST ACTION
        st.markdown("<br>", unsafe_allow_html=True)
        rule_nudges = generate_rule_nudges(dealer)
        
        nba_html = "<div class='nba-card'><div class='nba-title'>🎯 WHAT TO DO TODAY</div>"
        for i, nudge in enumerate(rule_nudges, 1):
            tag_badge = f"<span style='background: rgba(255,255,255,0.3); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;'>{nudge['tag']}</span>"
            nba_html += f"<div class='nba-action'><strong>{i}.</strong> {nudge['text']} {tag_badge}</div>"
        nba_html += "</div>"
        st.markdown(nba_html, unsafe_allow_html=True)
        
        # 8 CORE METRICS
        st.subheader("📊 Key Metrics (Last 90 days)")
        
        has_no_orders = safe_get(dealer, 'has_no_orders', 0)
        last_90d_rev = safe_get(dealer, 'total_revenue_last_90d', 0)
        prev_90d_rev = safe_get(dealer, 'total_revenue_prev_90d', 0)

        col1, col2, col3, col4 = st.columns(4)
        
        # Monthly Sales
        with col1:
            monthly_rev = last_90d_rev / 3.0
            trend = safe_get(dealer, 'pct_revenue_trend_90d', 0)

            if has_no_orders == 1:
                display_simple_metric(
                    "Monthly Sales (Potential)",
                    fmt_rs(safe_get(dealer, 'cluster_avg_monthly_revenue_last_90d', 0)),
                    "Based on similar dealers",
                    "attention"
                )
            elif monthly_rev == 0:
                display_simple_metric(
                    "Monthly Sales (Avg)",
                    fmt_rs(0),
                    "No sales activity",
                    "risk"
                )
            elif trend > 10:
                display_simple_metric(
                    "Monthly Sales (Avg)",
                    fmt_rs(monthly_rev),
                    f"📈 Growing: Up {trend:.0f}%",
                    "healthy"
                )
            elif trend > 0:
                display_simple_metric(
                    "Monthly Sales (Avg)",
                    fmt_rs(monthly_rev),
                    f"↗️ Stable growth: +{trend:.0f}%",
                    "healthy"
                )
            elif trend > -10:
                display_simple_metric(
                    "Monthly Sales (Avg)",
                    fmt_rs(monthly_rev),
                    "Stable: No major change",
                    "attention"
                )
            else:
                display_simple_metric(
                    "Monthly Sales (Avg)",
                    fmt_rs(monthly_rev),
                    f"📉 Declining: -{abs(trend):.0f}%",
                    "risk"
                )

        # Orders
        with col2:
            orders =to_int(safe_get(dealer, 'total_orders_last_90d', 0))
            orders_prev =to_int(safe_get(dealer, 'total_orders_prev_90d', 0))
            
            if has_no_orders == 1:
                display_simple_metric(
                    "Total Orders",
                    0,
                    "No orders yet - activation needed",
                    "risk"
                )
            elif orders > orders_prev:
                display_simple_metric(
                    "Total Orders",
                    orders,
                    f"📈 Up from {orders_prev} → {orders}",
                    "healthy"
                )
            elif orders == orders_prev and orders > 0:
                display_simple_metric(
                    "Total Orders",
                    orders,
                    f"→ Same as before ({orders})",
                    "healthy"
                )
            else:
                display_simple_metric(
                    "Total Orders",
                    orders,
                    f"📉 Down from {orders_prev} → {orders}",
                    "attention"
                )
        
        # Days Since Last Order
        with col3:
            if has_no_orders == 1:
                display_simple_metric(
                    "Days Since Last Order",
                    "N/A",
                    "Never ordered - new dealer",
                    "attention"
                )
            else:
                dsl = safe_get(dealer, 'days_since_last_order', 0)
                avg_gap = safe_get(dealer, 'avg_order_gap_180d', 0)

                if avg_gap > 0 and dsl >= 2 * avg_gap:
                    status = "risk"
                elif dsl <= 30:
                    status = "healthy"
                elif dsl <= 45:
                    status = "attention"
                else:
                    status = "risk"

                if avg_gap > 0:
                    cycle_text = f"Generally orders every {avg_gap:.0f} days"
                else:
                    if dsl <= 30:
                        cycle_text = "Recently ordered"
                    elif dsl <= 45:
                        cycle_text = "Overdue - follow up"
                    else:
                        cycle_text = "URGENT - Very overdue"

                display_simple_metric(
                    "Days Since Last Order",
                    f"{int(dsl)} days",
                    cycle_text,
                    status
                )
        
        # Product Variety
        with col4:
            if has_no_orders == 1:
                display_simple_metric(
                    "Product Variety",
                    "0 products",
                    "Start with hero products",
                    "attention"
                )
            else:
                products = safe_get(dealer, 'count_base_product_last_90d', 0)
                gap = safe_get(dealer, 'base_product_gap_vs_cluster_avg_last_90d', 0)
                if gap >= 10:
                    display_simple_metric(
                        "Product Variety",
                        f"{int(products)} products",
                        "Very limited - cross-sell",
                        "attention"
                    )
                elif gap >= 5:
                    display_simple_metric(
                        "Product Variety",
                        f"{int(products)} products",
                        "Room to expand",
                        "attention"
                    )
                else:
                    display_simple_metric(
                        "Product Variety",
                        f"{int(products)} products",
                        "Excellent variety",
                        "healthy"
                    )
        
        # Second row: 4 metrics
        st.markdown("<br>", unsafe_allow_html=True)
        col5, col6, col7, col8 = st.columns(4)
        
        # Churn Risk
        with col5:
            if has_no_orders == 1:
                display_simple_metric(
                    "Churn Risk",
                    "N/A",
                    "Not applicable - no order history",
                    "attention"
                )
            else:
                churn_risk = safe_get(dealer, 'order_churn_risk_score', 0)
                
                if churn_risk < 1.0:
                    display_simple_metric(
                        "Churn Risk",
                        f"{churn_risk:.1f}",
                        "Low risk - stable dealer",
                        "healthy"
                    )
                elif churn_risk < 1.5:
                    display_simple_metric(
                        "Churn Risk",
                        f"{churn_risk:.1f}",
                        "Moderate risk - monitor",
                        "attention"
                    )
                else:
                    display_simple_metric(
                        "Churn Risk",
                        f"{churn_risk:.1f}",
                        "High risk - urgent action",
                        "risk"
                    )
        
        # Priority Score
        with col6:
            priority = safe_get(dealer, 'priority_score_OP', 0)
            
            if priority >= 70:
                display_simple_metric(
                    "Priority Score",
                    f"{priority:.0f}/100",
                    "Top priority - visit ASAP",
                    "risk"
                )
            elif priority >= 50:
                display_simple_metric(
                    "Priority Score",
                    f"{priority:.0f}/100",
                    "High priority - plan visit",
                    "attention"
                )
            else:
                display_simple_metric(
                    "Priority Score",
                    f"{priority:.0f}/100",
                    "Stable - routine check",
                    "healthy"
                )
        
        # Revenue Opportunity
        with col7:
            opp_value, opp_desc = calculate_opportunity(dealer)

            if opp_value > 0:
                display_simple_metric(
                    "Revenue Opportunity",
                    fmt_rs(opp_value),
                    opp_desc,
                    "attention"
                )
            elif opp_value == 0:
                display_simple_metric(
                    "Revenue Position",
                    fmt_rs(0),
                    "Performing at par vs peers",
                    "healthy"
                )
            else:
                display_simple_metric(
                    "Revenue Position",
                    "Above Average",
                    "Performing well vs peers",
                    "healthy"
                )

        # Avg Order Value
        with col8:
            if has_no_orders == 1:
                cluster_aov = safe_get(dealer, 'cluster_avg_aov_last_90d', 0)
                display_simple_metric(
                    "Target AOV",
                    fmt_rs(cluster_aov),
                    "Expected based on peers",
                    "attention"
                )
            else:
                aov = safe_get(dealer, 'avg_order_value_last_90d', 0)
                aov_trend = safe_get(dealer, 'pct_aov_trend_90d', 0)
                
                if aov_trend > 10:
                    display_simple_metric(
                        "Avg Order Value (90d)",
                        fmt_rs(aov),
                        f"📈 Ticket size up {aov_trend:.0f}%",
                        "healthy"
                    )
                elif aov_trend > 0:
                    display_simple_metric(
                        "Avg Order Value (90d)",
                        fmt_rs(aov),
                        f"↗️ Slight growth ({aov_trend:.0f}%)",
                        "healthy"
                    )
                elif aov_trend > -10:
                    display_simple_metric(
                        "Avg Order Value (90d)",
                        fmt_rs(aov),
                        "Stable ticket size",
                        "attention"
                    )
                else:
                    display_simple_metric(
                        "Avg Order Value (90d)",
                        fmt_rs(aov),
                        f"📉 Ticket size down {abs(aov_trend):.0f}%",
                        "attention"
                    )
    
        # Benchmarking charts
        if has_no_orders == 0:
            st.markdown("---")
            st.subheader("📈 Performance Benchmarking & Sub-brand Intelligence")

            col_bench1, col_bench2, col_bench3 = st.columns(3)

            with col_bench1:
                fig_rev = create_revenue_benchmark_chart(dealer)
                st.plotly_chart(fig_rev, width='stretch')

            with col_bench2:
                fig_orders = create_order_frequency_benchmark(dealer)
                st.plotly_chart(fig_orders, width='stretch')

            with col_bench3:
                fig_subbrand = create_subbrand_mix_chart(dealer)
                if fig_subbrand:
                    st.plotly_chart(fig_subbrand, width='stretch')
                else:
                    st.info("No sub-brand data available for this dealer")
        else:
            st.markdown("---")
            st.info("📊 Benchmarking charts will be available once dealer places first order")

        # Tabs for detailed info
        st.markdown("---")
        tab1, tab2, tab3 = st.tabs(["💡 Smart Actions", "📊 Details", "ℹ️ How to Use"])
        
        with tab1:
            st.subheader("AI-Powered Action Plan")
            if st.button("🤖 Generate Custom Actions"):
                with st.spinner("Analyzing dealer patterns..."):
                    actions = generate_ai_nudges(dealer)

                for i, action in enumerate(actions, 1):
                    tag_color = "#667eea" if action['tag_family'] == 'LLM' else "#48bb78"
                    st.markdown(f"""
                    <div class='action-card' style='border-left-color: {tag_color};'>
                        <div class='action-title'>
                            Action {i}: {action['do']}
                            <span style='background: {tag_color}; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem;'>{action['tag']}</span>
                        </div>
                        <div class='action-why'><strong>Why:</strong> {action['why']}</div>
                        <div class='action-impact'>💰 Impact: {action['impact']}</div>
                    </div>
                    """, unsafe_allow_html=True)

        
        with tab2:
            st.subheader("Additional Details")
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("### Revenue Breakdown")
                if has_no_orders == 1:
                    st.metric("Potential (based on peers)", fmt_rs(safe_get(dealer, 'cluster_avg_monthly_revenue_last_90d', 0)))
                    st.info("No order history yet - metrics will appear after first order")
                else:
                    st.metric("Last 90 days", fmt_rs(safe_get(dealer, 'total_revenue_last_90d', 0)))
                    st.metric("Previous 90 days", fmt_rs(safe_get(dealer, 'total_revenue_prev_90d', 0)))
                    st.metric("Lifetime Revenue", fmt_rs(safe_get(dealer, 'total_revenue_lifetime', 0)))
                    st.metric("Avg Order Value (90d)", fmt_rs(safe_get(dealer, 'avg_order_value_last_90d', 0)))
            
            with c2: 
                st.markdown("### Territory Position")
                if has_no_orders == 0:
                    rank =to_int(safe_get(dealer, 'dealer_rank_in_territory_revenue', 0))
                    total =to_int(safe_get(dealer, 'territory_count_dealers', 0))
                    st.metric("Territory Rank", f"#{rank} of {total}")
                else:
                    st.info("Territory ranking not applicable - no orders yet")
                
                tenure =to_int(safe_get(dealer, 'tenure_months', 0))
                st.metric("Tenure", f"{tenure} months")
                
                is_new = safe_get(dealer, 'is_new_dealer', 0)
                dealer_type = "🆕 New Dealer (Last 30 days)" if is_new == 1 else "Existing Dealer"
                st.metric("Dealer Type", dealer_type)

            # Product Mix & Gaps
            if has_no_orders == 0:
                st.markdown("### Product Mix & Gaps")
                missing_cats, low_share_cats = get_product_gaps(dealer)
                pg_html = "<div class='product-gaps-box'>"

                if not missing_cats and not low_share_cats:
                    pg_html += "✅ This dealer is well diversified across key categories."
                else:
                    if missing_cats:
                        pg_html += "<strong>Not buying yet:</strong> " + ", ".join(missing_cats) + "<br>"
                    if low_share_cats:
                        low_strs = [
                            f"{label} (~{share*100:.0f}% of sales)"
                            for label, share in low_share_cats
                        ]
                        pg_html += "<strong>Low share categories:</strong> " + ", ".join(low_strs)
                    pg_html += "<br><br>💡 Use these as primary cross-sell focus areas in your next visit."
                pg_html += "</div>"

                st.markdown(pg_html, unsafe_allow_html=True)
        
        with tab3:
            st.markdown("""
            ## How to Use This Dashboard
            
            ### 🎯 Start Here: Next Best Action
            The **blue card at top** tells you EXACTLY what to do today. Focus on these 1-3 actions first.
            
            ### 🚦 Status Colors (Only 3)
            - **🟢 Green (Healthy)**: Dealer is doing well - maintain relationship  
            - **🟡 Yellow (Needs Attention)**: Schedule visit within 1-2 weeks  
            - **🔴 Red (At Risk)**: URGENT - call or visit immediately  
            
            ### 🆕 New Dealer vs Existing Dealer
            
            **New Dealers (Last 30 days):**
            - **No Orders Yet**: Focus on activation and first order
            - **Low Billing**: Focus on upselling to match peer average
            - **Good Billing**: Focus on cross-selling and expansion
            
            **Existing Dealers (30+ days):**
            - **Inactive 90+ days**: Urgent reactivation needed
            - **Declining**: Focus on recovery and gap closure
            - **Growing**: Focus on momentum and wallet expansion
            
            ### 📊 8 Core Metrics
            
            **1. Monthly Sales (Avg)**  
            - For new dealers with no orders: Shows potential based on similar dealers
            - For active dealers: Shows if sales are growing, flat, or declining  
            
            **2. Orders (Last 3 Months)**  
            - Number of orders in the last 90 days  
            - Shows if order frequency is going up or down  
            
            **3. Days Since Last Order**  
            - For new dealers: Shows "Never ordered" status
            - For active dealers: Shows if dealer is overdue vs normal cycle  
            
            **4. Product Variety**  
            - How many different products the dealer buys  
            - More variety = bigger basket and stronger relationship  
            
            **5. Churn Risk**  
            - How likely the dealer is to stop ordering  
            - Higher score = more risk (not applicable for new dealers with no orders)
            
            **6. Priority Score**  
            - How urgently this dealer needs attention  
            - Higher = visit sooner  
            
            **7. Revenue Opportunity**  
            - How much more this dealer could spend monthly vs similar dealers  
            
            **8. Avg Order Value**  
            - For new dealers: Target AOV based on peers
            - For active dealers: Average ticket size and trend
            
            ### 📱 Field Visit Checklist
            
            **For New Dealers (No Orders):**
            1. Check potential opportunity vs cluster average
            2. Prepare hero product presentation
            3. Understand dealer's customer base
            4. Focus on getting first order placed
            
            **For New Dealers (With Orders):**
            1. Compare billing vs cluster average
            2. If underperforming → upsell focus
            3. If performing well → cross-sell opportunities
            4. Establish regular ordering rhythm
            
            **For Existing Dealers:**
            1. Check the **"WHAT TO DO TODAY"** card  
            2. Look at **Days Since Last Order** and cycle deviation  
            3. Note **Revenue Opportunity** and trends
            4. Check **Product Mix & Gaps** for cross-sell ideas  
            5. Generate AI actions for concrete talking points  
            
            ### 🎯 Success Tips
            - **Priority 1**: New dealers with no orders (activate immediately)
            - **Priority 2**: Dealers with Priority Score > 70
            - **Priority 3**: Dealers with > 45 days since last order
            - **Cross-sell** to dealers with < 15 products or clear gaps
            - **Celebrate growth** with dealers showing positive trends
            - **Use cluster comparisons** to set realistic targets
            """)
else:
    st.markdown("<h1 class='main-header'>🎯 TSM Action Dashboard</h1>", unsafe_allow_html=True)
    
    st.info("👈 **Get Started:** Load your dealer data and select a dealer from the sidebar")
    
    st.markdown("""
    ## Welcome to Your Action Dashboard
    
    This tool gives you **clear, simple actions** for each dealer visit.
    
    ### What Makes This Different?
    
    ✅ **No technical jargon** - Plain language anyone can understand  
    ✅ **Only 3 colors** - Green (good), Yellow (attention), Red (urgent)  
    ✅ **Next Best Action** - Tells you exactly what to do today  
    ✅ **8 core metrics** - Not 50+ confusing numbers  
    ✅ **Simple status** - Healthy, Needs Attention, or At Risk  
    ✅ **Smart dealer categorization** - New vs Existing dealer logic
    ✅ **Rupee opportunities** - Real money potential, not just percentages  
    
    ### New Dealer Intelligence
    
    The dashboard automatically recognizes:
    - 🆕 **New dealers** (onboarded in last 30 days)
    - 📦 **No orders yet** (activation needed)
    - 📊 **Low billing** (vs similar dealers - upsell opportunity)
    - 🚀 **Good performance** (cross-sell opportunity)
    
    ### The Most Important Part
    
    Every dealer page starts with **"WHAT TO DO TODAY"** - a blue card with 1-3 specific actions.
    
    **That's it. That's all you need to look at.**
    
    Everything else is extra detail if you want it.
    
    ### Quick Start
    
    1. Upload your CSV file (or it loads automatically)  
    2. Search for a dealer  
    3. Read the blue **"WHAT TO DO TODAY"** card  
    4. Take those actions  
    5. Done!  
    
    ### Example Actions You'll See
    
    **For New Dealers:**
    - 📞 "Call to activate - no orders yet"
    - 📊 "Billing ₹12K less than peers - upsell opportunity"
    - 🚀 "Strong start - introduce additional categories"
    
    **For Existing Dealers:**
    - 📞 "Call dealer today - 42 days since last order"  
    - 🛒 "Cross-sell 5 new product categories"  
    - 📅 "Set up bi-weekly ordering schedule"  
    - 💡 "Investigate 15% sales drop vs peers"  
    """)