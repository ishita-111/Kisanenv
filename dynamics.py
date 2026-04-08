from __future__ import annotations

import math
import random
from typing import Any, List, Optional

OPTIMAL_DOSAGE: dict[str, dict[str, tuple[float, float]]] = {
    "spray_pesticide": {
        "wheat": (1.5, 3.0),
        "cotton": (2.0, 4.0),
        "soybean": (1.5, 3.5),
    },
    "spray_fungicide": {
        "wheat": (1.0, 2.5),
        "cotton": (1.5, 3.0),
        "soybean": (1.0, 2.5),
    },
    "apply_fertilizer": {
        "wheat": (2.0, 5.0),
        "cotton": (3.0, 6.0),
        "soybean": (2.0, 4.5),
    },
    "irrigate": {
        "wheat": (20.0, 40.0),
        "cotton": (25.0, 50.0),
        "soybean": (20.0, 45.0),
    },
}

OPTIMAL_TIMING: dict[str, str] = {
    "spray_pesticide": "morning",
    "spray_fungicide": "morning",
    "apply_fertilizer": "morning",
    "irrigate": "evening",
    "harvest_now": "morning",
    "request_soil_test": "immediate",
    "consult_market": "immediate",
    "wait_observe": "immediate",
    "sell_crop": "immediate",
    "file_insurance_claim": "immediate",
}

STAGE_NUTRIENT_NEEDS: dict[str, dict[str, tuple[float, float, float]]] = {
    "seedling":      {"wheat": (30, 15, 20), "cotton": (25, 15, 18), "soybean": (20, 18, 15)},
    "sowing":        {"wheat": (25, 12, 18), "cotton": (20, 12, 15), "soybean": (18, 15, 12)},
    "vegetative":    {"wheat": (50, 20, 30), "cotton": (45, 25, 35), "soybean": (35, 25, 30)},
    "flowering":     {"wheat": (40, 30, 40), "cotton": (35, 30, 40), "soybean": (30, 30, 35)},
    "boll_formation":{"wheat": (30, 25, 35), "cotton": (30, 25, 45), "soybean": (25, 20, 30)},
    "grain_filling": {"wheat": (25, 20, 30), "cotton": (25, 20, 30), "soybean": (20, 18, 25)},
    "pod_filling":   {"wheat": (25, 20, 30), "cotton": (25, 20, 30), "soybean": (25, 22, 28)},
    "harvest_ready": {"wheat": (15, 10, 15), "cotton": (15, 10, 15), "soybean": (12, 10, 12)},
}

class WeatherEngine:
    @staticmethod
    def advance(state: dict, rng: random.Random, days: int = 1) -> None:
        weather_state = state["weather"]

        for _ in range(days):
            season_target = state.get("_season_base_temp", 30.0)
            drift = (season_target - weather_state["temperature_c"]) * 0.1
            weather_state["temperature_c"] += drift + rng.gauss(0, 1.2)
            weather_state["temperature_c"] = max(5.0, min(50.0, weather_state["temperature_c"]))

            base_humidity = max(20, min(95, 80 - (weather_state["temperature_c"] - 25) * 1.5))
            weather_state["humidity_pct"] += (base_humidity - weather_state["humidity_pct"]) * 0.15
            weather_state["humidity_pct"] += rng.gauss(0, 3)
            weather_state["humidity_pct"] = max(15.0, min(98.0, weather_state["humidity_pct"]))

            weather_state["wind_speed_kmh"] = max(0, weather_state["wind_speed_kmh"] + rng.gauss(0, 2))
            weather_state["wind_speed_kmh"] = max(0.0, min(60.0, weather_state["wind_speed_kmh"]))

            drought_active = "drought" in state.get("_active_crises", [])
            rain_prob = 0.05 if drought_active else 0.25
            if weather_state["humidity_pct"] > 75:
                rain_prob += 0.15
            if rng.random() < rain_prob:
                weather_state["rainfall_today_mm"] = rng.uniform(2, 45) * (0.2 if drought_active else 1.0)
            else:
                weather_state["rainfall_today_mm"] = 0.0

        weather_state["forecast"] = []
        for offset in range(1, 4):
            forecast_temp = weather_state["temperature_c"] + rng.gauss(0, 2 * offset)
            forecast_rain = max(0, weather_state["rainfall_today_mm"] * rng.uniform(0.3, 1.5) + rng.gauss(0, 5))
            forecast_humidity = weather_state["humidity_pct"] + rng.gauss(0, 5 * offset)
            weather_state["forecast"].append({
                "day": offset,
                "temp_c": round(max(5, min(50, forecast_temp)), 1),
                "rain_mm": round(max(0, forecast_rain), 1),
                "humidity_pct": round(max(15, min(98, forecast_humidity)), 1),
            })


