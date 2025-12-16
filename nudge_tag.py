"""
Tag schema and configuration for nudge learning system.
Each tag has baseline success rates estimated from domain knowledge.
These will be refined using historical data in Phase 2.
"""

TAG_SCHEMA = {
    # ==================== RISK TAGS (Defensive) ====================
    "CHURN_RISK_INACTIVE_90D": {
        "priority_base": 100,
        "baseline_success_rate": 0.25,  # 25% of inactive dealers order naturally
        "expected_outcome": "order_placed_30d",
        "description": "Dealer inactive 90+ days, high churn risk"
    },
    
    "CHURN_RISK_HIGH_SCORE": {
        "priority_base": 95,
        "baseline_success_rate": 0.30,
        "expected_outcome": "order_placed_30d",
        "description": "Churn risk score > 1.5"
    },
    
    "SALES_DROP_SHARP": {
        "priority_base": 90,
        "baseline_success_rate": 0.35,  # Dealers dropping often recover partially
        "expected_outcome": "revenue_increase_10pct",
        "description": "Revenue down >20% vs previous period"
    },
    
    "AOV_SHRINKING": {
        "priority_base": 70,
        "baseline_success_rate": 0.40,
        "expected_outcome": "aov_increase_10pct",
        "description": "Average order value declining >10%"
    },
    
    # ==================== NEW DEALER TAGS ====================
    "NEW_DEALER_NO_ORDERS": {
        "priority_base": 85,
        "baseline_success_rate": 0.60,  # Most new dealers order within 30d
        "expected_outcome": "order_placed_30d",
        "description": "New dealer (< 30 days), no orders yet"
    },
    
    "NEW_DEALER_LOW_BILLING": {
        "priority_base": 75,
        "baseline_success_rate": 0.50,
        "expected_outcome": "revenue_increase_15pct",
        "description": "New dealer billing below cluster average"
    },
    
    "NEW_DEALER_STRONG_START": {
        "priority_base": 60,
        "baseline_success_rate": 0.55,
        "expected_outcome": "new_category_added_30d",
        "description": "New dealer performing above average"
    },
    
    # ==================== GROWTH TAGS (Offensive) ====================
    "GROWTH_MOMENTUM": {
        "priority_base": 65,
        "baseline_success_rate": 0.65,  # Growing dealers tend to keep growing
        "expected_outcome": "revenue_increase_15pct",
        "description": "Positive revenue trend, capitalize on momentum"
    },
    
    "RECOVERY_BOUNCE_BACK": {
        "priority_base": 70,
        "baseline_success_rate": 0.55,
        "expected_outcome": "revenue_increase_10pct",
        "description": "Revenue recovered >20% after drop"
    },
    
    "UNDERPERFORMER_VS_PEERS": {
        "priority_base": 65,
        "baseline_success_rate": 0.45,
        "expected_outcome": "revenue_increase_10pct",
        "description": "Billing significantly below cluster average"
    },
    
    # ==================== PRODUCT TAGS ====================
    "CROSS_SELL_CATEGORY": {
        "priority_base": 55,
        "baseline_success_rate": 0.35,
        "expected_outcome": "new_category_added_30d",
        "description": "Opportunity to introduce new product categories"
    },
    
    "PRODUCT_VARIETY_LOW": {
        "priority_base": 50,
        "baseline_success_rate": 0.40,
        "expected_outcome": "new_products_added_30d",
        "description": "Limited product range vs peers"
    },
    
    "SUBBRAND_DOMINANT_STYLE": {
        "priority_base": 55,
        "baseline_success_rate": 0.35,
        "expected_outcome": "subbrand_mix_improved",
        "description": "Over-dependent on low-margin Style sub-brand"
    },
    
    "SUBBRAND_DOMINANT_CALISTA": {
        "priority_base": 50,
        "baseline_success_rate": 0.40,
        "expected_outcome": "subbrand_mix_improved",
        "description": "Strong Calista base, upsell to One"
    },
    
    "SUBBRAND_DOMINANT_ONE": {
        "priority_base": 45,
        "baseline_success_rate": 0.50,
        "expected_outcome": "subbrand_mix_maintained",
        "description": "Protect premium One sub-brand relationship"
    },
    
    "SUBBRAND_DOMINANT_OTHER": {
        "priority_base": 50,
        "baseline_success_rate": 0.40,
        "expected_outcome": "subbrand_mix_improved",
        "description": "Over-concentrated in one sub-brand"
    },
    
    # ==================== LLM TAGS ====================
    "LLM_REPURCHASE_DUE": {
        "priority_base": 60,
        "baseline_success_rate": 0.50,
        "expected_outcome": "order_placed_30d",
        "description": "AI-identified repurchase opportunity"
    },
    
    "LLM_CROSS_SELL": {
        "priority_base": 55,
        "baseline_success_rate": 0.35,
        "expected_outcome": "new_category_added_30d",
        "description": "AI-identified cross-sell in strong categories"
    },
    
    "LLM_INACTIVE_CATEGORY": {
        "priority_base": 60,
        "baseline_success_rate": 0.30,
        "expected_outcome": "category_reactivated_30d",
        "description": "AI-identified inactive category reactivation"
    },
    
    "LLM_TERRITORY_HERO": {
        "priority_base": 50,
        "baseline_success_rate": 0.40,
        "expected_outcome": "new_products_added_30d",
        "description": "AI-identified territory hero products"
    },
    
    "LLM_GENERAL": {
        "priority_base": 45,
        "baseline_success_rate": 0.45,
        "expected_outcome": "revenue_increase_10pct",
        "description": "General AI recommendation (unclassified)"
    },
}

