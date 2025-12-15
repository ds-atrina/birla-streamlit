import os
import re
import json
import math
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from ast import literal_eval

load_dotenv()

# -----------------------------
# Page config & Simplified CSS
# -----------------------------
st.set_page_config(page_title="TSM Action Dashboard", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    /* Simplified 3-color system */
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
    }

    /* Only 3 status banners */
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

    /* Simplified metric cards */
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

    /* NBA Card - Most Important */
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

    /* Action cards */
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

    /* Dealer header */
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

    .segment-stamp span {
        display: block;
        line-height: 1.2;
    }
    
    .dealer-title {
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    
    .dealer-subtitle {
        font-size: 1rem;
        opacity: 0.9;
    }

    /* Persona badges */
    .badge-row {
        margin-top: 0.5rem;
    }

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

    /* Product gaps box */
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
def safe_get(d, k, default=0):
    """
    Strict safe_get:
    - If key is missing -> raise KeyError so you immediately see which column is wrong.
    - If value is NaN -> return default.
    - If value is numeric-like -> cast to float.
    """
    if k not in d:
        raise KeyError(
            f"Column '{k}' not found in current row. "
            f"Available keys (sample): {list(d.keys())[:15]}"
        )
    
    v = d.get(k, default)
    if pd.isna(v):
        return default

    try:
        return float(v)
    except Exception:
        return v

def fmt_rs(x):
    try:
        val = float(x)
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
    """
    Sub-brand mix pie chart using 180d revenue shares.
    """
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
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02
        ),
        margin=dict(t=60, b=20, l=20, r=120),
    )
    return fig

def get_dealer_stamp(dealer: dict):
    """Returns a stamp label for the dealer header"""
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
    """Badges for dealer personas"""
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

    if 'dealer_segment_OP' in dealer:
        seg_op = dealer.get('dealer_segment_OP')
        if seg_op and not pd.isna(seg_op):
            badges.append((f"🔵 Ordering: {seg_op}", "badge"))
    
    if 'dealer_segment_BG' in dealer:
        seg_bg = dealer.get('dealer_segment_BG')
        if seg_bg and not pd.isna(seg_bg):
            badges.append((f"🟢 Billing: {seg_bg}", "badge"))
    
    return badges

def get_dealer_status(dealer: dict):
    """Status banner from recency, churn risk & trend"""
    has_no_orders = safe_get(dealer, 'has_no_orders', 0)
    is_new = safe_get(dealer, 'is_new_dealer', 0)
    
    # Special case: New dealer with no orders
    if has_no_orders == 1 and is_new == 1:
        return "attention", "🟡 NEW DEALER - NO ORDERS YET", "Dealer onboarded but hasn't placed first order"
    
    # Special case: Existing dealer with no orders (should be rare)
    if has_no_orders == 1:
        return "risk", "🔴 NO ORDER HISTORY", "Dealer exists in system but has never ordered"
    
    dsl = safe_get(dealer, 'days_since_last_order', 0)
    avg_gap = safe_get(dealer, 'avg_order_gap_180d', 0)
    trend = safe_get(dealer, 'pct_revenue_trend_90d', 0)
    churn_risk = safe_get(dealer, 'order_churn_risk_score', 0)
    
    # Priority 1: Recency
    if dsl > 90:
        return "risk", "🚨 INACTIVE", f"No order in {dsl} days - dealer may be lost"
    elif dsl > 45:
        return "risk", "🔴 AT RISK", f"No order in {dsl} days - urgent follow-up needed"
    
    # Priority 2: Churn Risk
    if churn_risk > 1.5:
        return "risk", "🔴 HIGH CHURN RISK", f"Risk score {churn_risk:.1f} - immediate action required"
    
    # Priority 3: Trend
    if trend < -10:
        return "attention", "🟡 DECLINING", f"Sales down {abs(trend):.0f}% - needs attention"
    
    # Priority 4: Growth check
    if trend > 10 and dsl < 30:
        return "healthy", "🟢 GROWING", f"Sales up {trend:.0f}% - capitalize on momentum"
    
    # Default stable
    if dsl < 30:
        return "healthy", "🟢 STABLE", "Regular ordering pattern - maintain engagement"
    else:
        return "attention", "🟡 NEEDS FOLLOW-UP", f"Last order {dsl} days ago - schedule visit"

