import json
import os

class ClaimAnalysisEngine:
    def __init__(self, materials_db_path="config/materials_pricing.json"):
        self.materials_db_path = materials_db_path
        # Fallback industry-standard baseline unit pricing matrix (simulating Xactimate profiles)
        self.default_pricing = {
            "ROOFING_SHINGLES_SQ": 425.00,  # Price per square (100 sq ft) including labor
            "ROOF_UNDERLAYMENT_ROLL": 85.00,
            "TARPING_SERVICE_HR": 95.00,
            "SIDING_VINYL_SQ": 550.00,
            "DRYWALL_REPAIR_SQFT": 12.50
        }
        self.load_pricing_database()

    def load_pricing_database(self):
        if os.path.exists(self.materials_db_path):
            try:
                with open(self.materials_db_path, "r") as f:
                    self.default_pricing.update(json.load(f))
            except Exception:
                pass

    def calculate_scope_value(self, field_meta: dict) -> dict:
        """Generates line-item valuations based on physical storm damage dimensions."""
        line_items = []
        total_gross_estimate = 0.0

        # Process Roofing Squares
        roof_squares = field_meta.get("roof_squares", 0.0)
        if roof_squares > 0:
            cost = roof_squares * self.default_pricing["ROOFING_SHINGLES_SQ"]
            underlayment_needed = max(1, int(roof_squares // 3))
            underlayment_cost = underlayment_needed * self.default_pricing["ROOF_UNDERLAYMENT_ROLL"]
            
            line_items.append({"item": "Architectural Shingles Replacement", "quantity": roof_squares, "unit": "SQ", "cost": cost})
            line_items.append({"item": "Synthetic Underlayment Barrier", "quantity": underlayment_needed, "unit": "ROLL", "cost": underlayment_cost})
            total_gross_estimate += (cost + underlayment_cost)

        # Process Emergency Tarping
        if field_meta.get("tarping_required", False):
            tarp_cost = 4 * self.default_pricing["TARPING_SERVICE_HR"]  # Standard emergency dispatch baseline
            line_items.append({"item": "Emergency Mitigation Tarping (Labor Block)", "quantity": 4, "unit": "HR", "cost": tarp_cost})
            total_gross_estimate += tarp_cost

        return {
            "gross_construction_total": total_gross_estimate,
            "line_items": line_items
        }

if __name__ == "__main__":
    print("=== ESTIMATE PARSING ENGINE DIAGNOSTIC ===")
    # Simulate data ingestion pulled directly from the local bridge transaction cache
    sample_field_meta = {
        "roof_squares": 32.5,
        "tarping_required": True
    }
    
    engine = ClaimAnalysisEngine()
    analysis = engine.calculate_scope_value(sample_field_meta)
    print(json.dumps(analysis, indent=4))