# Tag families for grouping
TAG_FAMILIES = {
    "RISK": [
        "CHURN_RISK_INACTIVE_90D",
        "CHURN_RISK_HIGH_SCORE",
        "SALES_DROP_SHARP",
        "AOV_SHRINKING"
    ],
    "NEW_DEALER": [
        "NEW_DEALER_NO_ORDERS",
        "NEW_DEALER_LOW_BILLING",
        "NEW_DEALER_STRONG_START"
    ],
    "GROWTH": [
        "GROWTH_MOMENTUM",
        "RECOVERY_BOUNCE_BACK",
        "UNDERPERFORMER_VS_PEERS"
    ],
    "PRODUCT": [
        "CROSS_SELL_CATEGORY",
        "PRODUCT_VARIETY_LOW",
        "SUBBRAND_DOMINANT_STYLE",
        "SUBBRAND_DOMINANT_CALISTA",
        "SUBBRAND_DOMINANT_ONE",
        "SUBBRAND_DOMINANT_OTHER"
    ],
    "LLM": [
        "LLM_REPURCHASE_DUE",
        "LLM_CROSS_SELL",
        "LLM_INACTIVE_CATEGORY",
        "LLM_TERRITORY_HERO",
        "LLM_GENERAL"
    ]
}

def get_tag_family(tag: str) -> str:
    """Get the family for a given tag"""
    for family, tags in TAG_FAMILIES.items():
        if tag in tags:
            return family
    return "UNKNOWN"

"""
Robust tag assignment using:
1. Dealer state rules (primary)
2. Text pattern matching (secondary)
3. Confidence scoring (to flag uncertain assignments)
"""