class SoilEngine:
    @staticmethod
    def advance(state: dict, rng: random.Random, days: int = 1) -> None:
        soil_state = state["soil"]
        weather_state = state["weather"]

        for _ in range(days):
            temp_c = weather_state["temperature_c"]
            evaporation_rate = 0.015 + 0.008 * max(0, (temp_c - 25) / 25)
            wind_evaporation = weather_state["wind_speed_kmh"] * 0.001
            rainfall_contribution = weather_state["rainfall_today_mm"] / 150.0
            soil_state["moisture"] += rainfall_contribution - evaporation_rate - wind_evaporation
            soil_state["moisture"] = max(0.0, min(1.0, soil_state["moisture"]))

            crop_name = state["crop_type"]
            growth_stage = state["growth_stage"]
            nutrient_needs = STAGE_NUTRIENT_NEEDS.get(growth_stage, {}).get(crop_name, (30, 15, 20))

            depletion_factor = 0.008 if growth_stage in ("vegetative", "flowering") else 0.004
            soil_state["nitrogen_ppm"] -= nutrient_needs[0] * depletion_factor + rng.gauss(0, 0.3)
            soil_state["phosphorus_ppm"] -= nutrient_needs[1] * depletion_factor * 0.5 + rng.gauss(0, 0.15)
            soil_state["potassium_ppm"] -= nutrient_needs[2] * depletion_factor * 0.6 + rng.gauss(0, 0.2)

            soil_state["ph"] += rng.gauss(0, 0.02)
            soil_state["ph"] = max(4.0, min(9.0, soil_state["ph"]))

            soil_state["nitrogen_ppm"] = max(0.0, min(200.0, soil_state["nitrogen_ppm"]))
            soil_state["phosphorus_ppm"] = max(0.0, min(100.0, soil_state["phosphorus_ppm"]))
            soil_state["potassium_ppm"] = max(0.0, min(150.0, soil_state["potassium_ppm"]))

        observation_noise = 1.0 if soil_state.get("_recently_tested", False) else 3.0
        soil_state["nitrogen_ppm_observed"] = max(0, soil_state["nitrogen_ppm"] + rng.gauss(0, observation_noise * 5))
        soil_state["phosphorus_ppm_observed"] = max(0, soil_state["phosphorus_ppm"] + rng.gauss(0, observation_noise * 3))
        soil_state["potassium_ppm_observed"] = max(0, soil_state["potassium_ppm"] + rng.gauss(0, observation_noise * 4))

        last_test = soil_state.get("last_tested_step")
        if last_test is None:
            last_test = -10
        steps_since_analysis = state["step_number"] - last_test
        soil_state["_recently_tested"] = steps_since_analysis <= 3

    @staticmethod
    def apply_fertilizer(state: dict, dosage: float) -> None:
        soil_state = state["soil"]
        soil_state["nitrogen_ppm"] += dosage * 8.0
        soil_state["phosphorus_ppm"] += dosage * 3.0
        soil_state["potassium_ppm"] += dosage * 4.0
        soil_state["nitrogen_ppm"] = min(200.0, soil_state["nitrogen_ppm"])
        soil_state["phosphorus_ppm"] = min(100.0, soil_state["phosphorus_ppm"])
        soil_state["potassium_ppm"] = min(150.0, soil_state["potassium_ppm"])

    @staticmethod
    def apply_irrigation(state: dict, dosage: float) -> None:
        moisture_gain = min(dosage, 50.0) / 50.0 * 0.35
        state["soil"]["moisture"] = min(1.0, state["soil"]["moisture"] + moisture_gain)


