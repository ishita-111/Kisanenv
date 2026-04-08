from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from enum import Enum
from typing import Any, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from grader import KisanGrader
from tasks import CROP_DATA, TASKS, build_initial_state
from dynamics import (
    WeatherEngine, SoilEngine, PestEngine, CropEngine, MarketEngine,
    generate_symptom_description
)

class ActionType(str, Enum):
    spray_pesticide = "spray_pesticide"
    spray_fungicide = "spray_fungicide"
    apply_fertilizer = "apply_fertilizer"
    irrigate = "irrigate"
    harvest_now = "harvest_now"
    wait_observe = "wait_observe"
    sell_crop = "sell_crop"
    request_soil_test = "request_soil_test"
    consult_market = "consult_market"
    file_insurance_claim = "file_insurance_claim"

class DayForecast(BaseModel):
    day: int
    temp_c: float
    rain_mm: float
    humidity_pct: float

class WeatherData(BaseModel):
    temperature_c: float
    humidity_pct: float
    wind_speed_kmh: float
    rainfall_today_mm: float
    forecast: List[DayForecast]

class SoilData(BaseModel):
    moisture: float
    nitrogen_ppm_observed: float
    phosphorus_ppm_observed: float
    potassium_ppm_observed: float
    last_tested_step: Optional[int]

class EconomicsData(BaseModel):
    total_spent_inr: float
    revenue_earned_inr: float
    profit_loss_inr: float
    expected_max_profit: float

class Observation(BaseModel):
    crop_type: str
    growth_stage: str
    symptom_description: str
    weather: WeatherData
    soil: SoilData
    pest_probability_observed: float
    market_price_per_qtl: float
    market_trend_observed: str
    budget_remaining_inr: float
    yield_estimate_pct: float
    days_to_harvest: int
    day_of_season: int
    season_day_total: int
    active_alerts: List[str]
    previous_actions: List[str] = []
    step_number: int = 0
    task_id: str

class Action(BaseModel):
    action_type: ActionType
    target: str = ""
    dosage_or_amount: float = 0.0
    timing: str = "immediate"
    reasoning: str = ""

class ResetRequest(BaseModel):
    task_id: Optional[str] = "task_1_easy"

class GraderRequest(BaseModel):
    task_id: str
    history: list

ILLEGAL_ACTIONS_BY_STAGE: dict[str, list[str]] = {
    "seedling": ["harvest_now", "sell_crop"],
    "sowing": ["harvest_now", "sell_crop"],
    "vegetative": ["harvest_now", "sell_crop"],
    "flowering": ["harvest_now", "sell_crop"],
    "boll_formation": ["sell_crop"],
    "grain_filling": ["sell_crop"],
    "pod_filling": ["sell_crop"],
    "harvest_ready": [],
}

