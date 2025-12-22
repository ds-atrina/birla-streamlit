# app.py
import os
import logging
import pandas as pd
import streamlit as st

# MUST be the first Streamlit call
st.set_page_config(page_title="TSM Action Dashboard", page_icon="🎯", layout="wide")

from utils import app_utils as U
from utils import app_charts as C
from utils import app_nudges as N
from utils import app_territory as T
from utils import app_dealer as D
from utils import app_state as S
from utils import app_data as DATA
from utils import app_ui as UI

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# Config
# -----------------------------
FILE_PATH = "clustered_dealer_master_improved_with_prodrecs.csv"

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

def _get_ai_actions_cache(max_items: int = 120):
    if "ai_actions_by_dealer" not in st.session_state:
        st.session_state.ai_actions_by_dealer = {}

    cache = st.session_state.ai_actions_by_dealer

    # Soft cap: keep only the most recent ~max_items keys
    if len(cache) > max_items:
        # dict preserves insertion order in Py3.7+
        for k in list(cache.keys())[: len(cache) - max_items]:
            cache.pop(k, None)

    return cache

# -----------------------------
# Init
# -----------------------------
S.AppState.init()
UI.inject_css()

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

def render_ai_status_sidebar():
    st.sidebar.markdown("---")
    st.sidebar.subheader("🤖 AI Status")

    # Key presence (don’t print key)
    has_key = bool(os.getenv("GOOGLE_API_KEY"))
    st.sidebar.write("GOOGLE_API_KEY:", "✅ Found" if has_key else "❌ Missing")

    # LangChain Gemini import availability (exposed via utils/app_nudges.py)
    has_llm = getattr(N, "ChatGoogleGenerativeAI", None) is not None
    st.sidebar.write("Gemini client:", "✅ Available" if has_llm else "❌ Not installed/import failed")

    if not has_key:
        st.sidebar.info("Set GOOGLE_API_KEY in your environment before AI nudges will work.")


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
        st.plotly_chart(fig, width="stretch")

    with c2:
        fig = C.create_order_frequency_benchmark(dealer)
        st.plotly_chart(fig, width="stretch")

    with c3:
        fig = C.create_subbrand_mix_chart(dealer)
        if fig:
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No sub-brand data available for this dealer.")