class PestEngine:
    PRESSURE_LEVELS = ["none", "low", "moderate", "severe", "critical"]

    @staticmethod
    def advance(state: dict, rng: random.Random, days: int = 1) -> None:
        pest_state = state["pest_state"]
        weather_state = state["weather"]

        for _ in range(days):
            humidity_factor = max(0, (weather_state["humidity_pct"] - 50)) / 50.0
            temp_factor = max(0, (weather_state["temperature_c"] - 20)) / 30.0
            spread_prob = 0.05 + 0.15 * humidity_factor + 0.10 * temp_factor

            current_pressure_idx = PestEngine.PRESSURE_LEVELS.index(pest_state["pressure"])

            if current_pressure_idx >= 1 and rng.random() < spread_prob:
                if current_pressure_idx < len(PestEngine.PRESSURE_LEVELS) - 1:
                    pest_state["pressure"] = PestEngine.PRESSURE_LEVELS[current_pressure_idx + 1]
                    pest_state["infestation_pct"] = min(100, pest_state["infestation_pct"] + rng.uniform(5, 15))

            if pest_state.get("disease_active", False):
                pest_state["disease_severity"] = min(100, pest_state["disease_severity"] + rng.uniform(1, 4))

            if current_pressure_idx >= 1 and rng.random() < 0.03:
                pest_state["pressure"] = PestEngine.PRESSURE_LEVELS[max(0, current_pressure_idx - 1)]

        actual_pressure_idx = PestEngine.PRESSURE_LEVELS.index(pest_state["pressure"])
        pest_state["observed_probability"] = min(1.0, actual_pressure_idx / 4.0 + rng.gauss(0, 0.1))
        pest_state["observed_probability"] = max(0.0, pest_state["observed_probability"])

    @staticmethod
    def apply_pesticide(state: dict, dosage: float, crop: str) -> float:
        pest_state = state["pest_state"]
        optimal_range = OPTIMAL_DOSAGE.get("spray_pesticide", {}).get(crop, (2.0, 4.0))
        effectiveness_score = _dosage_effectiveness(dosage, optimal_range)

        current_pressure_idx = PestEngine.PRESSURE_LEVELS.index(pest_state["pressure"])
        level_reduction = int(effectiveness_score * 2)
        new_idx = max(0, current_pressure_idx - level_reduction)
        pest_state["pressure"] = PestEngine.PRESSURE_LEVELS[new_idx]
        pest_state["infestation_pct"] = max(0, pest_state["infestation_pct"] * (1 - effectiveness_score * 0.6))
        return effectiveness_score

    @staticmethod
    def apply_fungicide(state: dict, dosage: float, crop: str) -> float:
        pest_state = state["pest_state"]
        optimal_range = OPTIMAL_DOSAGE.get("spray_fungicide", {}).get(crop, (1.5, 3.0))
        effectiveness_score = _dosage_effectiveness(dosage, optimal_range)

        if pest_state.get("disease_active", False):
            pest_state["disease_severity"] = max(0, pest_state["disease_severity"] * (1 - effectiveness_score * 0.7))
            if pest_state["disease_severity"] < 5:
                pest_state["disease_active"] = False
        current_pressure_idx = PestEngine.PRESSURE_LEVELS.index(pest_state["pressure"])
        if current_pressure_idx > 0:
            pest_state["pressure"] = PestEngine.PRESSURE_LEVELS[max(0, current_pressure_idx - 1)]
        return effectiveness_score


