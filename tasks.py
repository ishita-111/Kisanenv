from __future__ import annotations
from typing import Any

CROP_DATA: dict[str, dict[str, Any]] = {
    "wheat": {
        "scientific_name": "Triticum aestivum",
        "growth_stages": ["seedling", "vegetative", "flowering", "grain_filling", "harvest_ready"],
        "days_per_stage": [15, 30, 20, 25, 10],
        "optimal_temp_range": (15.0, 25.0),
        "optimal_moisture": 0.55,
        "base_market_price": 2150.0,
        "expected_yield_qtl_per_ha": 45.0,
        "initial_investment_inr": 2000.0,
        "costs": {
            "spray_pesticide": 800,
            "spray_fungicide": 600,
            "apply_fertilizer": 500,
            "irrigate": 300,
            "request_soil_test": 200,
            "consult_market": 0,
            "harvest_now": 400,
            "sell_crop": 0,
            "wait_observe": 0,
            "file_insurance_claim": 0,
        },
    },
    "cotton": {
        "scientific_name": "Gossypium hirsutum",
        "growth_stages": ["sowing", "vegetative", "flowering", "boll_formation", "harvest_ready"],
        "days_per_stage": [10, 35, 25, 40, 10],
        "optimal_temp_range": (25.0, 35.0),
        "optimal_moisture": 0.50,
        "base_market_price": 6500.0,
        "expected_yield_qtl_per_ha": 20.0,
        "initial_investment_inr": 4000.0,
        "costs": {
            "spray_pesticide": 1200,
            "spray_fungicide": 900,
            "apply_fertilizer": 700,
            "irrigate": 500,
            "request_soil_test": 250,
            "consult_market": 0,
            "harvest_now": 600,
            "sell_crop": 0,
            "wait_observe": 0,
            "file_insurance_claim": 0,
        },
    },
    "soybean": {
        "scientific_name": "Glycine max",
        "growth_stages": ["seedling", "vegetative", "flowering", "pod_filling", "harvest_ready"],
        "days_per_stage": [12, 30, 20, 30, 8],
        "optimal_temp_range": (20.0, 30.0),
        "optimal_moisture": 0.50,
        "base_market_price": 4200.0,
        "expected_yield_qtl_per_ha": 25.0,
        "initial_investment_inr": 3000.0,
        "costs": {
            "spray_pesticide": 1000,
            "spray_fungicide": 750,
            "apply_fertilizer": 600,
            "irrigate": 400,
            "request_soil_test": 200,
            "consult_market": 0,
            "harvest_now": 500,
            "sell_crop": 0,
            "wait_observe": 0,
            "file_insurance_claim": 0,
        },
    },
}

TASKS: dict[str, dict[str, Any]] = {
    "task_1_easy": {
        "name": "Pest or Deficiency",
        "difficulty": "easy",
        "seed": 42,
        "crop": "wheat",
        "scenario": "rust_vs_deficiency",
        "max_steps": 5,
        "budget_inr": 5000,
        "days_per_step": 1,
        "correct_action_sequence": ["request_soil_test", "spray_fungicide"],
    },
    "task_2_medium": {
        "name": "Cotton Season Management",
        "difficulty": "medium",
        "seed": 137,
        "crop": "cotton",
        "scenario": "full_season_bollworm",
        "max_steps": 15,
        "budget_inr": 15000,
        "days_per_step": 5,
        "surprise_event_step": 7,
        "surprise_event_type": "bollworm_outbreak",
    },
    "task_3_hard": {
        "name": "Crisis Navigation",
        "difficulty": "hard",
        "seed": 999,
        "crop": "soybean",
        "scenario": "compound_crisis",
        "max_steps": 20,
        "budget_inr": 8000,
        "days_per_step": 2,
        "insurance_unlock_step": 8,
        "insurance_close_step": 12,
        "active_crises": ["locust", "drought", "early_blight", "npk_imbalance", "price_crash_35pct"],
    },
}