def assign_rule_tag_v2(nudge_text: str, dealer: dict) -> tuple[str, float]:
    is_new = dealer.get('is_new_dealer', 0) == 1
    has_no_orders = dealer.get('has_no_orders', 0) == 1
    dsl = dealer.get('days_since_last_order', 0)
    churn_risk = dealer.get('order_churn_risk_score', 0)
    rev_trend = dealer.get('pct_revenue_trend_90d', 0)
    aov_trend = dealer.get('pct_aov_trend_90d', 0)
    gap_to_cluster = dealer.get('revenue_gap_vs_cluster_avg_monthly_last_90d', 0)
    products_count = dealer.get('count_base_product_last_90d', 0)

    text_lower = (nudge_text or "").lower()

    # TEXT-FIRST (highest precision)
    text_map = [
        ("🚨 urgent reactivation", ("CHURN_RISK_INACTIVE_90D", 0.95)),
        ("📉 sales drop", ("SALES_DROP_SHARP", 0.95)),
        ("📉 order size shrinking", ("AOV_SHRINKING", 0.90)),
        ("📈 recovery", ("RECOVERY_BOUNCE_BACK", 0.95)),
        ("🚀 high performer", ("GROWTH_MOMENTUM", 0.90)),
        ("💰 growth opportunity", ("UNDERPERFORMER_VS_PEERS", 0.90)),
        ("🎨 mix upgrade", ("SUBBRAND_DOMINANT_STYLE", 0.95)),
        ("🎨 premium push", ("SUBBRAND_DOMINANT_CALISTA", 0.95)),
        ("💎 protect premium", ("SUBBRAND_DOMINANT_ONE", 0.95)),
        ("📦 dealer is highly dependent", ("SUBBRAND_DOMINANT_OTHER", 0.85)),
    ]
    for prefix, (tag, conf) in text_map:
        if text_lower.startswith(prefix.lower()):
            return tag, conf

    # NEW DEALER
    if is_new:
        if has_no_orders:
            return "NEW_DEALER_NO_ORDERS", 1.0
        elif gap_to_cluster > 0 and any(w in text_lower for w in ["gap", "below", "peer", "cluster"]):
            return "NEW_DEALER_LOW_BILLING", 0.9
        elif gap_to_cluster <= 0 and any(w in text_lower for w in ["strong", "above", "expand"]):
            return "NEW_DEALER_STRONG_START", 0.9
        else:
            return ("NEW_DEALER_LOW_BILLING", 0.6) if gap_to_cluster > 0 else ("NEW_DEALER_STRONG_START", 0.6)

    # CRITICAL RISK
    if dsl >= 90:
        return ("CHURN_RISK_INACTIVE_90D", 1.0) if any(w in text_lower for w in ["inactive", "reactivat", "lost", "churn"]) else ("CHURN_RISK_INACTIVE_90D", 0.8)

    if churn_risk > 1.5:
        return ("CHURN_RISK_HIGH_SCORE", 1.0) if any(w in text_lower for w in ["churn", "risk"]) else ("CHURN_RISK_HIGH_SCORE", 0.7)

    # SALES TRENDS
    if rev_trend < -20:
        return ("SALES_DROP_SHARP", 0.95) if any(w in text_lower for w in ["drop", "declin", "down"]) else ("SALES_DROP_SHARP", 0.7)

    if rev_trend > 20:
        return ("RECOVERY_BOUNCE_BACK", 0.95) if any(w in text_lower for w in ["recover", "bounce", "back"]) else ("RECOVERY_BOUNCE_BACK", 0.7)

    if 10 < rev_trend <= 20:
        return ("GROWTH_MOMENTUM", 0.9) if any(w in text_lower for w in ["momentum", "grow", "capitaliz"]) else ("GROWTH_MOMENTUM", 0.6)

    if aov_trend < -10:
        return ("AOV_SHRINKING", 0.9) if any(w in text_lower for w in ["shrink", "ticket", "order value"]) else ("AOV_SHRINKING", 0.6)

    # PEER COMPARISON
    if gap_to_cluster > 5000:
        return ("UNDERPERFORMER_VS_PEERS", 0.9) if any(w in text_lower for w in ["gap", "below", "peer", "cluster"]) else ("UNDERPERFORMER_VS_PEERS", 0.6)

    # PRODUCT MIX (shares are fractions 0–1)
    share_style = dealer.get('share_revenue_style_180d', 0) or 0
    share_calista = dealer.get('share_revenue_calista_180d', 0) or 0
    share_one = dealer.get('share_revenue_one_180d', 0) or 0

    if share_style > 0.5:
        return ("SUBBRAND_DOMINANT_STYLE", 0.95) if ("style" in text_lower and ("upgrade" in text_lower or "calista" in text_lower)) else ("SUBBRAND_DOMINANT_STYLE", 0.7)
    if share_calista > 0.5:
        return ("SUBBRAND_DOMINANT_CALISTA", 0.95) if ("calista" in text_lower and ("premium" in text_lower or "one" in text_lower)) else ("SUBBRAND_DOMINANT_CALISTA", 0.7)
    if share_one > 0.5:
        return ("SUBBRAND_DOMINANT_ONE", 0.95) if ("one" in text_lower and "protect" in text_lower) else ("SUBBRAND_DOMINANT_ONE", 0.7)

    all_subbrands = {
        'allwood': dealer.get('share_revenue_allwood_180d', 0) or 0,
        'prime': dealer.get('share_revenue_prime_180d', 0) or 0,
        'allwoodpro': dealer.get('share_revenue_allwoodpro_180d', 0) or 0,
        'alldry': dealer.get('share_revenue_alldry_180d', 0) or 0,
        'artist': dealer.get('share_revenue_artist_180d', 0) or 0,
    }
    max_share = max(all_subbrands.values()) if all_subbrands else 0
    if max_share > 0.5 and ("sub-brand" in text_lower or "subbrand" in text_lower):
        return "SUBBRAND_DOMINANT_OTHER", 0.8

    if products_count < 15:
        if "product" in text_lower and any(w in text_lower for w in ["variety", "range", "limited"]):
            return "PRODUCT_VARIETY_LOW", 0.9
        if "cross" in text_lower or "new category" in text_lower or "introduce" in text_lower:
            return "CROSS_SELL_CATEGORY", 0.8
        return "PRODUCT_VARIETY_LOW", 0.5

    if "cross" in text_lower or "new category" in text_lower or "introduce" in text_lower:
        return "CROSS_SELL_CATEGORY", 0.7

    # FALLBACK
    if dsl > 45:
        return "CHURN_RISK_INACTIVE_90D", 0.4
    elif rev_trend < -10:
        return "SALES_DROP_SHARP", 0.4
    elif gap_to_cluster > 0:
        return "UNDERPERFORMER_VS_PEERS", 0.4
    else:
        return "CROSS_SELL_CATEGORY", 0.3