def get_subbrand_nudges(dealer: dict):
    actions = []
    # =====================================================
    # SUB-BRAND MIX & WALLET EXPANSION
    # =====================================================
    share_allwood     = safe_get(dealer, "share_revenue_allwood_180d", 0.0)
    share_prime       = safe_get(dealer, "share_revenue_prime_180d", 0.0)
    share_allwoodpro  = safe_get(dealer, "share_revenue_allwoodpro_180d", 0.0)
    share_one         = safe_get(dealer, "share_revenue_one_180d", 0.0)
    share_calista     = safe_get(dealer, "share_revenue_calista_180d", 0.0)
    share_style       = safe_get(dealer, "share_revenue_style_180d", 0.0)
    share_alldry      = safe_get(dealer, "share_revenue_alldry_180d", 0.0)
    share_artist      = safe_get(dealer, "share_revenue_artist_180d", 0.0)
    share_samplekit   = safe_get(dealer, "share_revenue_samplekit_180d", 0.0)
    share_collaterals = safe_get(dealer, "share_revenue_collaterals_180d", 0.0)

    subbrand_shares = {
        "Allwood":      share_allwood,
        "Prime":        share_prime,
        "Allwood Pro":  share_allwoodpro,
        "One":          share_one,
        "Calista":      share_calista,
        "Style":        share_style,
        "AllDry":       share_alldry,
        "Artist":       share_artist,
        "Sample Kit":   share_samplekit,
        "Collaterals":  share_collaterals,
    }

    # Identify the dominant brand (>50%)
    dominant_brand = None
    dominant_share = 0
    for name, share in subbrand_shares.items():
        if share > 0.5:
            dominant_brand = name
            dominant_share = share
            break
    
    if not dominant_brand:
        return actions
    # ---------------------------------------------------------
    # PRODUCT MIX ACTIONS (Only 1 max to keep it simple)
    # ---------------------------------------------------------
    if dominant_brand == "Style":
        actions.append(
            f"🎨 Mix Upgrade: {dominant_share:.0f}% sales are low-margin 'Style'. "
            "Action: Pitch 'Calista' as a longer-lasting finish to upgrade customers."
        )
    elif dominant_brand == "Calista":
        actions.append(
            f"🎨 Premium Push: Good base in 'Calista', ~ {dominant_share:.0f}% of total revenue. "
            "Action: Show 'One' shade cards to premium clients for top-tier projects."
        )
    elif dominant_brand == "One":
        actions.append(
            f"💎 Protect Premium: Dealer loves 'One' ({dominant_share:.0f}%). "
            "Action: Ensure full SKU range availability so they don't switch brands."
        )
    else:
        # For other sub-brands, just nudge around dominance
        actions.append(
            f"📦 Dealer is highly dependent on {name} (~{share:.0f}% of revenue). "
            "Action: Use the relationship on this sub-brand to open conversations on 1-2 more sub-brands "
        )
    return actions

