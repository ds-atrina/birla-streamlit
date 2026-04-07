# app.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # birla/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import logging  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from utils import app_utils as U  # noqa: E402
from utils import app_charts as C  # noqa: E402

# ------------------------------------------------------------
# Nudges: NEW (priority) + OLD (legacy)
# Supports both repo layouts:
#   - utils.app_* (common)
#   - utils.app_* (packaged)
# ------------------------------------------------------------
try:
    from utils import app_new_nudges as N_NEW  # type: ignore
    # from utils import app_nudges as N_OLD      # type: ignore
except Exception:  # pragma: no cover
    from utils import app_new_nudges as N_NEW  # type: ignore
    # from utils import app_nudges as N_OLD      # type: ignore

from utils import app_territory as T  # noqa: E402
from utils import app_dealer as D  # noqa: E402
from utils import app_state as S  # noqa: E402
from utils import app_data as DATA  # noqa: E402
from utils import app_ui as UI  # noqa: E402

ENABLE_COLLECTIONS = False
ENABLE_RECO = True

st.set_page_config(page_title="TSM Action Dashboard", page_icon="🎯", layout="wide")

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# Config
# -----------------------------
FILE_PATH = "processed_final_dealer_master_mar26.csv"
FILE_PATH = FILE_PATH.replace("../", "")

COLOR_MAP = {
    "OVERDUE": "#dc2626",
    "CHURN_RISK": "#991b1b",
    "DECLINING": "#9a3412",
    "DUE_TODAY": "#f97316",
    "DUE_TOMORROW": "#d97706",
    "DUE_IN7": "#a16207",
    "INACTIVE": "#7c2d12",
    "GAP_VS_PEERS": "#0891b2",
}

# -----------------------------
# Init
# -----------------------------
S.AppState.init()
UI.inject_css()

# ============================================================
# NUDGES: Combining + Rendering (UPDATED for Territory+ASM multi)
# ============================================================
def _dedupe_nudges(nudges):
    """
    De-dupe by (tag, level, classification).
    IMPORTANT: tags may repeat across territory vs asm now; do NOT dedupe purely on tag.
    """
    seen = set()
    out = []
    for n in (nudges or []):
        if not isinstance(n, dict):
            continue
        tag = str(n.get("tag") or "").strip()
        lvl = str(n.get("level") or "").strip()
        cls = str(n.get("classification") or "").strip()
        key = (tag, lvl, cls)
        if tag and key in seen:
            continue
        if tag:
            seen.add(key)
        out.append(n)
    return out


def generate_combined_rule_nudges(dealer: dict):
    """
    New nudges first, then legacy nudges; remove duplicates.
    NOTE: Since NEW now produces BOTH territory+ASM variants, dedupe considers level/classification.
    """
    new_nudges = []
    old_nudges = []
    try:
        new_nudges = N_NEW.generate_rule_nudges(dealer) or []
    except Exception:
        new_nudges = []
    # try:
    #     old_nudges = N_OLD.generate_rule_nudges(dealer) or []
    # except Exception:
    #     old_nudges = []

    return _dedupe_nudges(list(new_nudges) + list(old_nudges))


def _get_tags(rule_nudges: list[dict], prefix: str) -> list[str]:
    """Return all tags matching a prefix, preserving order."""
    out = []
    for n in (rule_nudges or []):
        tag = str(n.get("tag") or "")
        if tag.startswith(prefix):
            out.append(tag)
    return out


def _ordering_bucket_label(tag: str) -> str:
    mapping = {
        "ORDERING_NEW_NO_ORDERS": "New Dealer • No orders yet",
        "ORDERING_NEW_LOW": "New Dealer • Low orders (Upsell)",
        "ORDERING_NEW_HIGH": "New Dealer • High orders (Cross-sell)",
        "ORDERING_INACTIVE_CATEGORY": "Existing Dealer • Inactive category (Reorder)",
        "ORDERING_INACTIVE_90D": "Existing Dealer • Inactive 90+ days (Reactivate)",
        "ORDERING_UNDERPERFORMER": "Existing Dealer • Underperformer (Upsell)",
        "ORDERING_GOOD_PERFORMER": "Existing Dealer • Good performer (Cross-sell)",
        "ORDERING_ASM_CADENCE_GAP": "ASM • Cadence gap",
    }
    return mapping.get(tag, "Ordering Bucket")