class KisanEnv:
    def __init__(self) -> None:
        self.grader = KisanGrader()
        self._state: dict[str, Any] = {}
        self._rng: random.Random = random.Random()
        self._episode_history: list[dict] = []
        self._cumulative_reward: float = 0.0
        self._expected_max_profit: float = 10000.0

    def reset(self, task_id: str) -> Observation:
        if task_id not in TASKS:
            raise ValueError(f"Unknown task_id: {task_id}.")

        seed_val = int(hashlib.md5(task_id.encode()).hexdigest(), 16) % (2 ** 32)
        self._rng = random.Random(seed_val)

        self._state = build_initial_state(task_id)
        self._episode_history = []
        self._cumulative_reward = 0.0

        crop_data = CROP_DATA[self._state["crop_type"]]
        max_revenue = crop_data["expected_yield_qtl_per_ha"] * crop_data["base_market_price"]
        self._expected_max_profit = max_revenue - crop_data["initial_investment_inr"]

        return self._make_observation()

    def step(self, action: Action) -> Tuple[Observation, float, bool, dict]:
        if self._state.get("done", False):
            raise RuntimeError("Episode is done.")

        action_type = action.action_type.value
        growth_stage = self._state.get("growth_stage", "")
        crop_name = self._state["crop_type"]
        crop_data = CROP_DATA[crop_name]
        days = self._state["days_per_step"]

        self._state["active_alerts"] = []

        illegal_actions = ILLEGAL_ACTIONS_BY_STAGE.get(growth_stage, [])
        if action_type in illegal_actions:
            return self._handle_illegal_action(action, action_type, growth_stage)

        cost = crop_data["costs"].get(action_type, 0)
        self._state["budget_inr"] -= cost
        self._state["total_spent_inr"] += cost
        self._apply_action_effects(action_type, action, crop_data)

        if action_type not in ("sell_crop", "harvest_now"):
            WeatherEngine.advance(self._state, self._rng, days)
            SoilEngine.advance(self._state, self._rng, days)
            PestEngine.advance(self._state, self._rng, days)
            CropEngine.advance(self._state, self._rng, days)
            MarketEngine.advance(self._state, self._rng, days)

            self._state["day_of_season"] += days

        self._check_scenario_events()
        self._advance_growth_stage()
        self._state["symptom_description"] = generate_symptom_description(self._state, self._rng)

        self._state["step_number"] += 1
        self._state["previous_actions"].append(action_type)

        action_dict = action.model_dump()
        step_reward = self.grader.compute_step_reward(action_type, action_dict, self._state)
        self._cumulative_reward += step_reward

        done, done_reason = self._check_done()
        self._state["done"] = done
        self._state["done_reason"] = done_reason

        info_dict = self._build_info_dict(done, done_reason)
        observation = self._make_observation()

        self._episode_history.append({
            "step": self._state["step_number"],
            "action": action_dict,
            "reward": round(step_reward, 4),
            "done": done,
            "observation": observation.model_dump(),
            "info": info_dict,
        })

        return observation, round(step_reward, 4), done, info_dict

    def state(self) -> dict:
        return {
            "current_observation": self._make_observation().model_dump() if "task_id" in self._state else None,
            "internal_state_snapshot": {
                "crop_health": self._state.get("crop_health"),
                "soil_true_n": self._state.get("soil", {}).get("nitrogen_ppm"),
                "pest_true_pressure": self._state.get("pest_state", {}).get("pressure"),
            } if self._state else None,
            "episode_history": self._episode_history,
            "cumulative_reward": round(self._cumulative_reward, 4),
            "done": self._state.get("done", False),
            "task_id": self._state.get("task_id"),
        }

    def _handle_illegal_action(self, action: Action, action_type: str, growth_stage: str):
        info_dict = {
            "error": f"Action '{action_type}' is illegal at growth stage '{growth_stage}'",
            "step_breakdown": {
                "correctness": -0.30,
                "timing": 0.0, "dosage": 0.0,
                "budget_efficiency": 0.0, "reasoning_quality": 0.0,
                "urgency_response": -0.1, "loop_penalty": 0.0, "waste_penalty": -0.1,
            },
            "crop_health_pct": self._state["crop_health"],
            "max_steps": self._state["max_steps"],
        }
        reward = -0.30
        self._cumulative_reward += reward
        self._state["previous_actions"].append(action_type)
        self._state["step_number"] += 1
        observation = self._make_observation()
        self._episode_history.append({
            "step": self._state["step_number"],
            "action": action.model_dump(),
            "reward": reward,
            "done": False,
            "observation": observation.model_dump(),
            "info": info_dict,
        })
        return observation, reward, False, info_dict

    def _make_observation(self) -> Observation:
        weather_state = self._state["weather"]
        soil_state = self._state["soil"]
        pest_state = self._state["pest_state"]
        market_state = self._state["market"]

        return Observation(
            crop_type=self._state["crop_type"],
            growth_stage=self._state["growth_stage"],
            symptom_description=self._state["symptom_description"],
            weather=WeatherData(
                temperature_c=round(weather_state["temperature_c"], 1),
                humidity_pct=round(weather_state["humidity_pct"], 1),
                wind_speed_kmh=round(weather_state["wind_speed_kmh"], 1),
                rainfall_today_mm=round(weather_state["rainfall_today_mm"], 1),
                forecast=[DayForecast(**f) for f in weather_state["forecast"]],
            ),
            soil=SoilData(
                moisture=round(soil_state["moisture"], 3),
                nitrogen_ppm_observed=round(soil_state["nitrogen_ppm_observed"], 1),
                phosphorus_ppm_observed=round(soil_state["phosphorus_ppm_observed"], 1),
                potassium_ppm_observed=round(soil_state["potassium_ppm_observed"], 1),
                last_tested_step=soil_state.get("last_tested_step", None),
            ),
            pest_probability_observed=round(pest_state.get("observed_probability", 0.0), 2),
            market_price_per_qtl=round(market_state["price_per_qtl"], 2),
            market_trend_observed=market_state["observed_trend"],
            budget_remaining_inr=round(self._state["budget_inr"], 2),
            yield_estimate_pct=round(self._state.get("yield_potential_pct", 100.0), 1),
            days_to_harvest=max(0, self._state["days_to_harvest"]),
            day_of_season=self._state["day_of_season"],
            season_day_total=self._state["season_day_total"],
            active_alerts=list(self._state["active_alerts"]),
            previous_actions=list(self._state["previous_actions"]),
            step_number=self._state["step_number"],
            task_id=self._state["task_id"],
        )

    def _apply_action_effects(self, action_type: str, action: Action, crop_data: dict) -> None:
        crop_name = self._state["crop_type"]
        dosage = action.dosage_or_amount

        if action_type == "irrigate":
            SoilEngine.apply_irrigation(self._state, dosage)
        elif action_type == "apply_fertilizer":
            SoilEngine.apply_fertilizer(self._state, dosage)
        elif action_type == "spray_pesticide":
            effectiveness = PestEngine.apply_pesticide(self._state, dosage, crop_name)
            if effectiveness > 0.5:
                self._state["active_alerts"].append("Pesticide applied successfully.")
        elif action_type == "spray_fungicide":
            effectiveness = PestEngine.apply_fungicide(self._state, dosage, crop_name)
            if effectiveness > 0.5:
                self._state["active_alerts"].append("Fungicide applied successfully.")
        elif action_type == "request_soil_test":
            self._state["soil"]["last_tested_step"] = self._state["step_number"] + 1
            self._state["soil"]["_recently_tested"] = True
            soil_state = self._state["soil"]
            soil_state["nitrogen_ppm_observed"] = soil_state["nitrogen_ppm"]
            soil_state["phosphorus_ppm_observed"] = soil_state["phosphorus_ppm"]
            soil_state["potassium_ppm_observed"] = soil_state["potassium_ppm"]
            self._state["active_alerts"].append("Soil test completed.")
        elif action_type == "harvest_now":
            self._state["growth_stage"] = "harvest_ready"
        elif action_type == "sell_crop":
            revenue = (self._state["yield_potential_pct"] / 100.0) * \
                      crop_data["expected_yield_qtl_per_ha"] * \
                      self._state["market"]["price_per_qtl"]
            self._state["revenue_earned_inr"] = revenue
        elif action_type == "file_insurance_claim":
            unlock_step = self._state.get("_insurance_unlock_step", 999)
            close_step = self._state.get("_insurance_close_step", -1)
            current_step = self._state["step_number"]
            if unlock_step <= current_step <= close_step and not self._state.get("_insurance_filed"):
                self._state["_insurance_filed"] = True
                damage_pct = 100 - self._state["crop_health"]
                payout = min(5000, max(0, damage_pct * 50))
                self._state["revenue_earned_inr"] += payout
                self._state["active_alerts"].append(f"Insurance claim approved.")
            else:
                self._state["active_alerts"].append("Insurance claim rejected.")
        
        if self._state["step_number"] > 0:
            events = self._state.get("_critical_event_steps", {})
            for step_idx, event_type in events.items():
                if self.grader._is_response_to_event(action_type, event_type, self._state):
                    self._state["_critical_responded"][event_type] = True

    def _check_scenario_events(self) -> None:
        events = self._state.get("_season_events", {})
        current_step = self._state["step_number"]
        if current_step in events:
            event_data = events[current_step]
            if "alerts" in event_data:
                self._state["active_alerts"].extend(event_data["alerts"])
            if "pest_pressure" in event_data and "pest_state" in self._state:
                self._state["pest_state"]["pressure"] = event_data["pest_pressure"]
            if "pest_update" in event_data and "pest_state" in self._state:
                self._state["pest_state"].update(event_data["pest_update"])
            if "crop_health_penalty" in event_data:
                self._state["crop_health"] -= event_data["crop_health_penalty"]
            if "weather_override" in event_data:
                self._state["weather"].update(event_data["weather_override"])
            if "soil_moisture_boost" in event_data:
                self._state["soil"]["moisture"] = min(1.0, self._state["soil"]["moisture"] + event_data["soil_moisture_boost"])
            if "market_spike_pct" in event_data:
                self._state["market"]["price_per_qtl"] *= (1.0 + event_data["market_spike_pct"])

    def _advance_growth_stage(self) -> None:
        schedule = self._state.get("_growth_schedule")
        if schedule:
            current_step = self._state["step_number"]
            if current_step in schedule:
                new_stage = schedule[current_step]
                if new_stage != self._state["growth_stage"]:
                    self._state["growth_stage"] = new_stage
                    self._state["active_alerts"].append(f"Crop entered {new_stage} stage.")

    def _check_done(self) -> Tuple[bool, Optional[str]]:
        if self._state["step_number"] >= self._state["max_steps"]:
            return True, "max_steps_reached"
        if self._state["crop_health"] <= 0:
            return True, "crop_dead"
        if self._state["budget_inr"] < 0:
            return True, "budget_exhausted"
        
        last_action = self._state["previous_actions"][-1] if self._state["previous_actions"] else ""
        if last_action == "sell_crop":
            return True, "harvest_complete"
        if last_action == "harvest_now" and self._state["growth_stage"] == "harvest_ready":
            return True, "harvest_complete"
        return False, None

    def _build_info_dict(self, done: bool, reason: str | None) -> dict:
        step_breakdown = self._state.get("_last_step_breakdown", {})
        profit_loss = self._state["revenue_earned_inr"] - self._state["total_spent_inr"]
        
        info_dict = {
            "step_breakdown": step_breakdown,
            "crop_health_pct": round(self._state["crop_health"], 1),
            "max_steps": self._state["max_steps"],
            "economics": {
                "total_spent_inr": round(self._state["total_spent_inr"], 2),
                "revenue_earned_inr": round(self._state["revenue_earned_inr"], 2),
                "profit_loss_inr": round(profit_loss, 2),
                "expected_max_profit": round(self._expected_max_profit, 2),
            }
        }
        if done:
            info_dict["reason"] = reason
        return info_dict

