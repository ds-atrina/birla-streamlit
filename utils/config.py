# config.py
import os
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Config:
    raw_dir: str = "data/raw"
    proc_dir: str = "data/processed"
    run_tag: str = "mar26"
    new_dealer_cutoff: str = "2026-03-01"
    input_templates: dict = field(default_factory=lambda: {
        "dealer_features": "dealer_features_{RUN_TAG}.csv",
        "order_pattern": "order_pattern_{RUN_TAG}.csv",
        "billing_growth": "billing_growth_{RUN_TAG}.csv",
        "dealer_product_recommendations": "dealer_product_recs_{RUN_TAG}.csv",
        "dealer_overdue": "dealer_overdue_{RUN_TAG}.csv",
        "final_dealer_master": "final_dealer_master_{RUN_TAG}.csv"
    })
    product_recommendations: bool = False
    overdue: bool = False
    
    features: dict = field(default_factory=lambda: {
        "overdue": True,     
        "product_recs": True,    
        "sales_risk": True,      
    })

    def raw_path(self, key: str) -> str:
        fname = self.input_templates[key].format(RUN_TAG=self.run_tag)
        return os.path.join(self.raw_dir, fname)
    
    def proc_path(self, key: str) -> str:
        fname = "processed_" + self.input_templates[key].format(RUN_TAG=self.run_tag)
        return os.path.join(self.proc_dir, fname)

config = Config(run_tag="mar26", new_dealer_cutoff="2026-03-01", product_recommendations=True, overdue=False)