def _payment_bucket_label(tag: str) -> str:
    mapping = {
        "PAY_OD_DEALER": "OD Dealers (Credit blocked)",
        "PAY_NEARING_OD": "At Risk (CEI<70) • Nearing OD",
        "PAY_PAYMENT_DISCIPLINE": "At Risk (CEI<70) • Payment Discipline",
        "PAY_GOOD_PAYER_NEARING_OD": "Good Payer (CEI≥70) • Nearing OD Reminder",
        "PAY_GOOD_PAYER": "Good Payer (CEI≥70) • Maintain discipline",
    }
    return mapping.get(tag, "Payment Bucket")


def _badge_for_level(level: str) -> str:
    s = (level or "").strip().lower()
    if s == "asm":
        return "ASM"
    if s == "territory":
        return "Territory"
    if s == "dealer":
        return "Dealer"
    return (level or "Level").upper()


def _group_rule_nudges(rule_nudges: list[dict]) -> dict:
    """
    Group nudges for clean UI:
      - payments
      - ordering_territory
      - ordering_asm
      - ordering_other (dealer/unknown)
      - other (everything else)
    """
    groups = {
        "payments": [],
        "ordering_territory": [],
        "ordering_asm": [],
        "ordering_other": [],
        "other": [],
    }
    for n in (rule_nudges or []):
        ntype = str(n.get("nudge_type") or "").strip().lower()
        tag = str(n.get("tag") or "")
        lvl = str(n.get("level") or "").strip().lower()
        
        if ntype == "payment" or tag.startswith("PAY_") or tag.startswith("PAYMENT_"):
            groups["payments"].append(n)
        elif ntype == "ordering" or tag.startswith("ORDERING_"):
            if lvl == "territory":
                groups["ordering_territory"].append(n)
            elif lvl == "asm":
                groups["ordering_asm"].append(n)
            else:
                groups["ordering_other"].append(n)
        else:
            groups["other"].append(n)
    return groups