def build_initial_state(task_id: str) -> dict[str, Any]:
    task = TASKS[task_id]
    crop_name = task["crop"]
    crop = CROP_DATA[crop_name]
    scenario = task["scenario"]

    state: dict[str, Any] = {
        "task_id": task_id,
        "crop_type": crop_name,
        "max_steps": task["max_steps"],
        "days_per_step": task.get("days_per_step", 1),
        "budget_inr": float(task["budget_inr"]),
        "crop_health": 100.0,
        "yield_potential_pct": 85.0,
        "step_number": 0,
        "day_of_season": 0,
        "season_day_total": sum(crop["days_per_stage"]),
        "previous_actions": [],
        "done": False,
        "done_reason": None,
        "total_spent_inr": crop["initial_investment_inr"],
        "initial_investment_inr": crop["initial_investment_inr"],
        "revenue_earned_inr": 0.0,
        "active_alerts": [],
        "_scenario": scenario,
        "_initial_budget": float(task["budget_inr"]),
        "_active_crises": task.get("active_crises", []),
        "_health_history": [100.0],
        "_critical_event_steps": {},
        "_critical_responded": {},
    }

    if scenario == "rust_vs_deficiency":
        state.update(_build_easy_scenario(crop))
    elif scenario == "full_season_bollworm":
        state.update(_build_medium_scenario(crop))
    elif scenario == "compound_crisis":
        state.update(_build_hard_scenario(crop, task))

    return state


def _build_easy_scenario(crop: dict) -> dict:
    return {
        "growth_stage": "vegetative",
        "days_to_harvest": 70,
        "day_of_season": 30,
        "weather": {
            "temperature_c": 22.0,
            "humidity_pct": 75.0,
            "wind_speed_kmh": 8.0,
            "rainfall_today_mm": 0.0,
            "forecast": [
                {"day": 1, "temp_c": 21.5, "rain_mm": 3.0, "humidity_pct": 78.0},
                {"day": 2, "temp_c": 22.0, "rain_mm": 0.0, "humidity_pct": 72.0},
                {"day": 3, "temp_c": 23.0, "rain_mm": 0.0, "humidity_pct": 70.0},
            ],
        },
        "soil": {
            "moisture": 0.55,
            "nitrogen_ppm": 48.0,
            "phosphorus_ppm": 22.0,
            "potassium_ppm": 28.0,
            "ph": 6.8,
            "last_tested_step": None,
            "_recently_tested": False,
            "nitrogen_ppm_observed": 35.0,
            "phosphorus_ppm_observed": 18.0,
            "potassium_ppm_observed": 24.0,
        },
        "pest_state": {
            "pressure": "moderate",
            "primary_pest": "unknown",
            "primary_disease": "wheat_rust",
            "disease_active": True,
            "disease_severity": 35.0,
            "infestation_pct": 25.0,
            "observed_probability": 0.55,
        },
        "market": {
            "price_per_qtl": 2150.0,
            "trend_momentum": 0.001,
            "volatility": 0.015,
            "price_history": [2120.0, 2135.0, 2150.0],
            "observed_trend": "stable",
        },
        "symptom_description": (
            "Yellowing leaves starting from older leaves in the lower canopy. "
            "Brown-orange pustules visible on leaf undersurface. "
            "Symptoms are spreading from one corner of the field. "
            "Conditions: 22C, 75% humidity. "
            "Initial soil nutrient estimates appear borderline. "
        ),
        "_actual_problem": "rust_fungus",
        "_correct_action": "spray_fungicide",
        "_soil_test_result": "nitrogen_normal",
        "_season_base_temp": 22.0,
        "_critical_event_steps": {0: "diagnosis_needed"},
        "_critical_responded": {},
    }