# -------------------------
# Tag assignment v2 (LLM)
# -------------------------
def assign_llm_tag_v2(action: dict, dealer: dict) -> tuple[str, float]:
    text = ((action.get('do', '') + ' ' + action.get('why', '')) or "").lower()
    dsl = dealer.get('days_since_last_order', 0)
    rev_trend = dealer.get('pct_revenue_trend_90d', 0)
    products_count = dealer.get('count_base_product_last_90d', 0)

    repurchase_keywords = ['repurchase', 'reorder', 'due', 'overdue', 're-order', 'stock up']
    if any(word in text for word in repurchase_keywords):
        return ("LLM_REPURCHASE_DUE", 0.9) if dsl > 30 else ("LLM_REPURCHASE_DUE", 0.6)

    crosssell_keywords = ['cross-sell', 'new category', 'expand category', 'additional category', 'introduce']
    if any(word in text for word in crosssell_keywords):
        return ("LLM_CROSS_SELL", 0.9) if products_count < 20 else ("LLM_CROSS_SELL", 0.7)

    inactive_keywords = ['inactive', 'reactivate', 'restart', 'lapsed', 'dormant', 'resume']
    if any(word in text for word in inactive_keywords):
        return "LLM_INACTIVE_CATEGORY", 0.85

    hero_keywords = ['hero', 'territory', 'popular', 'best-selling', 'top-selling', 'fast-moving']
    if any(word in text for word in hero_keywords):
        return "LLM_TERRITORY_HERO", 0.8

    if dsl > 60:
        return "LLM_REPURCHASE_DUE", 0.5
    elif rev_trend < -10:
        return "LLM_CROSS_SELL", 0.4
    elif products_count < 15:
        return "LLM_CROSS_SELL", 0.4
    else:
        return "LLM_GENERAL", 0.3

# Backward compatible wrappers
def assign_rule_tag(nudge_text: str, dealer: dict) -> str:
    tag, _ = assign_rule_tag_v2(nudge_text, dealer)
    return tag

def assign_llm_tag(action: dict, dealer: dict) -> str:
    tag, _ = assign_llm_tag_v2(action, dealer)
    return tag

# ==================== NEW: VALIDATION & DEBUGGING ====================

