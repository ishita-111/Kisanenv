from __future__ import annotations
from typing import Any

from dynamics import (
    OPTIMAL_DOSAGE, OPTIMAL_TIMING,
    compute_dosage_score, compute_timing_score,
)

CORRECT_ACTIONS: dict[str, dict[str, float]] = {
    "rust_vs_deficiency": {
        "spray_fungicide": 0.40,
        "request_soil_test": 0.15,
        "wait_observe": 0.05,
        "spray_pesticide": -0.20,
        "apply_fertilizer": -0.25,
    },
    "full_season_bollworm": {
        "spray_pesticide": 0.25,
        "apply_fertilizer": 0.15,
        "irrigate": 0.15,
        "wait_observe": 0.05,
        "harvest_now": 0.20,
        "sell_crop": 0.15,
        "request_soil_test": 0.08,
        "consult_market": 0.10,
        "spray_fungicide": -0.15,
    },
    "compound_crisis": {
        "spray_pesticide": 0.18,
        "irrigate": 0.15,
        "file_insurance_claim": 0.22,
        "sell_crop": 0.15,
        "harvest_now": 0.15,
        "consult_market": 0.10,
        "request_soil_test": 0.12,
        "spray_fungicide": 0.12,
        "apply_fertilizer": 0.05,
        "wait_observe": -0.08,
    },
}

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