def _build_medium_scenario(crop: dict) -> dict:
    return {
        "growth_stage": "sowing",
        "days_to_harvest": 120,
        "day_of_season": 0,
        "weather": {
            "temperature_c": 32.0,
            "humidity_pct": 55.0,
            "wind_speed_kmh": 12.0,
            "rainfall_today_mm": 0.0,
            "forecast": [
                {"day": 1, "temp_c": 33.0, "rain_mm": 0.0, "humidity_pct": 52.0},
                {"day": 2, "temp_c": 31.0, "rain_mm": 5.0, "humidity_pct": 60.0},
                {"day": 3, "temp_c": 30.0, "rain_mm": 15.0, "humidity_pct": 70.0},
            ],
        },
        "soil": {
            "moisture": 0.35,
            "nitrogen_ppm": 40.0,
            "phosphorus_ppm": 18.0,
            "potassium_ppm": 22.0,
            "ph": 7.0,
            "last_tested_step": None,
            "_recently_tested": False,
            "nitrogen_ppm_observed": 38.0,
            "phosphorus_ppm_observed": 16.0,
            "potassium_ppm_observed": 20.0,
        },
        "pest_state": {
            "pressure": "none",
            "primary_pest": "none",
            "primary_disease": "none",
            "disease_active": False,
            "disease_severity": 0.0,
            "infestation_pct": 0.0,
            "observed_probability": 0.0,
        },
        "market": {
            "price_per_qtl": 6500.0,
            "trend_momentum": 0.005,
            "volatility": 0.02,
            "price_history": [6400.0, 6450.0, 6500.0],
            "observed_trend": "rising",
        },
        "symptom_description": (
            "Cotton seeds prepared for sowing. Field tilled and ready. "
            "Monsoon onset expected in 5 days. Soil appears dry. "
            "No pest or disease pressure currently."
        ),
        "_season_base_temp": 32.0,
        "_season_events": {
            3: {
                "type": "nutrient_need",
                "description": (
                    "Cotton entering vegetative growth phase. "
                    "Nutrient demand increasing rapidly. "
                    "Leaf color appears slightly pale."
                ),
                "alerts": ["Nutrient demand increasing"],
            },
            7: {
                "type": "bollworm_outbreak",
                "description": (
                    "ALERT: American bollworm (Helicoverpa armigera) infestation detected! "
                    "Larvae observed on ~30% of bolls. Square and boll damage visible. "
                ),
                "pest_pressure": "severe",
                "pest_update": {
                    "primary_pest": "bollworm_helicoverpa",
                    "infestation_pct": 30.0,
                    "observed_probability": 0.85,
                },
                "crop_health_penalty": 20.0,
                "alerts": ["CRITICAL: Bollworm outbreak"],
            },
            10: {
                "type": "market_opportunity",
                "description": (
                    "Market advisory: Cotton prices rising due to export demand. "
                    "Current price premium of 8% over last month."
                ),
                "alerts": ["Market opportunity — prices rising"],
            },
        },
        "_growth_schedule": {
            0: "sowing", 1: "sowing",
            2: "vegetative", 3: "vegetative", 4: "vegetative", 5: "vegetative",
            6: "flowering", 7: "flowering", 8: "flowering",
            9: "boll_formation", 10: "boll_formation", 11: "boll_formation",
            12: "harvest_ready", 13: "harvest_ready", 14: "harvest_ready",
        },
        "_critical_event_steps": {7: "bollworm_outbreak"},
        "_critical_responded": {},
    }