def validate_tag_assignment(nudge_text: str, assigned_tag: str, dealer: dict, confidence: float) -> dict:
    """
    Validate tag assignment and provide debugging info.
    Use this to audit tag quality.
    
    Returns dict with:
    - is_valid: bool
    - issues: list of problems
    - suggestions: alternative tags to consider
    """
    issues = []
    suggestions = []
    
    # Check 1: Confidence too low
    if confidence < 0.5:
        issues.append(f"Low confidence ({confidence:.2f}) - tag may be wrong")
    
    # Check 2: Text-state mismatch
    text_lower = nudge_text.lower()
    is_new = dealer.get('is_new_dealer', 0) == 1
    dsl = dealer.get('days_since_last_order', 0)
    
    if assigned_tag == "NEW_DEALER_NO_ORDERS" and not is_new:
        issues.append("Tag is NEW_DEALER but dealer is not new")
        suggestions.append("CHURN_RISK_INACTIVE_90D" if dsl > 45 else "CROSS_SELL_CATEGORY")
    
    if assigned_tag == "CHURN_RISK_INACTIVE_90D" and dsl < 45:
        issues.append(f"Tag is CHURN_RISK but dealer only {dsl} days since order")
        suggestions.append("CROSS_SELL_CATEGORY")
    
    # Check 3: Tag doesn't match text at all
    tag_keywords = {
        "CHURN_RISK_INACTIVE_90D": ["inactive", "reactivate", "lost", "churn"],
        "SALES_DROP_SHARP": ["drop", "decline", "down", "falling"],
        "RECOVERY_BOUNCE_BACK": ["recover", "bounce", "back"],
        "CROSS_SELL_CATEGORY": ["cross", "new category", "introduce"],
        "PRODUCT_VARIETY_LOW": ["variety", "range", "limited"],
    }
    
    if assigned_tag in tag_keywords:
        expected_words = tag_keywords[assigned_tag]
        if not any(word in text_lower for word in expected_words):
            issues.append(f"Text doesn't contain expected keywords for {assigned_tag}")
    
    is_valid = len(issues) == 0 and confidence >= 0.6
    
    return {
        'is_valid': is_valid,
        'confidence': confidence,
        'issues': issues,
        'suggestions': suggestions
    }


def get_tag_with_validation(nudge_text: str, dealer: dict, is_llm: bool = False) -> dict:
    """
    Get tag assignment with full validation report.
    Use this during development to audit quality.
    """
    if is_llm:
        tag, confidence = assign_llm_tag_v2({'do': nudge_text, 'why': ''}, dealer)
    else:
        tag, confidence = assign_rule_tag_v2(nudge_text, dealer)
    
    validation = validate_tag_assignment(nudge_text, tag, dealer, confidence)
    
    return {
        'tag': tag,
        'confidence': confidence,
        'tag_family': get_tag_family(tag),
        'validation': validation
    }


def validate_tag(tag: str) -> bool:
    """Check if tag exists in schema"""
    return tag in TAG_SCHEMA