def generate_nba(dealer: dict):
    actions = []
    
    # --- DATA EXTRACTION ---
    is_new = safe_get(dealer, 'is_new_dealer', 0)
    has_no_orders = safe_get(dealer, 'has_no_orders', 0)
    
    dsl = int(safe_get(dealer, "days_since_last_order", 0))
    orders_90 = int(safe_get(dealer, "total_orders_last_90d", 0))
    
    # Financials
    rev_90 = safe_get(dealer, "total_revenue_last_90d", 0.0)
    monthly_rev = rev_90 / 3.0
    prev_90_rev = safe_get(dealer, "total_revenue_prev_90d", 0.0)
    
    # Trends
    # Calculate trend manually if key missing: (Curr - Prev) / Prev
    if prev_90_rev > 0:
        rev_trend = ((rev_90 - prev_90_rev) / prev_90_rev) * 100
    else:
        rev_trend = safe_get(dealer, "pct_revenue_trend_90d", 0.0)

    ticket_size_trend = safe_get(dealer, "pct_aov_trend_90d", 0.0) 
    
    # Peer Comparison
    cluster_avg = safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", 0.0)
    gap_to_cluster = safe_get(dealer, "revenue_gap_vs_cluster_avg_monthly_last_90d", 0.0)
    
    # Specific Flags (Assuming these boolean flags exist or are derived)
    # inactive_category = safe_get(dealer, "has_inactive_category_90d", 0) 
    # bulk_no_repeat = safe_get(dealer, "flag_bulk_order_no_repeat", 0) 

    # =====================================================
    # SCENARIO 1: NEW DEALER (Onboarded < 30 days)
    # =====================================================
    if is_new == 1:
        # Case 1.1: No Orders Yet
        if has_no_orders == 1:
            actions.append(
                f"🚀 New Dealer Activation: Onboarded but zero orders yet. "
                "Action: Pitch Hero Products (Emulsion/Primer) & 'Early Bird Scheme' (2% extra off) to start."
            )
            return actions # Stop here for new/empty dealers

        # Case 1.2: Low Orders (Below Cluster)
        if gap_to_cluster > 0:
            actions.append(
                f"📊 Bridge the Gap: Billing is {fmt_rs(abs(gap_to_cluster))} less than territory peers. "
                "Action: Push stock of fast-moving items (Hero Products) to match peer volume."
            )
        
        # Case 1.3: High Orders (Above Cluster)
        else:
            actions.append(
                f"🌟 Strong Start: Billing higher than territory peers. "
                "Action: Introduce Waterproofing Solutions to capture full wallet."
            )
        return actions

    # =====================================================
    # SCENARIO 2: EXISTING DEALER - RISKS & DROPS
    # =====================================================
    
    # Case 2.1: Inactive (Churn Risk)
    if dsl >= 90:
        lost_sales = monthly_rev * 3 if monthly_rev > 0 else 45000 # fallback
        actions.append(
            f"🚨 Urgent Reactivation: Inactive for {dsl} days (Losing ~{fmt_rs(lost_sales)} sales). "
            "Action: Call today. Check if stock is unsold or if a competitor took the counter."
        )
        return actions

    # Case 2.2: Sharp Drop (Active but dropping)
    if rev_trend < -20:
        actions.append(
            f"📉 Sales Drop: Billing down {abs(rev_trend):.0f}% vs last month. "
            "Action: Visit dealer. Check if stock is lying unsold or if a competitor took share."
        )

    # Case 2.3: Bulk Order No Repeat (Specific Behavior)
    # if bulk_no_repeat == 1:
    #     actions.append(
    #         "📦 Stock Check: Ordered bulk last quarter but hasn't repeated. "
    #         "Action: Check satisfaction with that product batch and ask for re-order."
    #     )

    # Case 2.4: Shrinking Ticket Size
    if ticket_size_trend < -10 and orders_90 >= 3:
        actions.append(
            "📉 Order Size Shrinking: Average order value is dropped in the last 90 days. "
            "Action: Check if retailer demand is slowing down or if they are splitting orders."
        )

    # =====================================================
    # SCENARIO 3: EXISTING DEALER - OPPORTUNITIES
    # =====================================================

    # Case 3.1: Inactive Category (Cross-sell recovery)
    # if inactive_category == 1:
    #     actions.append(
    #         "🔄 Category Lapse: Hasn't ordered a previously purchased category in 90+ days. "
    #         "Action: Encourage re-order of this category to capture missing sales."
    #     )

    # Case 3.2: Recovery (Bounce back)
    if rev_trend > 20 and prev_90_rev > 0:
         actions.append(
            "📈 Recovery: Billing trend recovered this month! "
            "Action: Appreciate the business and explore upsell opportunities immediately."
        )

    # Case 3.3: Underperformer (Gap vs Peers)
    if gap_to_cluster > 5000 and rev_trend > -20: # If gap exists but not crashing
        actions.append(
            f"💰 Growth Opportunity: Billing {fmt_rs(abs(gap_to_cluster))} below cluster average. "
            "Action: Identify missing SKUs compared to peers and fill the gap."
        )

    # Case 3.4: Good Performer (Momentum)
    if rev_trend > 0 and gap_to_cluster <= 0:
        actions.append(
            f"🚀 High Performer: Growing {rev_trend:.0f}% and beating territory average. "
            "Action: Introduce Waterproofing or new Premium lines to expand wallet share."
        )

    # =====================================================
    # 4. APPEND SUB-BRAND NUDGE
    # =====================================================
    # Only append if we haven't already generated a "Critical" stop-action
    # (We return early for New/Inactive, but flow through for others)
    product_nudges = get_subbrand_nudges(dealer)
    if product_nudges:
        actions.extend(product_nudges)

    # Fallback if list is empty
    if not actions:
        actions.append("🤝 Visit the dealer to identify gaps, preferences and competition.")

    return actions