def _build_hard_scenario(crop: dict, task: dict) -> dict:
    return {
        "growth_stage": "flowering",
        "days_to_harvest": 40,
        "day_of_season": 60,
        "weather": {
            "temperature_c": 38.0,
            "humidity_pct": 35.0,
            "wind_speed_kmh": 18.0,
            "rainfall_today_mm": 0.0,
            "forecast": [
                {"day": 1, "temp_c": 39.0, "rain_mm": 0.0, "humidity_pct": 32.0},
                {"day": 2, "temp_c": 40.0, "rain_mm": 0.0, "humidity_pct": 28.0},
                {"day": 3, "temp_c": 37.0, "rain_mm": 0.0, "humidity_pct": 35.0},
            ],
        },
        "soil": {
            "moisture": 0.12,
            "nitrogen_ppm": 18.0,
            "phosphorus_ppm": 8.0,
            "potassium_ppm": 14.0,
            "ph": 7.5,
            "last_tested_step": None,
            "_recently_tested": False,
            "nitrogen_ppm_observed": 30.0,
            "phosphorus_ppm_observed": 12.0,
            "potassium_ppm_observed": 16.0,
        },
        "pest_state": {
            "pressure": "severe",
            "primary_pest": "locust",
            "primary_disease": "early_blight",
            "disease_active": True,
            "disease_severity": 25.0,
            "infestation_pct": 40.0,
            "observed_probability": 0.75,
        },
        "market": {
            "price_per_qtl": 2730.0,
            "trend_momentum": -0.008,
            "volatility": 0.04,
            "price_history": [3500.0, 3200.0, 3000.0, 2900.0, 2800.0, 2730.0],
            "observed_trend": "falling",
        },
        "symptom_description": (
            "COMPOUND CRISIS — Multiple simultaneous issues detected:\n"
            "1) LOCUST: Swarm spotted 50 km away, advancing. Initial feeding damage "
            "visible on field edges (~40% affected).\n"
            "2) DROUGHT: Monsoon failed — Day 60 with negligible rainfall. "
            "Soil moisture critically low (0.12). Wilting observed.\n"
            "3) DISEASE: Dark lesions with concentric rings on lower leaves — "
            "consistent with early blight.\n"
            "4) CONFLICTING SIGNALS: Yellowing and purple discoloration could indicate "
            "NPK deficiency, cold stress, OR disease progression.\n"
            "5) MARKET: Mandi prices crashed 35% due to oversupply. "
            "Current: 2730/qtl (was 4200).\n"
            "Insurance claim window opens at step 8, closes at step 12.\n"
            "WARNING: Budget limited to 8000. Every action must be justified."
        ),
        "_insurance_unlock_step": task.get("insurance_unlock_step", 8),
        "_insurance_close_step": task.get("insurance_close_step", 12),
        "_insurance_filed": False,
        "_price_crash_pct": 0.35,
        "_season_base_temp": 38.0,
        "_season_events": {
            3: {
                "type": "unreliable_report",
                "description": (
                    "Neighbor farmer reports locust swarm has changed direction. "
                    "However, district agricultural officer contradicts this. "
                ),
                "alerts": ["Conflicting locust reports — uncertain trajectory"],
            },
            6: {
                "type": "government_advisory",
                "description": (
                    "Government crop advisory released: Apply DAP fertilizer immediately. "
                    "Advisory is generic, not field-specific. "
                ),
                "alerts": ["Government advisory conflicts with field observations"],
                "pest_update": {
                    "disease_severity_increase": 15.0,
                },
            },
            8: {
                "type": "insurance_window_open",
                "description": (
                    "INSURANCE WINDOW NOW OPEN. "
                    "Expected payout: 3500-5000 based on damage assessment. "
                    "Window closes at step 12."
                ),
                "alerts": ["Insurance claim window OPEN"],
            },
            10: {
                "type": "unexpected_rainfall",
                "description": (
                    "SURPRISE: Unexpected rainfall of 25mm received! "
                    "Soil moisture partially restored. "
                ),
                "weather_override": {
                    "rainfall_today_mm": 25.0,
                    "humidity_pct": 72.0,
                },
                "soil_moisture_boost": 0.15,
                "alerts": ["Unexpected rainfall"],
            },
            12: {
                "type": "insurance_window_close",
                "description": (
                    "Insurance claim window has CLOSED. "
                ),
                "alerts": ["Insurance window closed"],
            },
            14: {
                "type": "market_spike",
                "description": (
                    "MARKET SPIKE: Soybean prices surge 18% due to export order. "
                ),
                "market_spike_pct": 0.18,
                "alerts": ["Market spike"],
            },
        },
        "_growth_schedule": {
            0: "flowering", 1: "flowering", 2: "flowering", 3: "flowering",
            4: "pod_filling", 5: "pod_filling", 6: "pod_filling", 7: "pod_filling",
            8: "pod_filling", 9: "pod_filling", 10: "pod_filling",
            11: "harvest_ready", 12: "harvest_ready", 13: "harvest_ready",
            14: "harvest_ready", 15: "harvest_ready", 16: "harvest_ready",
            17: "harvest_ready", 18: "harvest_ready", 19: "harvest_ready",
        },
        "_critical_event_steps": {
            0: "compound_crisis_start",
            8: "insurance_window",
            14: "market_spike",
        },
        "_critical_responded": {},
    }
