# utils/app_dealer.py 

import pandas as pd
from utils import app_utils as U

def get_dealer_stamp(dealer: dict):
    is_new = U.safe_get(dealer, 'is_new_dealer', 0)
    has_no_orders = U.safe_get(dealer, 'has_no_orders', 0)
    if has_no_orders == 1:
        return "No Orders Yet"
    if is_new == 1:
        return "New Dealer"

    prev_90d_rev = U.safe_get(dealer, 'total_revenue_prev_90d', 0)
    last_90d_rev = U.safe_get(dealer, 'total_revenue_last_90d', 0)

    if prev_90d_rev == 0 and last_90d_rev == 0:
        return "⚠️ No Activity"
    if U.safe_get(dealer, 'dealer_is_reactivated', 0) == 1:
        return "🔄 Reactivated"
    if U.safe_get(dealer, 'dealer_is_dropping_off', 0) == 1:
        return "⚠️ Dropping Off"
    return None

def get_dealer_badges(dealer: dict):
    badges = []
    if U.safe_get(dealer, 'dealer_is_high_freq', 0) == 1:
        badges.append(("⚡ High Frequency", "badge-high-freq"))
    if U.safe_get(dealer, 'dealer_is_low_freq', 0) == 1:
        badges.append(("🐌 Low Frequency", "badge-low-freq"))
    if U.safe_get(dealer, 'is_new_dealer', 0) == 1:
        badges.append(("🆕 New", "badge-new"))
    if U.safe_get(dealer, 'dealer_is_reactivated', 0) == 1:
        badges.append(("🔄 Reactivated", "badge-reactivated"))
    if U.safe_get(dealer, 'dealer_is_dropping_off', 0) == 1:
        badges.append(("⚠️ Dropping Off", "badge-dropping"))

    seg_op = dealer.get('dealer_segment_OP')
    if seg_op and not pd.isna(seg_op):
        badges.append((f"🔵 Ordering: {seg_op}", "badge"))
    seg_bg = dealer.get('dealer_segment_BG')
    if seg_bg and not pd.isna(seg_bg):
        badges.append((f"🟢 Billing: {seg_bg}", "badge"))
    return badges

def get_dealer_status(dealer: dict):
    has_no_orders = U.safe_get(dealer, 'has_no_orders', 0)
    is_new = U.safe_get(dealer, 'is_new_dealer', 0)

    if has_no_orders == 1 and is_new == 1:
        return "attention", "🟡 NEW DEALER - NO ORDERS YET", "Dealer onboarded but hasn't placed first order"
    if has_no_orders == 1:
        return "risk", "🔴 NO ORDER HISTORY", "Dealer exists in system but has never ordered"

    dsl = U.safe_get(dealer, 'days_since_last_order', 0)
    trend = U.safe_get(dealer, 'pct_revenue_trend_90d', 0)
    churn_risk = U.safe_get(dealer, 'order_churn_risk_score', 0)

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
        share = U.safe_get(dealer, col, None)
        if share is None:
            continue
        try:
            share_val = U.to_float(share)
        except Exception:
            continue
        if share_val <= 0.0001:
            missing.append(label)
        elif share_val < threshold_low:
            low_share.append((label, share_val))

    return missing, low_share