class CropEngine:
    @staticmethod
    def advance(state: dict, rng: random.Random, days: int = 1) -> None:
        crop_name = state["crop_type"]
        soil_state = state["soil"]
        weather_state = state["weather"]
        pest_state = state["pest_state"]

        from tasks import CROP_DATA
        crop_data = CROP_DATA[crop_name]
        optimal_low, optimal_high = crop_data["optimal_temp_range"]

        for _ in range(days):
            health_delta = 0.0

            current_temp = weather_state["temperature_c"]
            if current_temp < optimal_low:
                health_delta -= (optimal_low - current_temp) * 0.25
            elif current_temp > optimal_high:
                health_delta -= (current_temp - optimal_high) * 0.30

            if soil_state["moisture"] < 0.15:
                health_delta -= 3.5
            elif soil_state["moisture"] < 0.25:
                health_delta -= 1.5
            elif soil_state["moisture"] > 0.90:
                health_delta -= 1.0

            growth_stage = state["growth_stage"]
            nutrient_needs = STAGE_NUTRIENT_NEEDS.get(growth_stage, {}).get(crop_name, (30, 15, 20))
            nitrogen_deficit = max(0, nutrient_needs[0] - soil_state["nitrogen_ppm"]) / nutrient_needs[0]
            phosphorus_deficit = max(0, nutrient_needs[1] - soil_state["phosphorus_ppm"]) / nutrient_needs[1]
            potassium_deficit = max(0, nutrient_needs[2] - soil_state["potassium_ppm"]) / nutrient_needs[2]
            total_nutrient_stress = (nitrogen_deficit * 0.5 + phosphorus_deficit * 0.25 + potassium_deficit * 0.25)
            health_delta -= total_nutrient_stress * 2.0

            pest_pressure_idx = PestEngine.PRESSURE_LEVELS.index(pest_state["pressure"])
            health_delta -= pest_pressure_idx * 1.2
            if pest_state.get("disease_active", False):
                health_delta -= pest_state["disease_severity"] * 0.04

            if health_delta > -0.5:
                natural_recovery = (70 - state["crop_health"]) * 0.02
                health_delta += max(-0.5, min(0.5, natural_recovery))

            state["crop_health"] += health_delta
            state["crop_health"] = max(0.0, min(100.0, state["crop_health"]))

        state["yield_potential_pct"] = _compute_yield_potential(state)
        state["days_to_harvest"] = max(0, state["days_to_harvest"] - days)

    @staticmethod
    def compute_nutrient_deficiency_visible(state: dict) -> bool:
        soil_state = state["soil"]
        crop_name = state["crop_type"]
        growth_stage = state["growth_stage"]
        nutrient_needs = STAGE_NUTRIENT_NEEDS.get(growth_stage, {}).get(crop_name, (30, 15, 20))
        return (
            soil_state["nitrogen_ppm"] < nutrient_needs[0] * 0.6
            or soil_state["phosphorus_ppm"] < nutrient_needs[1] * 0.5
            or soil_state["potassium_ppm"] < nutrient_needs[2] * 0.5
        )


class MarketEngine:
    @staticmethod
    def advance(state: dict, rng: random.Random, days: int = 1) -> None:
        market_state = state["market"]

        for _ in range(days):
            current_trend = market_state.get("trend_momentum", 0.0)
            current_trend += rng.gauss(0, 0.003)
            current_trend = max(-0.03, min(0.03, current_trend))
            market_state["trend_momentum"] = current_trend

            price_volatility = market_state.get("volatility", 0.02)
            price_change = current_trend + rng.gauss(0, price_volatility)

            if "price_crash_35pct" in state.get("_active_crises", []):
                price_change -= 0.005

            market_state["price_per_qtl"] *= (1.0 + price_change)
            market_state["price_per_qtl"] = max(500.0, min(15000.0, market_state["price_per_qtl"]))

            price_records = market_state.get("price_history", [])
            price_records.append(round(market_state["price_per_qtl"], 2))
            if len(price_records) > 10:
                price_records = price_records[-10:]
            market_state["price_history"] = price_records

        price_records = market_state.get("price_history", [])
        if len(price_records) >= 3:
            recent_average = sum(price_records[-3:]) / 3
            older_average = sum(price_records[:min(3, len(price_records))]) / min(3, len(price_records))
            if recent_average > older_average * 1.02:
                market_state["observed_trend"] = "rising"
            elif recent_average < older_average * 0.98:
                market_state["observed_trend"] = "falling"
            else:
                market_state["observed_trend"] = "stable"
        else:
            market_state["observed_trend"] = "unknown"