class KisanGrader:
    def compute_step_reward(self, action_type: str, action_dict: dict,
                            state: dict) -> float:
        reward = 0.0
        breakdown = {}

        corr = self._action_correctness(action_type, state)
        reward += corr
        breakdown["correctness"] = round(corr, 4)

        timing = compute_timing_score(action_type, action_dict.get("timing", "immediate"))
        reward += timing
        breakdown["timing"] = round(timing, 4)

        dosage = compute_dosage_score(
            action_type, action_dict.get("dosage_or_amount", 0), state.get("crop_type", "wheat")
        )
        reward += dosage
        breakdown["dosage"] = round(dosage, 4)

        budget = self._budget_efficiency(action_dict, state)
        reward += budget
        breakdown["budget_efficiency"] = round(budget, 4)

        reasoning = self._reasoning_quality(action_dict)
        reward += reasoning
        breakdown["reasoning_quality"] = round(reasoning, 4)

        urgency = self._urgency_response(action_type, state)
        reward += urgency
        breakdown["urgency_response"] = round(urgency, 4)

        loop = self._loop_penalty(action_type, state)
        reward += loop
        breakdown["loop_penalty"] = round(loop, 4)

        waste = self._waste_penalty(action_type, state)
        reward += waste
        breakdown["waste_penalty"] = round(waste, 4)

        state["_last_step_breakdown"] = breakdown

        return float(max(-0.5, min(0.5, reward)))

    def compute_episode_score(self, episode_history: list[dict],
                              final_state: dict | None = None) -> float:
        if not episode_history:
            return 0.0

        last = episode_history[-1]
        info = last.get("info", {})

        crop_health = info.get("crop_health_pct", info.get("crop_health", 50)) / 100.0
        crop_health = max(0.0, min(1.0, crop_health))

        economic = self._economic_score(episode_history, info)

        correctness_vals = []
        for h in episode_history:
            bd = h.get("info", {}).get("step_breakdown", {})
            correctness_vals.append(bd.get("correctness", bd.get("correctness_signal", 0.0)))
        avg_correct = sum(correctness_vals) / max(1, len(correctness_vals))
        action_score = max(0, min(1, (avg_correct + 0.3) / 0.7))

        timing_vals = []
        dosage_vals = []
        for h in episode_history:
            bd = h.get("info", {}).get("step_breakdown", {})
            timing_vals.append(bd.get("timing", 0.0))
            dosage_vals.append(bd.get("dosage", 0.0))
        avg_timing = sum(timing_vals) / max(1, len(timing_vals))
        avg_dosage = sum(dosage_vals) / max(1, len(dosage_vals))
        td_score = max(0, min(1, (avg_timing + avg_dosage + 0.15) / 0.35))

        reasoning_vals = []
        for h in episode_history:
            bd = h.get("info", {}).get("step_breakdown", {})
            reasoning_vals.append(bd.get("reasoning_quality", 0.0))
        avg_reasoning = sum(reasoning_vals) / max(1, len(reasoning_vals))
        reasoning_score = max(0, min(1, avg_reasoning / 0.15))

        step_eff = self._step_efficiency(episode_history)

        final = (
            0.30 * crop_health
            + 0.25 * economic
            + 0.20 * action_score
            + 0.15 * td_score
            + 0.10 * reasoning_score
            + step_eff
        )

        return float(max(0.0, min(1.0, final)))

    def grade_task(self, task_id: str, episode_history: list[dict],
                   final_state: dict | None = None) -> dict:
        score = self.compute_episode_score(episode_history, final_state)
        return {
            "task_id": task_id,
            "score": round(score, 4),
            "breakdown": self._score_breakdown(episode_history),
        }

    def _action_correctness(self, action_type: str, state: dict) -> float:
        scenario = state.get("_scenario", "")
        rules = CORRECT_ACTIONS.get(scenario, {})
        base = rules.get(action_type, 0.0)

        growth_stage = state.get("growth_stage", "")
        pest = state.get("pest_state", {})

        if action_type == "harvest_now" and growth_stage == "harvest_ready":
            base += 0.10

        if (action_type == "spray_pesticide"
                and pest.get("pressure") in ("severe", "critical")):
            base += 0.12

        if (action_type == "spray_fungicide"
                and pest.get("disease_active", False)
                and pest.get("disease_severity", 0) > 10):
            base += 0.12

        if action_type == "file_insurance_claim" and scenario == "compound_crisis":
            step = state.get("step_number", 0)
            unlock = state.get("_insurance_unlock_step", 8)
            close = state.get("_insurance_close_step", 12)
            if unlock <= step <= close:
                base += 0.10
            elif step < unlock:
                base = -0.20
            else:
                base = -0.15

        if action_type == "apply_fertilizer":
            soil = state.get("soil", {})
            n_low = soil.get("nitrogen_ppm", 50) < 25
            p_low = soil.get("phosphorus_ppm", 20) < 10
            if n_low or p_low:
                base += 0.10

        if action_type == "irrigate":
            moisture = state.get("soil", {}).get("moisture", 0.5)
            if moisture < 0.20:
                base += 0.10

        return float(max(-0.30, min(0.45, base)))

    def _budget_efficiency(self, action_dict: dict, state: dict) -> float:
        budget = state.get("budget_inr", 0)
        initial = state.get("_initial_budget", budget)
        if initial <= 0:
            return 0.0
        used_frac = 1.0 - (budget / initial)
        if used_frac <= 0.50:
            return 0.06
        elif used_frac <= 0.70:
            return 0.03
        elif used_frac <= 0.90:
            return 0.0
        return -0.05

    def _reasoning_quality(self, action_dict: dict) -> float:
        reasoning = action_dict.get("reasoning", "")
        if not reasoning or len(reasoning.strip()) < 10:
            return 0.0
        length = len(reasoning.strip())
        if length >= 150:
            return 0.15
        elif length >= 80:
            return 0.10
        elif length >= 30:
            return 0.05
        return 0.02

    def _urgency_response(self, action_type: str, state: dict) -> float:
        critical_events = state.get("_critical_event_steps", {})
        responded = state.get("_critical_responded", {})
        step = state.get("step_number", 0)

        total = 0.0
        for event_step_str, event_type in critical_events.items():
            event_step = int(event_step_str) if isinstance(event_step_str, str) else event_step_str
            if event_step <= step and event_type not in responded:
                delay = step - event_step
                is_response = self._is_response_to_event(action_type, event_type, state)
                if is_response:
                    if delay <= 1:
                        total += 0.10
                    elif delay <= 2:
                        total += 0.05
                    else:
                        total -= 0.05
                elif delay > 2:
                    total -= 0.08

        return float(max(-0.15, min(0.10, total)))

    def _is_response_to_event(self, action_type: str, event_type: str,
                              state: dict) -> bool:
        responses = {
            "diagnosis_needed": {"request_soil_test", "spray_fungicide", "spray_pesticide"},
            "bollworm_outbreak": {"spray_pesticide"},
            "compound_crisis_start": {"spray_pesticide", "irrigate", "request_soil_test"},
            "insurance_window": {"file_insurance_claim"},
            "market_spike": {"sell_crop", "harvest_now"},
        }
        return action_type in responses.get(event_type, set())

    def _loop_penalty(self, action_type: str, state: dict) -> float:
        recent = state.get("previous_actions", [])
        if len(recent) >= 3 and all(a == action_type for a in recent[-3:]):
            return -0.15
        if len(recent) >= 2 and all(a == action_type for a in recent[-2:]):
            return -0.05
        return 0.0

    def _waste_penalty(self, action_type: str, state: dict) -> float:
        penalty = 0.0
        weather = state.get("weather", {})
        soil = state.get("soil", {})
        pest = state.get("pest_state", {})

        if action_type == "irrigate":
            forecast = weather.get("forecast", [])
            rain_coming = any(f.get("rain_mm", 0) > 15 for f in forecast[:2])
            if rain_coming or weather.get("rainfall_today_mm", 0) > 20:
                penalty -= 0.10
            if soil.get("moisture", 0) > 0.75:
                penalty -= 0.08

        if action_type == "spray_pesticide" and pest.get("pressure") == "none":
            scenario = state.get("_scenario", "")
            if scenario != "rust_vs_deficiency":
                penalty -= 0.10

        if action_type == "spray_fungicide" and not pest.get("disease_active", False):
            scenario = state.get("_scenario", "")
            if scenario != "rust_vs_deficiency":
                penalty -= 0.08

        if action_type == "apply_fertilizer":
            n = soil.get("nitrogen_ppm", 0)
            if n > 80:
                penalty -= 0.10
            recent = state.get("previous_actions", [])[-2:]
            if "apply_fertilizer" in recent:
                penalty -= 0.08

        if action_type in ("spray_pesticide", "spray_fungicide"):
            if weather.get("wind_speed_kmh", 0) > 25:
                penalty -= 0.05

        return float(penalty)

    def _economic_score(self, episode_history: list[dict],
                        final_info: dict) -> float:
        economics = final_info.get("economics", {})
        profit = economics.get("profit_loss_inr", 0)
        expected_max = economics.get("expected_max_profit", 10000)

        if expected_max <= 0:
            return 0.5

        ratio = profit / expected_max
        return float(max(0.0, min(1.0, (ratio + 1.0) / 2.0)))

    def _step_efficiency(self, episode_history: list[dict]) -> float:
        if not episode_history:
            return 0.0
        last = episode_history[-1]
        info = last.get("info", {})
        max_steps = info.get("max_steps", 20)
        steps_used = len(episode_history)
        if steps_used < max_steps and last.get("done"):
            efficiency = 1.0 - (steps_used / max_steps)
            return min(0.05, 0.05 * efficiency)
        return 0.0

    def _score_breakdown(self, episode_history: list[dict]) -> dict:
        if not episode_history:
            return {"final_score": 0.0}

        last = episode_history[-1]
        info = last.get("info", {})

        totals = {
            "correctness": 0.0, "timing": 0.0, "dosage": 0.0,
            "budget_efficiency": 0.0, "reasoning_quality": 0.0,
            "urgency_response": 0.0, "loop_penalty": 0.0, "waste_penalty": 0.0,
        }
        for h in episode_history:
            bd = h.get("info", {}).get("step_breakdown", {})
            for key in totals:
                totals[key] += bd.get(key, 0.0)

        total_reward = sum(h.get("reward", 0.0) for h in episode_history)
        steps = len(episode_history)

        return {
            "steps_taken": steps,
            "total_step_rewards": round(total_reward, 4),
            "avg_reward_per_step": round(total_reward / max(1, steps), 4),
            "components": {k: round(v, 4) for k, v in totals.items()},
            "crop_health_final": info.get("crop_health_pct", 0),
            "economic_outcome": info.get("economics", {}),
            "final_score": round(
                self.compute_episode_score(episode_history), 4
            ),
        }