def calculate_opportunity(dealer: dict):
    """Calculate revenue opportunity vs cluster"""
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
        return gap, f"Potential monthly revenue increase"
    elif gap == 0:
        return 0, "Dealer performing at par with peers"
    else:
        return gap, "Dealer performing above peer average"

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

# ----------------------------
# Local safe helpers (robust)
# ----------------------------
def is_nan(x) -> bool:
    try:
        return isinstance(x, float) and math.isnan(x)
    except Exception:
        return False

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

def flag_text(x):
    return "Yes" if x == 1 else "No"

def fmt_rs(x):
        return f"₹{to_float(x, 0.0):,.0f}"

def ensure_list(x):
    """
    Accept list/dict/None/NaN/JSON-string/Python-repr-string and return a list[dict].
    This is the critical fix for your llm_* columns.
    """
    if x is None or is_nan(x):
        return []
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        return [x]
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return []
        if s.lower() in {"none", "null", "nan"}:
            return []
        # Try JSON (rarely works if string is valid JSON)
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except Exception:
            pass
        # Fallback: Python literal repr (your common case)
        try:
            parsed = literal_eval(s)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except Exception:
            return []
    return []
    
def get_context(dealer: dict) -> str:
    """
    Generalised LLM prompt for TSM nudges with realistic MONTHLY impact.
    - Forces the model to diagnose -> pick objective -> craft invoice-level actions -> estimate impact.
    - Keeps language simple and actionable for TSMs.
    - Prevents "dead" ₹1k nudges by requiring material, plausible uplift.
    """

    # -----------------------------
    # Scenario / flags
    # -----------------------------
    is_new = to_int(safe_get(dealer, "is_new_dealer", 0), 0)
    has_no_orders = to_int(safe_get(dealer, "has_no_orders", 0), 0)
    days_since_last_order = to_int(safe_get(dealer, "days_since_last_order", 9999), 9999)
    days_until_expected_order = to_int(safe_get(dealer, "days_until_expected_order", 9999), 9999)
    trend_90d = to_float(safe_get(dealer, "pct_revenue_trend_90d", 0.0), 0.0)
    dropping_off = to_int(safe_get(dealer, "dealer_is_dropping_off", 0), 0)
    churn_risk = to_float(safe_get(dealer, "order_churn_risk_score", 0.0), 0.0)

    # -----------------------------
    # Product candidates
    # -----------------------------
    dealer_top = ensure_list(dealer.get("llm_dealer_top_products_90d"))
    terr_hero = ensure_list(dealer.get("llm_territory_top_products_90d"))
    cross_sell = ensure_list(dealer.get("llm_territory_products_in_dealer_categories"))
    repurchase = ensure_list(dealer.get("llm_repurchase_recommendations"))
    inactive_cats = ensure_list(dealer.get("llm_inactive_categories_90d"))

    # -----------------------------
    # Monthly anchors
    # -----------------------------
    total_rev_90d = to_float(safe_get(dealer, "total_revenue_last_90d", 0.0), 0.0)
    total_orders_90d = to_int(safe_get(dealer, "total_orders_last_90d", 0), 0)

    baseline_monthly_sales = (total_rev_90d / 3.0) if total_rev_90d > 0 else 0.0
    baseline_orders_per_month = (total_orders_90d / 3.0) if total_orders_90d > 0 else 0.0

    avg_order_value_90d = to_float(safe_get(dealer, "avg_order_value_last_90d", 0.0), 0.0)
    typical_invoice = avg_order_value_90d if avg_order_value_90d > 0 else (
        (total_rev_90d / total_orders_90d) if total_orders_90d > 0 else 0.0
    )

    cluster_avg_monthly = to_float(safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", 0.0), 0.0)
    territory_avg_monthly = to_float(safe_get(dealer, "territory_avg_monthly_revenue_last_90d", 0.0), 0.0)

    # -----------------------------
    # Context header
    # -----------------------------
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
- Revenue trend (90d): {trend_90d:.0f}%

BENCHMARKS (context only)
- Cluster avg monthly: {fmt_rs(cluster_avg_monthly)}
- Territory avg monthly: {fmt_rs(territory_avg_monthly)}

RISK
- Churn risk: {churn_risk:.2f}
- Dropping off: {flag_text(dropping_off)}
"""

    # -----------------------------
    # Candidate listing (simple)
    # -----------------------------
    def list_products(products):
        lines = []
        for p in products[:5]:
            base = p.get("base_product") or "N/A"
            cat = p.get("category") or ""
            lines.append(f"- {base} ({cat})")
        return "\n".join(lines) if lines else "None"

    product_block = f"""
PRODUCT CANDIDATES (use names exactly; do NOT invent products)

REPURCHASE (existing, due/overdue):
{list_products(repurchase)}

CROSS-SELL (new, inside dealer's strong categories):
{list_products(cross_sell)}

INACTIVE CATEGORY (reactivation):
{list_products(inactive_cats)}

TERRITORY HERO (for activation / expansion):
{list_products(terr_hero)}

CORE PRODUCTS (dealer already buys a lot):
{list_products(dealer_top)}
"""

    # -----------------------------
    # Generalised instruction contract
    # -----------------------------
    instructions = """
You are writing for a Territory Sales Manager (TSM).
Your output must be SIMPLE, DIRECT, SPOKEN language.
No long explanations. No jargon. No fluff.

### HARD RULES (must follow)
1) Use ONLY product names from PRODUCT CANDIDATES above. Do NOT invent products.
2) Give 2-3 actions maximum.
3) Output ONLY valid JSON. No extra text.
4) Each action must be invoice-ready: what to say/do in 1 call/visit.