def _dosage_effectiveness(dosage: float, optimal_range: tuple[float, float]) -> float:
    optimal_low, optimal_high = optimal_range
    if dosage <= 0:
        return 0.0
    if optimal_low <= dosage <= optimal_high:
        return 1.0
    if dosage < optimal_low:
        return max(0.0, dosage / optimal_low)
    overload_ratio = dosage / optimal_high
    return max(0.0, 1.0 - (overload_ratio - 1.0) * 0.5)

def _compute_yield_potential(state: dict) -> float:
    current_health = state["crop_health"]
    previous_yield = state.get("yield_potential_pct", 80.0)
    decay_alpha = 0.3
    yield_estimate = decay_alpha * current_health + (1 - decay_alpha) * previous_yield
    if current_health < 30:
        yield_estimate *= 0.95
    return round(max(0.0, min(100.0, yield_estimate)), 1)

def compute_dosage_score(action_type: str, dosage: float, crop: str) -> float:
    optimal_window = OPTIMAL_DOSAGE.get(action_type)
    if not optimal_window or crop not in optimal_window:
        return 0.0
    optimal_low, optimal_high = optimal_window[crop]
    if optimal_low <= dosage <= optimal_high:
        return 0.10
    if dosage <= 0:
        return -0.05
    if dosage < optimal_low:
        return -0.03
    overload_ratio = dosage / optimal_high
    return max(-0.10, -0.05 * (overload_ratio - 1.0))

def compute_timing_score(action_type: str, timing: str) -> float:
    optimal_timing = OPTIMAL_TIMING.get(action_type, "immediate")
    if optimal_timing == "immediate":
        return 0.05
    if timing == optimal_timing:
        return 0.10
    if timing == "immediate":
        return 0.0
    return -0.05

def generate_symptom_description(state: dict, rng: random.Random) -> str:
    description_parts = []
    soil_state = state["soil"]
    pest_state = state["pest_state"]
    weather_state = state["weather"]
    crop_name = state["crop_type"]
    growth_stage = state["growth_stage"]

    current_health = state["crop_health"]
    if current_health > 80:
        description_parts.append(f"Crop healthy at {growth_stage}.")
    elif current_health > 50:
        description_parts.append(f"Crop stress at {growth_stage}.")
    elif current_health > 25:
        description_parts.append(f"Crop damage at {growth_stage}.")
    else:
        description_parts.append(f"Crop survival at risk at {growth_stage}.")

    if pest_state["pressure"] in ("moderate", "severe", "critical"):
        pest_identifier = pest_state.get("primary_pest", "pest")
        description_parts.append(
            f"{pest_identifier} ({pest_state['pressure']}, "
            f"~{pest_state['infestation_pct']:.0f}%)."
        )

    if pest_state.get("disease_active", False):
        disease_identifier = pest_state.get("primary_disease", "infection")
        description_parts.append(
            f"{disease_identifier} (severity {pest_state['disease_severity']:.0f}/100)."
        )

    if CropEngine.compute_nutrient_deficiency_visible(state):
        nitrogen_low = soil_state["nitrogen_ppm"] < 25
        phosphorus_low = soil_state["phosphorus_ppm"] < 10
        potassium_low = soil_state["potassium_ppm"] < 12
        if nitrogen_low:
            description_parts.append("Yellowing leaves.")
        if phosphorus_low:
            description_parts.append("Purple discoloration.")
        if potassium_low:
            description_parts.append("Edge browning.")

    if weather_state["rainfall_today_mm"] > 20:
        description_parts.append(f"Heavy rainfall: {weather_state['rainfall_today_mm']:.0f}mm.")
    if soil_state["moisture"] < 0.20:
        description_parts.append("Drought stress.")
    elif soil_state["moisture"] > 0.85:
        description_parts.append("Waterlogged.")

    if weather_state["temperature_c"] > 40:
        description_parts.append(f"Heat stress: {weather_state['temperature_c']:.1f}C.")

    active_alerts = state.get("active_alerts", [])
    for alert_msg in active_alerts:
        description_parts.append(f"{alert_msg}")

    return " ".join(description_parts) if description_parts else f"Crop at {growth_stage}."
