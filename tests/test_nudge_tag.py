import pandas as pd
import nudge_tag as nt


def test_assign_rule_tag_v2_new_dealer():
    dealer = {'is_new_dealer': 1, 'has_no_orders': 1}
    tag, conf = nt.assign_rule_tag_v2('', dealer)
    assert tag == 'NEW_DEALER_NO_ORDERS'
    assert conf == 1.0


def test_assign_llm_tag_v2_repurchase():
    dealer = {'days_since_last_order': 40, 'count_base_product_last_90d': 5}
    action = {'do': 'please reorder stock of sealer', 'why': ''}
    tag, conf = nt.assign_llm_tag_v2(action, dealer)
    assert tag == 'LLM_REPURCHASE_DUE'


def test_update_tag_performance_updates(tmp_path):
    # isolate storage dir
    nt.STORAGE_DIR = str(tmp_path)
    tmp = tmp_path
    tmp.mkdir(exist_ok=True)

    # initialize performance file
    _ = nt.initialize_tag_performance()

    # Create a simple outcomes dataframe with one dealer having LLM_GENERAL and revenue increase
    outcomes = pd.DataFrame([
        {
            'active_nudge_tags': 'LLM_GENERAL',
            'revenue_vs_prev_month_pct': 15,
            'payment_received': 0,
            'ordered': 0,
            'new_categories_added': 0,
            'aov_vs_prev_month_pct': 0,
        }
    ])

    updated = nt.update_tag_performance(outcomes, '2025-12')
    row = updated[updated['tag'] == 'LLM_GENERAL'].iloc[0]
    assert int(row['times_shown']) >= 1
    assert int(row['times_succeeded']) >= 1
    assert float(row['observed_success_rate']) >= 0.0
