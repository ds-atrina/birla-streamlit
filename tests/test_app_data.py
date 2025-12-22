import pandas as pd
from utils import app_data


def test_coerce_dealer_df_casts_and_aliases():
    df = pd.DataFrame({
        'dealer_composite_id': [123, 456],
        'total_revenue_last_90d': ['100000', '200000'],
        'avg_order_value_last_90d': ['5000', '8000'],
    })

    out = app_data.coerce_dealer_df(df.copy())

    # dealer_composite_id becomes string
    assert out['dealer_composite_id'].dtype == object
    assert out['dealer_composite_id'].iloc[0] == '123'

    # numeric columns become numeric
    assert out['total_revenue_last_90d'].dtype.kind in 'fi'
    assert out['total_revenue_last_90d'].iloc[0] == 100000

    # aliases for typical invoice exist
    for alias in ['avg_order_value_last_90d', 'avg_invoice_value_90d', 'typical_invoice_size']:
        assert alias in out.columns
        assert out[alias].dtype.kind in 'fi'
