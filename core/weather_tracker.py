import json
import urllib.request
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WEATHER-CORE] - %(levelname)s - %(message)s')

class AutoCorrectingWeatherEngine:
    def __init__(self):
        self.api_url = "https://archive-api.open-meteo.com/v1/archive"

    def _fetch_day_metrics(self, lat: float, lon: float, query_date: str) -> dict:
        """Helper to pull meteorological data for a singular target window."""
        params = (
            f"?latitude={lat}&longitude={lon}"
            f"&start_date={query_date}&end_date={query_date}"
            f"&daily=wind_speed_10m_max,precipitation_sum&timezone=auto"
        )
        try:
            req = urllib.request.Request(self.api_url + params, headers={'User-Agent': 'StormRestorationApp/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                daily = data.get("daily", {})
                return {
                    "max_wind": daily.get("wind_speed_10m_max", [0.0])[0],
                    "precip": daily.get("precipitation_sum", [0.0])[0]
                }
        except Exception:
            return {"max_wind": 0.0, "precip": 0.0}

    def verify_or_discover_storm(self, lat: float, lon: float, alleged_date: str) -> dict:
        """Validates the target date, or automatically scans a 14-day window for a verifiable weather anomaly."""
        logging.info(f"Validating primary Date of Loss target: {alleged_date}")
        initial_check = self._fetch_day_metrics(lat, lon, alleged_date)
        
        # Safe carrier verification threshold boundaries
        if initial_check["max_wind"] >= 40.0 or initial_check["precip"] >= 10.0:
            return {
                "status": "VERIFIED_PRIMARY",
                "verified_date": alleged_date,
                "metrics": initial_check,
                "search_performed": False
            }
            
        logging.warning(f"Primary date [{alleged_date}] failed carrier thresholds. Initializing autonomous correction scan...")
        
        # Parse the datetime string to run a surrounding window timeline analysis
        base_dt = datetime.strptime(alleged_date, "%Y-%m-%d")
        best_date = alleged_date
        highest_wind = initial_check["max_wind"]
        matching_metrics = initial_check
        
        # Scan a 14-day trailing/leading envelope window to locate the local meteorological event peak
        for offset in range(-7, 8):
            if offset == 0: continue
            current_date_str = (base_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
            metrics = self._fetch_day_metrics(lat, lon, current_date_str)
            
            if metrics["max_wind"] > highest_wind:
                highest_wind = metrics["max_wind"]
                best_date = current_date_str
                matching_metrics = metrics

        if highest_wind >= 40.0:
            return {
                "status": "AUTO_CORRECTED",
                "verified_date": best_date,
                "metrics": matching_metrics,
                "search_performed": True,
                "note": f"Adjusted date of loss from {alleged_date} to {best_date} based on verifiable wind speeds."
            }
            
        return {
            "status": "UNVERIFIABLE_LOD",
            "verified_date": alleged_date,
            "metrics": initial_check,
            "search_performed": True,
            "note": "No severe weather events could be metrologically verified within the 14-day window."
        }

if __name__ == "__main__":
    print("=== AUTONOMOUS METEOROLOGICAL CORRECTION ENGINE ===")
    engine = AutoCorrectingWeatherEngine()
    
    # Simulate scanning a location that has low wind on the 15th, but had a major storm hit on the 18th
    test_lat, test_lon, user_input_date = 39.0997, -94.5786, "2026-05-15"
    result = engine.verify_or_discover_storm(test_lat, test_lon, user_input_date)
    print(json.dumps(result, indent=4))