def render_territory_dashboard(df: pd.DataFrame, territory_name: str, show_debug: bool = False) -> None:
    territory_df = DATA.get_territory_df(df, territory_name)
    if territory_df.empty:
        st.error(f"No data found for territory: {territory_name}")
        return

    if show_debug:
        # with st.expander("🔧 Debug Info"):
        #     st.write(f"Territory dealers: {len(territory_df)}")
        #     st.write(f"Columns available: {list(territory_df.columns)}")
        pass

    asm = territory_df["asm_name"].iloc[0] if "asm_name" in territory_df.columns else "N/A"

    # Territory header should match dealer header styling (same CSS class)
    st.markdown(
        f"""
        <div class='dealer-header'>
            <div class='dealer-title'>🗺️ Territory Dashboard: {UI.esc(territory_name)}</div>
            <div class='dealer-subtitle'>{len(territory_df)} dealers • ASM: {UI.esc(asm)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # A) Health
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

    st.markdown("---")

    # B) Collections
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

    # C) Action list
    action_df = T.generate_combined_call_list(territory_df, top_n=200)

    st.subheader("🎯 Today's Action List")
    st.markdown("*Priority ranked list - select what to include + optional reason filters.*")

    rowA = st.columns([1, 1], vertical_alignment="center")
    with rowA[0]:
        st.caption("Include in ranking")
        include_sel = st.segmented_control(
            "Include",
            options=["Collections", "Sales risk", "Opportunities"],
            default=["Collections", "Sales risk", "Opportunities"],
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

    st.info(
        f"📊 Overdue Concentration: Top 10 dealers = **{collections['overdue_concentration_pct']:.0f}%** "
        "of total overdue - focus collection here."
    )

def render_dealer_dashboard(df: pd.DataFrame, dealer_id: str) -> None:
    dfi = st.session_state.get("df_indexed")
    if dfi is None or dealer_id not in dfi.index:
        st.error("Dealer not found.")
        return

    dealer = dfi.loc[dealer_id].to_dict()
    # ---- HEADER (FIX: must render as HTML) ----
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

    # Badges
    badges = D.get_dealer_badges(dealer)
    if badges:
        UI.render_badges(badges)

    # Status
    status_level, status_text, status_msg = D.get_dealer_status(dealer)
    UI.render_status_banner(status_level, status_text, status_msg)

    # 8 Core metrics (keep your existing logic, just using UI.metric_card)
    st.subheader("📊 Key Metrics (Last 90 days)")

    has_no_orders = U.safe_get(dealer, "has_no_orders", 0)
    last_90d_rev = U.safe_get(dealer, "total_revenue_last_90d", 0)
    prev_90d_rev = U.safe_get(dealer, "total_revenue_prev_90d", 0)

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

    # ---- FIX: Collections section should show if ANY collections numbers exist (not only overdue/due_today) ----
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

    # Charts (ONE ROW)
    render_dealer_charts_section(dealer)

    # ---- RESTORE: Tabs + AI nudges block (was in your older version) ----
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["💡 Smart Actions", "📊 Details", "ℹ️ How to Use"])

    with tab1:
        st.subheader("🎯 Dealer Action Plan (Rule + AI)")

        # 1) Always compute rule nudges immediately (2 items)
        rule_nudges = N.generate_rule_nudges(dealer)  # already returns normalized-ish dicts
        dealer_key = U.safe_get(dealer, "dealer_composite_id", None) or dealer_id

        # 2) Pull cached AI nudges (if already generated for this dealer)
        ai_cache = _get_ai_actions_cache()
        ai_nudges = ai_cache.get(dealer_key, [])

        # 3) Button generates AI nudges on-demand (3 items)
        cbtn1, cbtn2 = st.columns([1, 3], vertical_alignment="center")
        with cbtn1:
            if st.button("🤖 Generate AI Nudges", key=f"btn_ai_actions_{dealer_key}"):
                with st.spinner("Analyzing dealer patterns..."):
                    ai_cache[dealer_key] = N.generate_ai_nudges(dealer)  # returns list[dict]
                st.rerun()

        with cbtn2:
            # st.caption("AI nudges generated for this dealer (cached for this session).")
            pass

        # 4) Combine into ONE output format: first 2 rule + next 3 AI
        combined_actions = N.combine_rule_and_ai_actions(rule_nudges, ai_nudges, max_rule=2, max_ai=3)

        if not combined_actions:
            st.info("No actions available for this dealer.")
        else:
            for i, action in enumerate(combined_actions, 1):
                # color by source
                tag_color = "#48bb78" if action.get("source") == "RULE" else "#667eea"
                source_badge = action.get("source", "")

                st.markdown(
                    f"""
                    <div class='action-card' style='border-left-color: {tag_color};'>
                        <div class='action-title'>
                            Action {i}: {UI.esc(action.get('do',''))}
                            <span style='background: {tag_color}; color: white; padding: 0.25rem 0.5rem;
                                        border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem;'>
                                {UI.esc(source_badge)}
                            </span>
                            <span style='background: #111827; color: white; padding: 0.25rem 0.5rem;
                                        border-radius: 4px; font-size: 0.7rem; margin-left: 0.5rem;'>
                                {UI.esc(action.get('tag',''))}
                            </span>
                        </div>
                        <div class='action-why'><strong>Why:</strong> {UI.esc(action.get('why',''))}</div>
                        <div class='action-impact'>💰 Impact: {UI.esc(action.get('impact',''))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            
    with tab2:
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

    with tab3:
        st.markdown(UI.HOW_TO_USE_MD)

def render_quick_nav_sidebar() -> None:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚡ Quick Actions")

    # Add current dealer to recent list
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
            st.subheader("🔍 Find Dealer/Territory")

            search_type = st.radio("View:", ["Territory", "Dealer"], label_visibility="collapsed", key="search_type")

            territory_list = sorted(df["territory_name"].dropna().unique().tolist())
            if territory_list and st.session_state.selected_territory is None:
                S.AppState.navigate_to_territory(territory_list[0])

            if search_type == "Territory":
                selected_territory = st.selectbox(
                    "Territory:", territory_list, key="territory_select", on_change=_on_territory_change
                )
                if st.button("View Territory Dashboard", key="btn_view_territory"):
                    S.AppState.navigate_to_territory(selected_territory)
                    st.rerun()

                st.markdown("---")
                st.markdown("**Or select dealer in this territory:**")
                dealers_in_territory = (
                    df[df["territory_name"] == selected_territory]["dealer_composite_id"].dropna().unique().tolist()
                )
                dealers_in_territory = sorted(dealers_in_territory)
                selected_dealer = st.selectbox(
                    "Select Dealer:", dealers_in_territory, key="dealer_in_territory_select",
                    on_change=_on_dealer_change_from_territory
                )
                if st.button("View Dealer Dashboard", key="btn_view_dealer_from_territory"):
                    S.AppState.navigate_to_dealer(selected_dealer)
                    st.rerun()

            else:
                dealer_list = sorted(df["dealer_composite_id"].dropna().unique().tolist())
                selected_dealer = st.selectbox(
                    "Dealer ID:", dealer_list, key="dealer_select", on_change=_on_dealer_change_direct
                )
                if st.button("View Dealer Dashboard", key="btn_view_dealer"):
                    S.AppState.navigate_to_dealer(selected_dealer)
                    st.rerun()
        # render_ai_status_sidebar()
        render_quick_nav_sidebar()

    # Main routing
    if st.session_state.df is None:
        st.markdown("<h1 class='main-header'>🎯 TSM Action Dashboard</h1>", unsafe_allow_html=True)
        st.info("👈 **Get Started:** Load your dealer data and select a dealer/territory from the sidebar")
        return

    if st.session_state.view == S.AppState.VIEW_TERRITORY and st.session_state.selected_territory:
        render_territory_dashboard(st.session_state.df, st.session_state.selected_territory, show_debug=st.session_state.get("debug_mode", False))
    elif st.session_state.view == S.AppState.VIEW_DEALER and st.session_state.selected_dealer:
        render_dealer_dashboard(st.session_state.df, st.session_state.selected_dealer)
    else:
        st.markdown("<h1 class='main-header'>🎯 TSM Action Dashboard</h1>", unsafe_allow_html=True)
        st.info("👈 **Get Started:** Select a Territory or Dealer from the sidebar")


if __name__ == "__main__":
    main()