"""
CSV-based storage for nudges, outcomes, and tag performance.
Uses pandas for simplicity (no database needed for MVP).
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional
import uuid

# Storage directory
STORAGE_DIR = "data/nudges"
os.makedirs(STORAGE_DIR, exist_ok=True)

# ==================== NUDGE GENERATION ====================

NUDGE_COLUMNS = [
    "text","tag","tag_family","priority_base","strength_score","context_boost","final_score",
    "nudge_id","dealer_id","final_rank","generation_date",
    "do","why","impact",
    "llm_primary_tag","llm_tag_confidence","llm_tag_basis",
]

def save_nudges(nudges, month: str) -> str:
    df = pd.DataFrame(nudges)

    # Ensure all columns exist
    for c in NUDGE_COLUMNS:
        if c not in df.columns:
            df[c] = ""

    # Clean NaNs consistently
    df = df[NUDGE_COLUMNS].fillna("")

    filepath = os.path.join(STORAGE_DIR, f"nudges_generated_{month}.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Saved {len(df)} nudges to {filepath}")
    return filepath


def load_nudges(month: str) -> Optional[pd.DataFrame]:
    """Load nudges for a specific month"""
    filepath = os.path.join(STORAGE_DIR, f"nudges_generated_{month}.csv")
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    return None


# ==================== OUTCOME TRACKING ====================

def save_outcomes(outcomes: List[Dict], month: str) -> str:
    """
    Save dealer outcomes for a month.
    
    Args:
        outcomes: List of outcome dictionaries
        month: YYYY-MM format
        
    Returns:
        Filepath of saved CSV
    """
    df = pd.DataFrame(outcomes)
    filepath = os.path.join(STORAGE_DIR, f"dealer_outcomes_{month}.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Saved {len(outcomes)} outcomes to {filepath}")
    return filepath


def load_outcomes(month: str) -> Optional[pd.DataFrame]:
    """Load outcomes for a specific month"""
    filepath = os.path.join(STORAGE_DIR, f"dealer_outcomes_{month}.csv")
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    return None


# ==================== TAG PERFORMANCE ====================

def initialize_tag_performance() -> pd.DataFrame:
    """
    Create initial tag performance dataframe with baseline values.
    """
    tags = []
    for tag, config in TAG_SCHEMA.items():
        tags.append({
            'tag': tag,
            'tag_family': get_tag_family(tag),
            'baseline_success_rate': config['baseline_success_rate'],
            'observed_success_rate': config['baseline_success_rate'],  # Start at baseline
            'lift_over_baseline': 0.0,
            'times_shown': 0,
            'times_succeeded': 0,
            'confidence': 0.0,
            'strength_score': 0.0,
            'last_updated': datetime.now().strftime('%Y-%m-%d')
        })
    
    df = pd.DataFrame(tags)
    filepath = os.path.join(STORAGE_DIR, "tag_performance.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Initialized tag performance with {len(tags)} tags")
    return df


def load_tag_performance() -> pd.DataFrame:
    """Load tag performance (creates if doesn't exist)"""
    filepath = os.path.join(STORAGE_DIR, "tag_performance.csv")
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    else:
        return initialize_tag_performance()


def save_tag_performance(df: pd.DataFrame) -> str:
    """Save updated tag performance"""
    # filepath = os.path.join(STORAGE_DIR, "tag_performance.csv")
    # df.to_csv(filepath, index=False)
    print(f"✅ Updated tag performance")
    # return filepath


# ==================== LEARNING UPDATE ====================

def update_tag_performance(outcomes_df: pd.DataFrame, month: str) -> pd.DataFrame:
    """
    Update tag performance based on month's outcomes.
    
    Args:
        outcomes_df: DataFrame with dealer outcomes
        month: Which month we're updating for
        
    Returns:
        Updated tag performance DataFrame
    """
    tag_perf = load_tag_performance()
    
    for idx, row in tag_perf.iterrows():
        tag = row['tag']
        
        # Find dealers who saw this tag this month
        dealers_with_tag = outcomes_df[
            outcomes_df['active_nudge_tags'].str.contains(tag, na=False)
        ]
        
        if len(dealers_with_tag) == 0:
            continue  # Tag not shown this month
        
        # Get expected outcome from schema
        expected_outcome = TAG_SCHEMA[tag]['expected_outcome']
        
        # Calculate success based on outcome type
        if expected_outcome == 'order_placed_30d':
            success_count = dealers_with_tag['ordered'].sum()
        elif expected_outcome == 'revenue_increase_15pct':
            success_count = (dealers_with_tag['revenue_vs_prev_month_pct'] >= 15).sum()
        elif expected_outcome == 'revenue_increase_10pct':
            success_count = (dealers_with_tag['revenue_vs_prev_month_pct'] >= 10).sum()
        elif expected_outcome == 'new_category_added_30d':
            success_count = (dealers_with_tag['new_categories_added'] > 0).sum()
        elif expected_outcome == 'aov_increase_10pct':
            success_count = (dealers_with_tag['aov_vs_prev_month_pct'] >= 10).sum()
        else:
            # Default: did they order?
            success_count = dealers_with_tag['ordered'].sum()
        
        # Calculate metrics
        n = len(dealers_with_tag)
        observed_rate = success_count / n if n > 0 else 0.0
        baseline_rate = row['baseline_success_rate']
        
        # Lift calculation
        if baseline_rate > 0:
            lift = (observed_rate - baseline_rate) / baseline_rate
        else:
            lift = 0.0
        
        # Confidence based on sample size (full confidence at 30+ samples)
        confidence = min(1.0, n / 30.0)
        
        # Strength score: tanh(lift) * confidence, bounded to [-1, 1]
        strength = np.tanh(lift) * confidence
        
        # Update cumulative counts
        old_shown = row['times_shown']
        old_succeeded = row['times_succeeded']
        new_total_shown = old_shown + n
        new_total_succeeded = old_succeeded + success_count
        
        # Update row
        tag_perf.at[idx, 'observed_success_rate'] = observed_rate
        tag_perf.at[idx, 'lift_over_baseline'] = lift
        tag_perf.at[idx, 'times_shown'] = new_total_shown
        tag_perf.at[idx, 'times_succeeded'] = new_total_succeeded
        tag_perf.at[idx, 'confidence'] = confidence
        tag_perf.at[idx, 'strength_score'] = strength
        tag_perf.at[idx, 'last_updated'] = datetime.now().strftime('%Y-%m-%d')
    
    # Save updated performance
    save_tag_performance(tag_perf)
    
    return tag_perf


# ==================== UTILITY ====================

def get_strength_for_tag(tag: str) -> float:
    """Get current strength score for a tag"""
    tag_perf = load_tag_performance()
    row = tag_perf[tag_perf['tag'] == tag]
    if len(row) > 0:
        return row.iloc[0]['strength_score']
    return 0.0