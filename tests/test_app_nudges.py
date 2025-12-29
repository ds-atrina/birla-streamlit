import pandas as pd
import nudge_tag as nt
from utils import app_nudges as an


# ----------------------------
# app_nudges (LLM-free) tests
# ----------------------------
def test_variant_is_stable_per_dealer_and_key():
    dealer = {"dealer_id": "D1"}
    variants = ["A", "B", "C"]

    v1 = an._pick_variant(dealer, "COLLECTIONS_OVERDUE", variants)
    v2 = an._pick_variant(dealer, "COLLECTIONS_OVERDUE", variants)

    # Same dealer + same key => stable
    assert v1 == v2

    # Different dealer can differ
    dealer2 = {"dealer_id": "D2"}
    v3 = an._pick_variant(dealer2, "COLLECTIONS_OVERDUE", variants)
    # Not guaranteed to differ always, but should still be one of the options
    assert v3 in variants


def test_overdue_nudge_generated_and_tag_kept_same():
    dealer = {"dealer_id": "D1", "overdue_amt_total": 123456}
    acts = an.generate_collections_nudges(dealer)
    assert len(acts) == 1
    assert acts[0]["key"] == "COLLECTIONS_OVERDUE"
    assert acts[0]["tag"] == "OVERDUE_HIGH_AMOUNT"


def test_combine_sorts_by_impact_but_overdue_first():
    rule_actions = [
        {"do": "Overdue", "impact": "~₹1-₹2", "tag": "OVERDUE_HIGH_AMOUNT"},  # overdue must be first
        {"do": "Rule small", "impact": "~₹10-₹20", "tag": "CHURN_RISK_INACTIVE_90D"},
    ]
    ai_actions = [
        {"do": "AI big", "impact": "~₹100-₹200", "tag": "LLM_GENERAL"},
        {"do": "AI mid", "impact": "~₹50-₹60", "tag": "LLM_TERRITORY_HERO"},
    ]

    combined = an.combine_rule_and_ai_actions(rule_actions, ai_actions, max_rule=2, max_ai=3)
    assert combined[0]["tag"] == "OVERDUE_HIGH_AMOUNT"

    # Rest should be sorted by impact desc
    rest = combined[1:]
    scores = [an._impact_score(x) for x in rest]
    assert scores == sorted(scores, reverse=True)


def test_generate_ai_nudges_dormant_override_returns_one_general():
    dealer = {
        "dealer_id": "D1",
        "total_orders_last_90d": 0,   # dormant trigger
        "days_since_last_order": 200,
        "flag_zero_activity_90d": 1,
        # candidates can be empty; should still return 1 action
        "llm_repurchase_recommendations": [],
        "llm_territory_top_products_90d": [],
    }
    acts = an.generate_ai_nudges(dealer)
    assert len(acts) == 1
    assert acts[0]["tag"] == "LLM_GENERAL"


def test_generate_ai_nudges_non_dormant_max_three():
    dealer = {
        "dealer_id": "D1",
        "total_orders_last_90d": 5,
        "days_since_last_order": 10,
        "flag_zero_activity_90d": 0,
        "pct_revenue_trend_30d": 5,
        "order_churn_risk_score": 0.2,
        "dealer_is_dropping_off": 0,
        "total_revenue_last_90d": 90000,
        "llm_repurchase_recommendations": [
            {"product": "Sealer", "category": "Chemicals", "sub_category": "Sealer", "typical_order_value": 12000, "urgency_level": "HIGH", "action": "DUE_FOR_REORDER"}
        ],
        "llm_inactive_categories_90d": [
            {"category": "Putty", "sub_category": "Wall Putty", "days_since_last_purchase": 120, "dealer_past_monthly_sales": 10000, "peer_typical_monthly_sales": 40000}
        ],
        "llm_territory_products_in_dealer_categories": [
            {"product": "Primer", "category": "Primer", "sub_category": "Interior Primer", "percent_peers_stocking": 60, "benchmark_monthly_sales": 30000}
        ],
        "llm_territory_top_products_90d": [
            {"product": "Premium Emulsion", "category": "Emulsion", "sub_category": "Interior", "benchmark_monthly_sales": 50000, "percent_peers_stocking": 70, "estimated_revenue_lift": 15000}
        ],
        "llm_dealer_top_products_90d": [
            {"product": "Top Coat", "category": "Emulsion", "sub_category": "Interior", "avg_monthly_sales": 60000}
        ],
    }
    acts = an.generate_ai_nudges(dealer)
    assert 1 <= len(acts) <= 3
    for a in acts:
        assert a["tag"] in {"LLM_REPURCHASE_DUE", "LLM_INACTIVE_CATEGORY", "LLM_CROSS_SELL", "LLM_TERRITORY_HERO", "LLM_GENERAL"}


# ----------------------------
# nudge_tag tests (mostly same)
# ----------------------------
def test_assign_rule_tag_v2_new_dealer():
    dealer = {"is_new_dealer": 1, "has_no_orders": 1}
    tag, conf = nt.assign_rule_tag_v2("", dealer)
    assert tag == "NEW_DEALER_NO_ORDERS"
    assert conf == 1.0


def test_assign_llm_tag_repurchase():
    # depending on your nudge_tag.py naming:
    # - if you have assign_llm_tag_v2 -> use that
    # - else use assign_llm_tag
    dealer = {"days_since_last_order": 40, "count_base_product_last_90d": 5}
    action = {"do": "please reorder stock of sealer", "why": ""}

    if hasattr(nt, "assign_llm_tag_v2"):
        tag, _ = nt.assign_llm_tag_v2(action, dealer)
    else:
        tag = nt.assign_llm_tag(action, dealer)

    assert tag == "LLM_REPURCHASE_DUE"


def test_update_tag_performance_updates(tmp_path):
    # isolate storage dir
    nt.STORAGE_DIR = str(tmp_path)
    tmp_path.mkdir(exist_ok=True)

    _ = nt.initialize_tag_performance()

    outcomes = pd.DataFrame(
        [
            {
                "active_nudge_tags": "LLM_GENERAL",
                "revenue_vs_prev_month_pct": 15,
                "payment_received": 0,
                "ordered": 0,
                "new_categories_added": 0,
                "aov_vs_prev_month_pct": 0,
            }
        ]
    )

    updated = nt.update_tag_performance(outcomes, "2025-12")
    row = updated[updated["tag"] == "LLM_GENERAL"].iloc[0]
    assert int(row["times_shown"]) >= 1
    assert int(row["times_succeeded"]) >= 1
    assert float(row["observed_success_rate"]) >= 0.0