def _render_action_cards(nudges: list[dict], title: str):
    if not nudges:
        return

    st.markdown(f"### {title}")
    for i, action in enumerate(nudges, 1):
        impact_html = ""
        if action.get("impact"):
            impact_html = f"<div class='action-impact'>💰 Impact: {UI.esc(action['impact'])}</div>"

        lvl_badge = _badge_for_level(str(action.get("level") or ""))
        cls = str(action.get("classification") or "").strip()
        cls_badge = f" • {UI.esc(cls)}" if cls else ""

        st.markdown(
            f"""
            <div class='action-card'>
                <div class='action-title'>
                    {UI.esc(action.get('do', ''))}
                    <span style='background:#111827;color:white;padding:0.25rem 0.5rem;border-radius:4px;
                                 font-size:0.7rem;margin-left:0.5rem;'>
                        {UI.esc(action.get('tag', ''))}
                    </span>
                    <span style='background:#334155;color:white;padding:0.25rem 0.5rem;border-radius:4px;
                                 font-size:0.7rem;margin-left:0.5rem;'>
                        {UI.esc(lvl_badge)}{cls_badge}
                    </span>
                </div>
                <div class='action-why'><strong>Why:</strong> {UI.esc(action.get('why', ''))}</div>
                {impact_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# Navigation callbacks
# ============================================================
def _on_territory_change():
    t = st.session_state.get("territory_select")
    if t:
        S.AppState.navigate_to_territory(t)


def _on_dealer_change_from_territory():
    d = st.session_state.get("dealer_in_territory_select")
    if d:
        S.AppState.navigate_to_dealer(d)


def _on_dealer_change_direct():
    d = st.session_state.get("dealer_select")
    if d:
        S.AppState.navigate_to_dealer(d)


# ============================================================
# Existing sections (unchanged except small safety)
# ============================================================
def render_dealer_charts_section(dealer: dict) -> None:
    """Charts in ONE ROW (like before)."""
    has_no_orders = U.safe_get(dealer, "has_no_orders", 0)
    if has_no_orders == 1:
        st.markdown("---")
        st.info("📊 Benchmarking charts will be available once the dealer places the first order.")
        return

    st.markdown("---")
    st.subheader("📈 Performance Benchmarking & Sub-brand Intelligence")

    c1, c2, c3 = st.columns(3)

    with c1:
        fig = C.create_revenue_benchmark_chart(dealer)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        fig = C.create_order_frequency_benchmark(dealer)
        st.plotly_chart(fig, use_container_width=True)

    with c3:
        fig = C.create_subbrand_mix_chart(dealer)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sub-brand data available for this dealer.")


def render_territory_dashboard(df: pd.DataFrame, territory_name: str, show_debug: bool = False) -> None:
    territory_df = DATA.get_territory_df(df, territory_name)
    if territory_df.empty:
        st.error(f"No data found for territory: {territory_name}")
        return

    asm = territory_df["asm_name"].iloc[0] if "asm_name" in territory_df.columns else "N/A"

    st.markdown(
        f"""
        <div class='dealer-header'>
            <div class='dealer-title'>🗺️ Territory Dashboard: {UI.esc(territory_name)}</div>
            <div class='dealer-subtitle'>{len(territory_df)} dealers • ASM: {UI.esc(asm)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    health = T.calculate_territory_health(territory_df)
    st.subheader("🏥 Territory Health Snapshot")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        UI.metric_card("Total Dealers", f"{health['total_dealers']}", "Mapped dealers", "healthy")
    with c2:
        status = "healthy" if health["active_rate"] >= 70 else "attention" if health["active_rate"] >= 50 else "risk"
        UI.metric_card("Active (90d)", f"{health['active_dealers']}", f"{health['active_rate']:.0f}% active", status)
    with c3:
        status = "risk" if health["high_churn_count"] >= 10 else "attention" if health["high_churn_count"] >= 5 else "healthy"
        UI.metric_card("High Churn Count", f"{health['high_churn_count']}", "Dealers needing follow-up", status)
    with c4:
        status = "risk" if health["declining_count"] >= 8 else "attention" if health["declining_count"] >= 4 else "healthy"
        UI.metric_card("Declining Dealers", f"{health['declining_count']}", "Sales drop vs prev 90d", status)
    with c5:
        status = "healthy" if health["revenue_trend_pct"] >= 0 else "attention" if health["revenue_trend_pct"] >= -5 else "risk"
        UI.metric_card("Revenue (90d)", U.fmt_rs(health["total_revenue_90d"]), f"{health['revenue_trend_pct']:+.0f}% vs prev", status)

    if ENABLE_COLLECTIONS:
        st.markdown("---")
        collections = T.calculate_territory_collections(territory_df)
        st.subheader("💰 Territory Collections Snapshot")

        r1 = st.columns(3)
        r2 = st.columns(4)
        with r1[0]:
            UI.metric_card("Total Overdue", U.fmt_rs(collections["total_overdue"]), "Needs action", "risk" if collections["total_overdue"] > 0 else "healthy")
        with r1[1]:
            UI.metric_card("Total Outstanding", U.fmt_rs(collections["total_os"]), "Open invoices", "attention" if collections["total_os"] > 0 else "healthy")
        with r1[2]:
            UI.metric_card("Due Today", U.fmt_rs(collections["total_due_today"]), "Prioritize today’s calls", "risk" if collections["total_due_today"] > 0 else "healthy")

        with r2[0]:
            UI.metric_card("Due Today Only", U.fmt_rs(collections["total_due_today_only"]), "Call today", "attention" if collections["total_due_today_only"] > 0 else "healthy")
        with r2[1]:
            UI.metric_card("Due Tomorrow", U.fmt_rs(collections["total_due_tomorrow"]), "Prep tomorrow", "attention" if collections["total_due_tomorrow"] > 0 else "healthy")
        with r2[2]:
            UI.metric_card("Due in 7 Days", U.fmt_rs(collections["total_due_in7"]), "Plan this week", "attention" if collections["total_due_in7"] > 0 else "healthy")
        with r2[3]:
            pct = (collections["dealers_with_overdue"] / max(1, health["total_dealers"])) * 100
            status = "risk" if pct >= 25 else "attention" if pct >= 10 else "healthy"
            UI.metric_card("Dealers with Overdues", f"{collections['dealers_with_overdue']}", f"{pct:.0f}% of territory", status)

    st.markdown("---")

    action_df = T.generate_combined_call_list(territory_df, top_n=200)

    st.subheader("🎯 Today's Action List")
    st.markdown("*Priority ranked list - select what to include + optional reason filters.*")

    rowA = st.columns([1, 1], vertical_alignment="center")
    option_list = ["Sales risk", "Opportunities"]
    if ENABLE_COLLECTIONS:
        option_list.append("Collections")
    with rowA[0]:
        st.caption("Include in ranking")
        include_sel = st.segmented_control(
            "Include",
            options=option_list,
            default=option_list,
            selection_mode="multi",
            label_visibility="collapsed",
        )
    with rowA[1]:
        st.caption("Show top")
        top_n_show = st.slider("Show top", min_value=5, max_value=50, value=15, step=5, label_visibility="collapsed")

    include = []
    if "Collections" in include_sel:
        include.append("Collections")
    if "Sales risk" in include_sel:
        include.append("Sales risk")
    if "Opportunities" in include_sel:
        include.append("Opportunities")

    all_reasons = DATA.extract_all_reasons(action_df, reason_col="reason_chips")

    st.caption("Filter by reasons (optional)")
    reason_filter = st.segmented_control(
        "Reasons",
        options=all_reasons,
        default=[],
        selection_mode="multi",
        label_visibility="collapsed",
    )

    if action_df.empty:
        st.info("No high-priority dealers today - territory is in good shape!")
        return

    if not include:
        st.info("Select at least one of Collections / Sales risk / Opportunities.")
        return

    action_df = action_df.copy()
    action_df["active_score"] = 0.0
    if "Collections" in include:
        action_df["active_score"] += action_df.get("collections_score", 0)
    if "Sales risk" in include:
        action_df["active_score"] += action_df.get("sales_risk_score", 0)
    if "Opportunities" in include:
        action_df["active_score"] += action_df.get("opportunity_score", 0)

    action_df = action_df[action_df["active_score"] > 0].sort_values("active_score", ascending=False)

    if reason_filter:
        action_df = DATA.filter_by_any_reason(action_df, selected_reasons=reason_filter, reason_col="reason_chips")

    action_df = action_df.head(top_n_show)

    UI.render_action_cards(
        action_df=action_df,
        score_col="active_score",
        color_map=COLOR_MAP,
        fmt_rs_fn=U.fmt_rs,
        on_open=S.AppState.navigate_to_dealer,
    )

    if ENABLE_COLLECTIONS:
        st.info(
            f"📊 Overdue Concentration: Top 10 dealers = **{collections['overdue_concentration_pct']:.0f}%** "
            "of total overdue - focus collection here."
        )

def _prio_class(p: str) -> str:
    p = (p or "").strip().upper()
    if p == "HIGH":
        return "high"
    if p == "MODERATE":
        return "moderate"
    if p == "LOW":
        return "low"
    return "none"

def _render_reco_cards_compact(items, max_items: int = 3):
    if not items:
        st.info("No data available")
        return
    items = (items or [])[:max_items]
    for it in items:
        name = UI.esc(it.get("name", "N/A"))
        pr = (it.get("priority") or "").strip().upper()
        why = UI.esc(it.get("why") or "")
        border_color = "#48bb78" if pr == "HIGH" else "#ed8936" if pr == "MODERATE" else "#a0aec0"
        st.markdown(
            f"""<div class='action-card' style='border-left-color:{border_color};padding:1rem;margin:0.5rem 0;'>
  <div class='action-title' style='font-size:0.95rem;'>
    {name}
    <span style='background:#111827;color:white;padding:0.2rem 0.5rem;border-radius:4px;font-size:0.65rem;margin-left:0.5rem;'>{UI.esc(pr)}</span>
  </div>
  <div class='action-why' style='font-size:0.85rem;margin-top:0.3rem;'>{why}</div>
</div>""",
            unsafe_allow_html=True,
        )

# ============================================================
# Dealer Dashboard (UPDATED nudges rendering)
# ============================================================
def render_dealer_dashboard(df: pd.DataFrame, dealer_id: str) -> None:
    dfi = st.session_state.get("df_indexed")
    if dfi is None or dealer_id not in dfi.index:
        st.error("Dealer not found.")
        return

    dealer = dfi.loc[dealer_id].to_dict()

    stamp = D.get_dealer_stamp(dealer)
    UI.render_dealer_header(
        customer_name=U.safe_get(dealer, "customer_name", U.safe_get(dealer, "dealer_composite_id", "")),
        dealer_id=dealer_id,
        city=U.safe_get(dealer, "city_name", ""),
        state=U.safe_get(dealer, "state_name", ""),
        territory=U.safe_get(dealer, "territory_name", ""),
        asm=U.safe_get(dealer, "asm_name", ""),
        stamp_label=stamp,
    )

    badges = D.get_dealer_badges(dealer)
    if badges:
        UI.render_badges(badges)

    status_level, status_text, status_msg = D.get_dealer_status(dealer)
    UI.render_status_banner(status_level, status_text, status_msg)

    st.subheader("🎯 Dealer Action Plan")

    # All nudges together
    rule_nudges = generate_combined_rule_nudges(dealer)
    if rule_nudges:
        for i, action in enumerate(rule_nudges, 1):
            lvl = str(action.get("level") or "").strip().lower()

            lvl_text = ""
            if lvl == "asm":
                lvl_text = "ASM benchmark"
            elif lvl == "territory":
                lvl_text = "Territory benchmark"
            
            tag_badge = f"<span style='background:#111827;color:white;padding:0.25rem 0.5rem;border-radius:4px;font-size:0.7rem;margin-left:0.5rem;'>{UI.esc(action.get('tag', ''))}</span>"
            
            lvl_badge = ""
            if lvl_text:
                lvl_badge = f"<span style='background:#334155;color:white;padding:0.25rem 0.5rem;border-radius:4px;font-size:0.7rem;margin-left:0.5rem;'>{UI.esc(lvl_text)}</span>"
            
            impact_html = ""
            if action.get("impact"):
                impact_html = f"<div style='margin-top:0.5rem;font-size:0.85rem;color:#4a5568;'><strong>💰 Impact:</strong> {UI.esc(action['impact'])}</div>"

            st.markdown(
                f"""
                <div class='action-card'>
                    <div class='action-title'>{UI.esc(action.get('do', ''))}{tag_badge}{lvl_badge}</div>
                    <div class='action-why' style='margin-top:0.5rem;'><strong>Why:</strong> {UI.esc(action.get('why', ''))}</div>
                    {impact_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("✅ No urgent actions for this dealer.")

    # ------------------------------------------------------------
    # Dealer classification (SHOW ALL matched buckets now)
    # ------------------------------------------------------------
    st.markdown("---")
    st.subheader("🧩 Dealer Classification")

    pay_tags = _get_tags(rule_nudges, "PAY_")
    ord_tags = _get_tags(rule_nudges, "ORDERING_")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Payments**")
        if pay_tags:
            for t in pay_tags:
                st.caption(f"• **{_payment_bucket_label(t)}**  •  `{t}`")
        else:
            st.caption("• No payment bucket matched")

    with c2:
        st.markdown("**Ordering Pattern**")
        if ord_tags:
            # show label + level (important now)
            for n in (rule_nudges or []):
                tag = str(n.get("tag") or "")
                if not tag.startswith("ORDERING_"):
                    continue
                lvl = _badge_for_level(str(n.get("level") or ""))
                st.caption(f"• **{_ordering_bucket_label(tag)}**  •  `{tag}`  •  _{lvl}_")
        else:
            st.caption("• No ordering bucket matched")

    # Product Recommendations
    st.markdown("---")
    st.subheader("📦 Product Recommendations")

    prod_ui = N_NEW.generate_product_rec_nudges(dealer)

    # Dealer level
    st.markdown("**Dealer**")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Most Ordered (Upsell)")
        _render_reco_cards_compact(prod_ui.get("dealer_most_ordered"))
    with c2:
        st.caption("Repurchase Due (Upsell)")
        _render_reco_cards_compact(prod_ui.get("dealer_repurchase"))

    # Territory level
    # st.markdown("**Territory**")
    # t1, t2 = st.columns(2)
    # with t1:
    #     st.caption("Heroes Not Buying (Cross-sell within categories)")
    #     _render_reco_cards_compact(prod_ui.get("territory_heroes"))
    # with t2:
    #     st.caption("New Categories (Cross-sell outside categories)")
    #     _render_reco_cards_compact(prod_ui.get("territory_new_categories"))

    # ASM level (keys must match generate_product_rec_nudges in app_new_nudges)
    # Keep 2 columns to avoid cramped cards/UI breakage.
    st.markdown("**ASM**")
    a1, a2 = st.columns(2)
    with a1:
        st.caption("ASM Heroes (Cross-sell, based on dealer's top product categories)")
        _render_reco_cards_compact(prod_ui.get("asm_hero_top"))
    with a2:
        st.caption("ASM heroes in dealer categories (Cross-sell, based on similar dealers in area (same dealer category))")
        _render_reco_cards_compact(prod_ui.get("asm_hero_in_dealer_categories"))

    st.caption("New categories (cross-sell outside)")
    _render_reco_cards_compact(prod_ui.get("area_new_categories"))

    st.markdown("---")

    # Rest of metrics section
    st.subheader("📊 Key Metrics (Last 90 days)")

    has_no_orders = U.safe_get(dealer, "has_no_orders", 0)
    last_90d_rev = U.safe_get(dealer, "total_revenue_last_90d", 0)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        monthly_rev = (last_90d_rev or 0) / 3.0
        trend = U.safe_get(dealer, "pct_revenue_trend_90d", 0)

        if has_no_orders == 1:
            UI.metric_card("Monthly Sales (Potential)", U.fmt_rs(U.safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", 0)), "Based on similar dealers", "attention")
        elif monthly_rev == 0:
            UI.metric_card("Monthly Sales (Avg)", U.fmt_rs(0), "No sales activity", "risk")
        elif trend > 10:
            UI.metric_card("Monthly Sales (Avg)", U.fmt_rs(monthly_rev), f"📈 Growing: Up {trend:.0f}%", "healthy")
        elif trend > 0:
            UI.metric_card("Monthly Sales (Avg)", U.fmt_rs(monthly_rev), f"↗️ Stable growth: +{trend:.0f}%", "healthy")
        elif trend > -10:
            UI.metric_card("Monthly Sales (Avg)", U.fmt_rs(monthly_rev), "Stable: No major change", "attention")
        else:
            UI.metric_card("Monthly Sales (Avg)", U.fmt_rs(monthly_rev), f"📉 Declining: -{abs(trend):.0f}%", "risk")

    with col2:
        orders = U.to_int(U.safe_get(dealer, "total_orders_last_90d", 0))
        orders_prev = U.to_int(U.safe_get(dealer, "total_orders_prev_90d", 0))
        if has_no_orders == 1:
            UI.metric_card("Total Orders", 0, "No orders yet - activation needed", "risk")
        elif orders > orders_prev:
            UI.metric_card("Total Orders", orders, f"📈 Up from {orders_prev} → {orders}", "healthy")
        elif orders == orders_prev and orders > 0:
            UI.metric_card("Total Orders", orders, f"→ Same as before ({orders})", "healthy")
        else:
            UI.metric_card("Total Orders", orders, f"📉 Down from {orders_prev} → {orders}", "attention")

    with col3:
        if has_no_orders == 1:
            UI.metric_card("Days Since Last Order", "N/A", "Never ordered - new dealer", "attention")
        else:
            dsl = U.safe_get(dealer, "days_since_last_order", 0)
            avg_gap = U.safe_get(dealer, "avg_order_gap_180d", 0)
            if avg_gap > 0 and dsl >= 2 * avg_gap:
                status = "risk"
            elif dsl <= 30:
                status = "healthy"
            elif dsl <= 45:
                status = "attention"
            else:
                status = "risk"
            cycle_text = f"Generally orders every {avg_gap:.0f} days" if avg_gap > 0 else ("Recently ordered" if dsl <= 30 else "Overdue - follow up" if dsl <= 45 else "URGENT - Very overdue")
            UI.metric_card("Days Since Last Order", f"{int(dsl)} days", cycle_text, status)

    with col4:
        if has_no_orders == 1:
            UI.metric_card("Product Variety", "0 products", "Start with hero products", "attention")
        else:
            products = U.safe_get(dealer, "count_base_product_last_90d", 0)
            gap = U.safe_get(dealer, "base_product_gap_vs_cluster_avg_last_90d", 0)
            if gap >= 10:
                UI.metric_card("Product Variety", f"{int(products)} products", "Very limited - cross-sell", "attention")
            elif gap >= 5:
                UI.metric_card("Product Variety", f"{int(products)} products", "Room to expand", "attention")
            else:
                UI.metric_card("Product Variety", f"{int(products)} products", "Excellent variety", "healthy")

    st.markdown("<br>", unsafe_allow_html=True)
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        if has_no_orders == 1:
            UI.metric_card("Churn Risk", "N/A", "Not applicable - no order history", "attention")
        else:
            churn_risk = U.safe_get(dealer, "order_churn_risk_score", 0)
            if churn_risk < 1.0:
                UI.metric_card("Churn Risk", f"{churn_risk:.1f}", "Low risk - stable dealer", "healthy")
            elif churn_risk < 1.5:
                UI.metric_card("Churn Risk", f"{churn_risk:.1f}", "Moderate risk - monitor", "attention")
            else:
                UI.metric_card("Churn Risk", f"{churn_risk:.1f}", "High risk - urgent action", "risk")

    with col6:
        priority = U.safe_get(dealer, "priority_score_OP", 0)
        if priority >= 70:
            UI.metric_card("Priority Score", f"{priority:.0f}/100", "Top priority - visit ASAP", "risk")
        elif priority >= 50:
            UI.metric_card("Priority Score", f"{priority:.0f}/100", "High priority - plan visit", "attention")
        else:
            UI.metric_card("Priority Score", f"{priority:.0f}/100", "Stable - routine check", "healthy")

    with col7:
        opp_value, opp_desc = U.calculate_opportunity(dealer)
        if opp_value > 0:
            UI.metric_card("Revenue Opportunity", U.fmt_rs(opp_value), opp_desc, "attention")
        elif opp_value == 0:
            UI.metric_card("Revenue Position", U.fmt_rs(0), "Performing at par vs peers", "healthy")
        else:
            UI.metric_card("Revenue Position", "Above Average", "Performing well vs peers", "healthy")

    with col8:
        if has_no_orders == 1:
            cluster_aov = U.safe_get(dealer, "cluster_avg_aov_last_90d", 0)
            UI.metric_card("Target AOV", U.fmt_rs(cluster_aov), "Expected based on peers", "attention")
        else:
            aov = U.safe_get(dealer, "avg_order_value_last_90d", 0)
            aov_trend = U.safe_get(dealer, "pct_aov_trend_90d", 0)
            if aov_trend > 10:
                UI.metric_card("Avg Order Value (90d)", U.fmt_rs(aov), f"📈 Ticket size up {aov_trend:.0f}%", "healthy")
            elif aov_trend > 0:
                UI.metric_card("Avg Order Value (90d)", U.fmt_rs(aov), f"↗️ Slight growth ({aov_trend:.0f}%)", "healthy")
            elif aov_trend > -10:
                UI.metric_card("Avg Order Value (90d)", U.fmt_rs(aov), "Stable ticket size", "attention")
            else:
                UI.metric_card("Avg Order Value (90d)", U.fmt_rs(aov), f"📉 Ticket size down {abs(aov_trend):.0f}%", "attention")

    if ENABLE_COLLECTIONS:
        coll_vals = DATA.get_dealer_collections_numbers(dealer)
        if coll_vals["show"]:
            st.markdown("---")
            st.subheader("💰 Outstanding Overview")
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            overdue = coll_vals["overdue"]
            os_total = coll_vals["os_total"]
            due_today = coll_vals["due_today"]
            due_today_only = coll_vals["due_today_only"]
            due_tomorrow = coll_vals["due_tomorrow"]
            due_in7 = coll_vals["due_in7"]
            with c1:
                status = "risk" if overdue > 0 else "healthy"
                UI.metric_card("Overdue Amount", U.fmt_rs(overdue), "Action needed!" if overdue > 0 else "Clear", status)
            with c2:
                pct_overdue = f"{(overdue / os_total * 100):.0f}% overdue" if os_total > 0 else "N/A"
                UI.metric_card("Total Outstanding", U.fmt_rs(os_total), pct_overdue, "attention" if os_total > 100000 else "healthy")
            with c3:
                UI.metric_card("Due Today Only", U.fmt_rs(due_today_only), "CALL NOW" if due_today_only > 0 else "None", "risk" if due_today_only > 0 else "healthy")
            with c4:
                UI.metric_card("Due Today", U.fmt_rs(due_today), "CALL NOW" if due_today > 0 else "None", "risk" if due_today > 0 else "healthy")
            with c5:
                UI.metric_card("Due Tomorrow", U.fmt_rs(due_tomorrow), "Reminder call" if due_tomorrow > 0 else "None", "attention" if due_tomorrow > 0 else "healthy")
            with c6:
                UI.metric_card("Due in 7 Days", U.fmt_rs(due_in7), "Watch list" if due_in7 > 0 else "None", "attention" if due_in7 > 0 else "healthy")

    st.markdown("---")
    tab1, tab2 = st.tabs(["📊 Details", "ℹ️ How to Use"])
    with tab1:
        st.subheader("Additional Details")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Revenue Breakdown")
            if has_no_orders == 1:
                st.metric("Potential (based on peers)", U.fmt_rs(U.safe_get(dealer, "cluster_avg_monthly_revenue_last_90d", 0)))
                st.info("No order history yet - metrics will appear after first order")
            else:
                st.metric("Last 90 days", U.fmt_rs(U.safe_get(dealer, "total_revenue_last_90d", 0)))
                st.metric("Previous 90 days", U.fmt_rs(U.safe_get(dealer, "total_revenue_prev_90d", 0)))
                st.metric("Lifetime Revenue", U.fmt_rs(U.safe_get(dealer, "total_revenue_lifetime", 0)))
                st.metric("Avg Order Value (90d)", U.fmt_rs(U.safe_get(dealer, "avg_order_value_last_90d", 0)))
        with c2:
            st.markdown("### Territory Position")
            if has_no_orders == 0:
                rank = U.to_int(U.safe_get(dealer, "dealer_rank_in_territory_revenue", 0))
                total = U.to_int(U.safe_get(dealer, "territory_count_dealers", 0))
                st.metric("Territory Rank", f"#{rank} of {total}")
            else:
                st.info("Territory ranking not applicable - no orders yet")
            tenure = U.to_int(U.safe_get(dealer, "tenure_months", 0))
            st.metric("Tenure", f"{tenure} months")
            is_new = U.safe_get(dealer, "is_new_dealer", 0)
            dealer_type = "🆕 New Dealer (Last 30 days)" if is_new == 1 else "Existing Dealer"
            st.metric("Dealer Type", dealer_type)
        if has_no_orders == 0:
            st.markdown("### Product Mix & Gaps")
            missing_cats, low_share_cats = D.get_product_gaps(dealer)
            UI.render_product_gaps(missing_cats, low_share_cats)
    with tab2:
        st.markdown(UI.HOW_TO_USE_MD)


def render_quick_nav_sidebar() -> None:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚡ Quick Actions")

    if st.session_state.get("view") == S.AppState.VIEW_DEALER and st.session_state.get("selected_dealer"):
        S.AppState.remember_recent_dealer(st.session_state["selected_dealer"])

    rec = st.session_state.get("recent_dealers", [])
    if rec:
        st.sidebar.markdown("**Recently Viewed:**")
        for did in rec[-5:]:
            if st.sidebar.button(f"↩️ {did}", key=f"recent_{did}"):
                S.AppState.navigate_to_dealer(did)
                st.rerun()


def main() -> None:
    with st.sidebar.expander("⚙️ Settings"):
        debug_mode = st.checkbox("Debug Mode", value=st.session_state.get("debug_mode", False))
        st.session_state.debug_mode = debug_mode

    with st.sidebar:
        st.markdown("<h1 style='text-align: center;'>🎯 TSM Actions</h1>", unsafe_allow_html=True)
        st.markdown("---")

        st.subheader("📄 Load Data")
        try:
            if st.session_state.df is None:
                st.session_state.df = DATA.load_dealer_df(FILE_PATH)
            if st.session_state.df is not None and not st.session_state.df.empty and "dealer_composite_id" in st.session_state.df.columns:
                st.session_state.df_indexed = st.session_state.df.set_index("dealer_composite_id", drop=False)
            else:
                st.session_state.df_indexed = None
            st.success(f"✅ {len(st.session_state.df):,} dealers loaded")
        except FileNotFoundError:
            st.error(f"❌ File not found: {FILE_PATH}")
            uploaded = st.file_uploader("Upload CSV", type=["csv"])
            if uploaded:
                st.session_state.df = DATA.load_dealer_df(uploaded)
                st.success(f"✅ {len(st.session_state.df):,} dealers loaded")
        except Exception as e:
            st.error(f"❌ Could not load data: {e}")

        if st.session_state.df is not None:
            df = st.session_state.df

            st.markdown("---")
            st.subheader("🔍 Find Dealer")

            st.radio("View:", ["Dealer"], label_visibility="collapsed", key="search_type")

            dealer_list = sorted(df["dealer_composite_id"].dropna().unique().tolist())
            if dealer_list and st.session_state.selected_dealer is None:
                S.AppState.navigate_to_dealer(dealer_list[0])

            selected_dealer = st.selectbox(
                "Dealer ID:", dealer_list, key="dealer_select", on_change=_on_dealer_change_direct
            )
            if st.button("View Dealer Dashboard", key="btn_view_dealer"):
                S.AppState.navigate_to_dealer(selected_dealer)
                st.rerun()

        render_quick_nav_sidebar()

    # Main routing
    if st.session_state.df is None:
        st.markdown("<h1 class='main-header'>🎯 TSM Action Dashboard</h1>", unsafe_allow_html=True)
        st.info("👈 **Get Started:** Load your dealer data and select a dealer from the sidebar")
        return

    if st.session_state.view == S.AppState.VIEW_DEALER and st.session_state.selected_dealer:
        render_dealer_dashboard(st.session_state.df, st.session_state.selected_dealer)
    else:
        st.markdown("<h1 class='main-header'>🎯 TSM Action Dashboard</h1>", unsafe_allow_html=True)
        st.info("👈 **Get Started:** Select a Dealer from the sidebar")


if __name__ == "__main__":
    main()