app = FastAPI(
    title="KisanEnv",
    version="1.0.0",
    description="Production RL Environment for Crop Advisory"
)
kisan_env = KisanEnv()

@app.get("/")
async def root():
    return {"status": "ok", "environment": "KisanEnv"}

@app.get("/tasks")
async def get_tasks():
    action_schema = {
        "action_type": "string",
        "target": "string",
        "dosage_or_amount": "float",
        "timing": "string",
        "reasoning": "string",
    }
    tasks_list = []
    for task_id, task_data in TASKS.items():
        tasks_list.append({
            "id": task_id,
            "name": task_data["name"],
            "difficulty": task_data["difficulty"],
            "max_steps": task_data["max_steps"],
            "action_schema": action_schema,
        })
    return {"tasks": tasks_list}

@app.post("/reset")
async def reset(req: Optional[ResetRequest] = None):
    try:
        task_id = req.task_id if req and req.task_id else "task_1_easy"
        observation = kisan_env.reset(task_id)
        return observation.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/step")
async def step(action: Action):
    try:
        observation, reward, done, info_dict = kisan_env.step(action)
        return {
            "observation": observation.model_dump(),
            "reward": reward,
            "done": done,
            "info": info_dict,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/state")
async def get_state():
    return kisan_env.state()

@app.post("/grader")
async def grade(req: GraderRequest):
    grader = KisanGrader()
    result = grader.grade_task(req.task_id, req.history)
    return result

@app.post("/baseline")
async def run_baseline():
    api_key = os.getenv("OPENAI_API_KEY", "")
    try:
        env_vars = {**os.environ}
        if api_key:
            env_vars["OPENAI_API_KEY"] = api_key
            
        result = subprocess.run(
            [sys.executable, "run.py", "--heuristic-only" if not api_key else ""],
            capture_output=True,
            text=True,
            timeout=300,
            env=env_vars,
        )
        lines = result.stdout.strip().split("\n")
        scores = {}
        for line in lines:
            for task_id in TASKS:
                if task_id in line:
                    parts = line.strip().split()
                    try:
                        scores[task_id] = float(parts[-1])
                    except (ValueError, IndexError):
                        pass
        return scores if scores else {"stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