### YOUR JOB (do this internally before writing)
Step 1 — Diagnose this dealer in 1 line (internally)
- Are they: activation / retention-risk / declining basket / growing expansion / range-gap?
Use ALL signals: trend, churn risk, order timing, invoice size, baseline orders/month.

Step 2 — Choose ONE primary objective for THIS MONTH (internally)
Pick only one:
- SECURE: prevent drop / keep order rhythm
- EXPAND: add more items into next invoice (basket expansion)
- RECOVER: restart an inactive category
- ACTIVATE: first order / early repeat order

Step 3 — Build actions around the NEXT INVOICE (internal logic)
If next order is expected within 7 days, assume actions are bundled into the SAME invoice.
Use basket-thinking:
- 1 action can include 2-3 products that naturally go together.
Avoid repeating actions that are basically the same “add another SKU”.

Step 4 — IMPACT (most important)
Impact = REALISTIC influenced business value THIS MONTH (next 30 days).
It can include:
- Secured revenue (ensuring SKU is included)
- Accelerated revenue (pulled into this month)
- Expanded basket value (extra line items)
Not only strict causal uplift.

Use baseline anchors:
- Sales/month
- Orders/month
- Typical invoice size

How to estimate (internal):
A) Repurchase: anchor on product typical invoice if available; otherwise typical invoice size.
B) Cross-sell: assume trial add-on inside an existing invoice.
C) Reactivation: partial recovery of past run-rate (not full comeback).
D) Territory hero: starter add-on or expansion item, sized to the dealer.

