# utils/app_ui.py 

from __future__ import annotations

import html
from typing import Callable, Dict, Iterable, Optional

import pandas as pd
import streamlit as st


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def inject_css() -> None:
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

  .status-healthy, .status-attention, .status-risk {
      padding: 1.5rem 2rem;
      border-radius: 16px;
      color: white;
      margin-bottom: 1.5rem;
      font-size: 1.2rem;
      font-weight: 700;
      border: 2px solid rgba(255,255,255,0.2);
  }
  .status-healthy { background: linear-gradient(135deg, #48bb78 0%, #38a169 100%); box-shadow: 0 8px 24px rgba(72,187,120,0.25); }
  .status-attention { background: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%); box-shadow: 0 8px 24px rgba(237,137,54,0.25); }
  .status-risk { background: linear-gradient(135deg, #f56565 0%, #c53030 100%); box-shadow: 0 8px 24px rgba(245,101,101,0.25); }

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
  .metric-value { font-size: 2rem; font-weight: 800; margin: 0.5rem 0; }
  .metric-plain { font-size: 1.1rem; color: #4a5568; margin-top: 0.5rem; font-weight: 500; }

  .nba-card {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 2rem;
      border-radius: 16px;
      color: white;
      margin: 1.5rem 0;
      box-shadow: 0 10px 30px rgba(102,126,234,0.3);
  }
  .nba-title { font-size: 1.5rem; font-weight: 800; margin-bottom: 1rem; }
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
      transition: box-shadow 0.2s ease;
  }
  .action-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); }

  .action-title { font-size: 1.1rem; font-weight: 700; color: #2d3748; margin-bottom: 0.5rem; }
  .action-why { font-size: 0.95rem; color: #4a5568; margin: 0.5rem 0; line-height: 1.6; }

  .dealer-header {
      background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
      padding: 2rem;
      border-radius: 16px;
      color: white;
      margin-bottom: 1rem;
      box-shadow: 0 8px 20px rgba(0,0,0,0.15);
      position: relative;
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
  .segment-stamp span { display:block; line-height:1.2; }

  .dealer-title { font-size: 1.8rem; font-weight: 800; margin-bottom: 0.5rem; }
  .dealer-subtitle { font-size: 1rem; opacity: 0.9; }

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

  /* Compact segmented control */
  div[data-testid="stSegmentedControl"] label p { margin-bottom: 0.25rem !important; }
</style>
""", unsafe_allow_html=True)


def metric_card(label: str, value: str, plain_text: str, status: str = "healthy") -> None:
    st.markdown(f"""
    <div class='metric-card {esc(status)}'>
        <div class='metric-label'>{esc(label)}</div>
        <div class='metric-value'>{esc(value)}</div>
        <div class='metric-plain'>{esc(plain_text)}</div>
    </div>
    """, unsafe_allow_html=True)


def render_reason_chips(reasons: Iterable[str], color_map: Dict[str, str]) -> None:
    chips_html = ""
    for r in reasons:
        c = color_map.get(r, "#64748b")
        chips_html += (
            f"<span style='background:{c};color:white;padding:0.2rem 0.5rem;"
            f"border-radius:4px;font-size:0.7rem;margin-right:0.35rem;display:inline-block;'>"
            f"{esc(r)}</span>"
        )
    st.markdown(f"<div style='margin-top:0.25rem;'>{chips_html}</div>", unsafe_allow_html=True)


def render_dealer_header(customer_name: str, dealer_id: str, city: str, state: str, territory: str, asm: str, stamp_label: str | None = None) -> None:
    if stamp_label:
        st.markdown(
            f"""
            <div class='dealer-header'>
                <div class='segment-stamp'><span>{esc(stamp_label)}</span></div>
                <div class='dealer-title'>🏪 {esc(customer_name)} ({esc(dealer_id)})</div>
                <div class='dealer-subtitle'>
                    📍 {esc(city)}, {esc(state)} • Territory: {esc(territory)} • ASM: {esc(asm)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class='dealer-header'>
                <div class='dealer-title'>🏪 {esc(customer_name)} ({esc(dealer_id)})</div>
                <div class='dealer-subtitle'>
                    📍 {esc(city)}, {esc(state)} • Territory: {esc(territory)} • ASM: {esc(asm)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

def render_badges(badges: list[tuple[str, str]]) -> None:
    badge_html = "<div class='badge-row'>"
    for text, cls in badges:
        badge_html += f"<span class='badge {esc(cls)}'>{esc(text)}</span>"
    badge_html += "</div>"
    st.markdown(badge_html, unsafe_allow_html=True)


def render_status_banner(level: str, title: str, msg: str) -> None:
    st.markdown(
        f"<div class='status-{esc(level)}'>{esc(title)}<br><small>{esc(msg)}</small></div>",
        unsafe_allow_html=True,
    )
    
def render_nba(rule_nudges: list[dict]) -> None:
    nba_html = "<div class='nba-card'><div class='nba-title'>🎯 WHAT TO DO TODAY</div>"
    for i, nudge in enumerate(rule_nudges or [], 1):
        tag_badge = (
            f"<span style='background: rgba(255,255,255,0.3); padding: 0.25rem 0.5rem; "
            f"border-radius: 4px; font-size: 0.75rem; margin-left: 0.5rem;'>{esc(nudge.get('tag',''))}</span>"
        )
        nba_html += f"<div class='nba-action'><strong>{i}.</strong> {esc(nudge.get('text',''))} {tag_badge}</div>"
    nba_html += "</div>"
    st.markdown(nba_html, unsafe_allow_html=True)
    
def render_action_cards(
    action_df: pd.DataFrame,
    score_col: str,
    color_map: Dict[str, str],
    fmt_rs_fn: Callable[[float], str],
    on_open: Callable[[str], None],
) -> None:
    for i, (_, row) in enumerate(action_df.iterrows()):
        dealer_id = str(row.get("dealer_composite_id", ""))
        chips = [c.strip() for c in str(row.get("reason_chips", "")).split(",") if c.strip()]
        chips_html = "".join([
            f"<span style='background:{color_map.get(chip, '#64748b')};color:white;"
            f"padding:0.2rem 0.5rem;border-radius:4px;font-size:0.7rem;margin-right:0.3rem;'>"
            f"{esc(chip)}</span>"
            for chip in chips
        ])

        dsl = int(row.get("days_since_last_order", 0) or 0)
        churn = float(row.get("order_churn_risk_score", 0) or 0)
        score = float(row.get(score_col, 0) or 0)

        html_card = f"""
        <div class='action-card' style='margin: 0.5rem 0;'>
            <div class='action-title'>
                {esc(row.get('customer_name',''))} ({esc(dealer_id)})
                <span style='float:right;background:#667eea;color:white;padding:0.25rem 0.6rem;
                             border-radius:4px;font-size:0.75rem;'>Score: {score:.0f}</span>
            </div>
            <div style='margin:0.5rem 0;'>{chips_html}</div>
            <div class='action-why'><strong>Action:</strong> {esc(row.get('action_hint', 'Action needed'))}</div>
            <div style='font-size:0.85rem;color:#4a5568;margin-top:0.5rem;'>
                Days since order: {dsl} | Overdue: {esc(fmt_rs_fn(row.get('overdue_amt_total', 0)))} |
                Due Today: {esc(fmt_rs_fn(row.get('due_today_total', 0)))} | Churn Risk: {churn:.1f}
            </div>
        </div>
        """

        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(html_card, unsafe_allow_html=True)
        with col2:
            if st.button("Open", key=f"open_action_{dealer_id}_{i}"):
                on_open(dealer_id)
                st.rerun()

def render_product_gaps(missing_cats, low_share_cats) -> None:
    pg_html = "<div class='product-gaps-box'>"
    if not missing_cats and not low_share_cats:
        pg_html += "✅ This dealer is well diversified across key categories."
    else:
        if missing_cats:
            pg_html += "<strong>Not buying yet:</strong> " + ", ".join([esc(x) for x in missing_cats]) + "<br>"
        if low_share_cats:
            low_strs = [f"{esc(label)} (~{share*100:.0f}% of sales)" for label, share in low_share_cats]
            pg_html += "<strong>Low share categories:</strong> " + ", ".join(low_strs)
        pg_html += "<br><br>💡 Use these as primary cross-sell focus areas in your next visit."
    pg_html += "</div>"
    st.markdown(pg_html, unsafe_allow_html=True)

HOW_TO_USE_MD = """
## How to Use This Dashboard

### 🎯 Start Here: Select a territory or a dealer you want to view

### 🚦 Status Colors (Only 3)
- **🟢 Green (Healthy)**: maintain relationship  
- **🟡 Yellow (Needs Attention)**: plan visit / follow-up within 1-2 weeks  
- **🔴 Red (At Risk)**: urgent — call or visit immediately  

### 🧭 Navigation
- Pick a **Territory** or **Dealer** from the sidebar  
- The dashboard will open the selected page automatically  
- If you switch dealers, the page should refresh to the new dealer instantly

### ⚡ Rule Actions vs 🤖 AI Actions

**Rule Actions (Instant)**
- Always shown immediately (no button click)
- Prioritizes critical situations:
  - **Overdue**
  - **Churn risk / declining**
  - **Due today / tomorrow / in 7**
  - **Gap vs peers / inactive**

**AI Actions (Optional)**
- Click **Generate AI Actions** when you want extra talking points
- AI actions are generated **per dealer**
- Use AI actions as **supporting guidance**, not as a replacement for collections/risk priorities

### 📊 The 8 Core Metrics (What to look at)

**1) Monthly Sales (Avg)**  
- Shows whether billing is growing, flat, or declining  

**2) Orders (Last 90 Days)**  
- Highlights order frequency and engagement  

**3) Days Since Last Order**  
- Indicates inactivity and urgency vs expected cycle  

**4) Product Variety**  
- Lower variety often means smaller baskets and weak attachment  

**5) Churn Risk**  
- Higher score = more risk of stopping orders  

**6) Priority Score**  
- Higher = visit sooner  

**7) Revenue Opportunity / Gap vs Peers**  
- How much more dealer could buy compared to similar dealers  

**8) Avg Order Value (AOV)**  
- Ticket size signal — helps choose upsell vs activation  

### 📱 Field Visit Checklist (Fast)

**If dealer has Overdue**
1. Collect payment / confirm mode
2. Resolve dispute if any
3. Lock a commitment date & amount

**If dealer is inactive / churn risk**
1. Ask: “What changed in the last 30-60 days?”
2. Diagnose: competitor switch vs stock vs demand
3. Close: restart invoice date + starter basket

**If dealer is declining / gap vs peers**
1. Compare against peer basket
2. Push 2 missing fast movers
3. Close 1 incremental invoice this week

### ✅ Success Tips
- Collections and overdue always come first
- Use the dashboard daily to prioritize top *n* dealers
- Generate AI actions only when you need additional product talking points
- Keep actions simple: call today, visit this week, close one invoice
"""

WELCOME_MD = """
## Welcome to the TSM Action Dashboard

This tool gives you **clear, simple actions** for each dealer — so you can decide **who to visit today** and **what to do when you reach there**.

### What Makes This Different?

✅ **Action-first**: the action cards are the first thing you must read  
✅ **Collections-first logic**: if a dealer has **Overdue**, that becomes priority #1  
✅ **No noise**: only **8 core metrics**, not 50+ confusing numbers  
✅ **3 status colors**: 🟢 Healthy, 🟡 Needs Attention, 🔴 At Risk  
✅ **Explainable**: each action includes **why** + **expected impact**  
✅ **Fast**: rule actions load instantly; AI is generated only when needed  

### How Navigation Works (Important)

- Use the **sidebar** to select a **Territory** or **Dealer**  
- Dashboard page for selected territory or dealer appears

### Rule Actions vs AI Actions

**Rule Actions (Instant)**
- Always available immediately
- Covers: **Overdue/Due**, **inactivity**, **decline**, **gap vs peers**, **churn risk**
- Safe + consistent for daily execution

**AI Actions (Optional)**
- Generated only when you click **“Generate AI Actions”** for the dealer
- Used for **contextual talking points / product basket guidance**

### Quick Start

1. Select a **Territory** (to see who to call today)  
2. Click any **Dealer** (to see their action plan)  
3. Read action cards
4. Execute the actions (collections first if applicable)  
5. (Optional) Click **Generate AI Actions** for extra talking points / product basket  
"""