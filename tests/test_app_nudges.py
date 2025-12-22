import json
from utils import app_nudges as an


def test_extract_json_object_simple():
    text = """
Here is the answer:
```json
{"actions": [{"do":"Call today","why":"reason","impact":"~₹1-₹2","primary_tag":"LLM_GENERAL","tag_confidence":0.7,"tag_basis":"rc=1"}]}
```
"""
    out = an._extract_json_object(text)
    assert out is not None
    parsed = json.loads(out)
    assert 'actions' in parsed


def test_extract_json_object_no_json():
    text = "No json here, just text"
    assert an._extract_json_object(text) is None


def test_safe_llm_impact_uses_typical_invoice():
    dealer = {
        'total_revenue_last_90d': 90000,
        'total_orders_last_90d': 3,
    }
    action = {}
    s = an._safe_llm_impact(dealer, action)
    assert isinstance(s, str)
    assert '~₹' in s
