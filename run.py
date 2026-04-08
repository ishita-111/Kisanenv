import os
import sys
import json
import requests
import argparse
from typing import Dict, Any

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

BASE_URL = os.getenv("KISAN_ENV_URL", "http://localhost:8000")

def heuristic_agent_step(obs: Dict[str, Any]) -> dict:
    task = obs["task_id"]
    step = obs["step_number"]
    soil = obs["soil"]
    pest = obs["pest_probability_observed"]
    weather = obs["weather"]

    if task == "task_1_easy":
        if step == 0:
            return {"action_type": "request_soil_test", "timing": "immediate", "reasoning": "Need to confirm NPK before spraying"}
        elif step == 1:
            if soil["nitrogen_ppm_observed"] > 30:
                return {"action_type": "spray_fungicide", "timing": "morning", "reasoning": "Not a deficiency, treating rust"}
            else:
                return {"action_type": "apply_fertilizer", "target": "nitrogen", "dosage_or_amount": 3.0, "timing": "morning", "reasoning": "Treating deficiency"}
        else:
            return {"action_type": "wait_observe", "timing": "immediate", "reasoning": "Waiting for treatment effect"}

    elif task == "task_2_medium":
        alerts = str(obs["active_alerts"])
        if "Bollworm outbreak" in alerts:
            return {"action_type": "spray_pesticide", "target": "bollworm", "dosage_or_amount": 3.0, "timing": "morning", "reasoning": "Responding to outbreak"}
        if soil["moisture"] < 0.25 and weather["rainfall_today_mm"] == 0:
            return {"action_type": "irrigate", "dosage_or_amount": 30.0, "timing": "evening", "reasoning": "Soil is dry"}
        if soil["nitrogen_ppm_observed"] < 25:
            return {"action_type": "apply_fertilizer", "dosage_or_amount": 4.0, "timing": "morning", "reasoning": "Low nitrogen"}
        if obs["market_trend_observed"] == "rising" and obs["growth_stage"] == "harvest_ready":
            return {"action_type": "harvest_now", "timing": "morning", "reasoning": "Capitalizing on market spike"}
        if obs["previous_actions"] and obs["previous_actions"][-1] == "harvest_now":
            return {"action_type": "sell_crop", "timing": "immediate", "reasoning": "Selling harvested crop"}
        return {"action_type": "wait_observe", "timing": "immediate", "reasoning": "Monitoring"}

    elif task == "task_3_hard":
        alerts = str(obs["active_alerts"])
        if "Insurance claim window OPEN" in alerts:
            return {"action_type": "file_insurance_claim", "timing": "immediate", "reasoning": "Filing claim due to severe damage"}
        if pest > 0.6:
            return {"action_type": "spray_pesticide", "target": "locust", "dosage_or_amount": 2.5, "timing": "morning", "reasoning": "High pest pressure"}
        if soil["moisture"] < 0.20:
            return {"action_type": "irrigate", "dosage_or_amount": 25.0, "timing": "evening", "reasoning": "Severe drought"}
        if obs["growth_stage"] == "harvest_ready":
            return {"action_type": "harvest_now", "timing": "morning", "reasoning": "Salvaging crop"}
        
        return {"action_type": "wait_observe", "timing": "immediate", "reasoning": "Overwhelmed, waiting"}

    return {"action_type": "wait_observe", "timing": "immediate", "reasoning": "Fallback"}


def run_heuristic_episode(task_id: str) -> float:
    obs = requests.post(f"{BASE_URL}/reset", json={"task_id": task_id}).json()
    history = []

    for _ in range(20):
        action = heuristic_agent_step(obs)
        result = requests.post(f"{BASE_URL}/step", json=action).json()
        history.append(result)

        if result["done"]:
            break
        obs = result["observation"]

    score_resp = requests.post(
        f"{BASE_URL}/grader",
        json={"task_id": task_id, "history": history}
    ).json()

    return score_resp["score"]


SYSTEM_PROMPT = """You are an expert agronomist advising farmers in India.
Max budget is limited. Optimize the 8-component reward.
Consider timing (morning/evening) and dosage carefully.

Respond ONLY with valid JSON:
{
  "action_type": "spray_pesticide|spray_fungicide|apply_fertilizer|irrigate|harvest_now|wait_observe|sell_crop|request_soil_test|consult_market|file_insurance_claim",
  "target": "pest/nutrient name or empty",
  "dosage_or_amount": float,
  "timing": "immediate|morning|evening",
  "reasoning": "Detailed agronomic reasoning (at least 50 words)"
}"""

def run_llm_episode(task_id: str, client: Any) -> float:
    obs = requests.post(f"{BASE_URL}/reset", json={"task_id": task_id}).json()
    history = []

    for _ in range(30):
        safe_obs = {k: v for k, v in obs.items() if k not in ['symptom_description']}
        safe_obs['symptom_description'] = obs.get('symptom_description', '')[:500]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": json.dumps(safe_obs)},
            ],
            response_format={"type": "json_object"},
        )
        action = json.loads(response.choices[0].message.content)

        result = requests.post(f"{BASE_URL}/step", json=action).json()
        history.append(result)

        if result["done"]:
            break
        obs = result["observation"]

    score_resp = requests.post(
        f"{BASE_URL}/grader",
        json={"task_id": task_id, "history": history}
    ).json()

    return score_resp["score"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run KisanEnv Baseline Agents")
    parser.add_argument("--heuristic-only", action="store_true", help="Only run heuristic agent")
    args = parser.parse_args()

    results_heu = {}
    print("--- Running Rule-Based Heuristic Agent ---")
    for task in ["task_1_easy", "task_2_medium", "task_3_hard"]:
        print(f"Running {task}...", end=" ", flush=True)
        score = run_heuristic_episode(task)
        results_heu[task] = score
        print(f"{score:.3f}")

    if not args.heuristic_only and HAS_OPENAI and "OPENAI_API_KEY" in os.environ:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        results_llm = {}
        print("\n--- Running GPT-4o Agent ---")
        for task in ["task_1_easy", "task_2_medium", "task_3_hard"]:
            print(f"Running {task}...", end=" ", flush=True)
            score = run_llm_episode(task, client)
            results_llm[task] = score
            print(f"{score:.3f}")

        print("\n--- Final Comparison ---")
        print(f"{'Task':<20} | {'Heuristic':<10} | {'GPT-4o':<10}")
        print("-" * 46)
        for task in results_heu:
            print(f"{task:<20} | {results_heu[task]:.3f}      | {results_llm.get(task, 0):.3f}")
    else:
        print("\nTo run the LLM baseline, set OPENAI_API_KEY and install openai.")