Sanity checks (internal):
- Do NOT output tiny impacts that won't motivate a TSM, unless the dealer is extremely small.
- For existing dealers, total combined uplift across all actions should usually stay within ~5-15% of baseline monthly sales.
- If churn risk is high or trend is negative, at least one action should feel like "secure the next invoice".

### OUTPUT FORMAT (strict JSON)
{
  "actions": [
    {
      "do": "Exact words/steps the TSM should say/do. Mention product names.",
      "why": "Simple business reason (1 line).",
      "impact": "~₹X-₹Y this month (basis in 3-6 words)"
    }
  ]
}
"""

    return summary_block + "\n" + product_block + "\n" + instructions

def generate_simple_ai_insights(dealer: dict):
    """Simplified AI prompt with new dealer logic"""
    
    context = get_context(dealer)
    # st.write("AI Context:", context)
    # print("AI Context:", context)
    
    try:
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )
        
        response = model.invoke(context)
        response_text = response.content if hasattr(response, 'content') else str(response)
        insights = parse_json_relaxed(response_text)
        
        if insights and 'actions' in insights:
            return insights['actions'][:3]
        else:
            return fallback_actions(dealer)
            
    except Exception:
        return fallback_actions(dealer)

def fallback_actions(dealer: dict):
    """Simple rule-based fallback actions"""
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
            "do": f"Introduce {15-products} new product categories",
            "why": "Limited product range restricts order size",
            "impact": "10-15% increase in order value"
        })
    
    return actions[:3]

def display_simple_metric(label, value, plain_text, status="healthy"):
    """Simplified metric card with only 3 colors"""
    st.markdown(f"""
    <div class='metric-card {status}'>
        <div class='metric-label'>{label}</div>
        <div class='metric-value'>{value}</div>
        <div class='metric-plain'>{plain_text}</div>
    </div>
    """, unsafe_allow_html=True)

def get_product_gaps(dealer: dict):
    """Simple product gap view based on category share columns"""
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
            share_val = float(share)
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
        # st.success(f"✅ {len(st.session_state.df):,} dealers")
    except Exception:
        uploaded = st.file_uploader("Upload CSV", type=['csv'])
        if uploaded:
            st.session_state.df = pd.read_csv(uploaded)
            st.success(f"✅ {len(st.session_state.df):,} dealers")

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
        nba_actions = generate_nba(dealer)
        
        nba_html = "<div class='nba-card'><div class='nba-title'>🎯 WHAT TO DO TODAY</div>"
        for i, action in enumerate(nba_actions, 1):
            nba_html += f"<div class='nba-action'><strong>{i}.</strong> {action}</div>"
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
            orders = int(safe_get(dealer, 'total_orders_last_90d', 0))
            orders_prev = int(safe_get(dealer, 'total_orders_prev_90d', 0))
            
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
                    actions = generate_simple_ai_insights(dealer)
                
                for i, action in enumerate(actions, 1):
                    st.markdown(f"""
                    <div class='action-card'>
                        <div class='action-title'>Action {i}: {action['do']}</div>
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
                    rank = int(safe_get(dealer, 'dealer_rank_in_territory_revenue', 0))
                    total = int(safe_get(dealer, 'territory_count_dealers', 0))
                    st.metric("Territory Rank", f"#{rank} of {total}")
                else:
                    st.info("Territory ranking not applicable - no orders yet")
                
                tenure = int(safe_get(dealer, 'tenure_months', 0))
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