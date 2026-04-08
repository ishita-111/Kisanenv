import os
import json
import requests
from openai import OpenAI

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o")
HF_TOKEN = os.environ.get("HF_TOKEN")
BENCHMARK = "KisanEnv"

ENV_BASE_URL = os.environ.get("KISAN_ENV_URL", "http://localhost:7860")

SYSTEM_PROMPT = """You are an expert agronomist advising farmers in India.
Max budget is limited. Optimize the 8-component reward.
Consider timing (morning/evening) and dosage carefully.

Respond ONLY with valid JSON:
{
  "action_type": "spray_pesticide|spray_fungicide|apply_fertilizer|irrigate|harvest_now|wait_observe|sell_crop|request_soil_test|consult_market|file_insurance_claim",
  "target": "pest/nutrient name or empty",
  "dosage_or_amount": float,
  "timing": "immediate|morning|evening",
  "reasoning": "Detailed agronomic reasoning"
}"""

def run_inference():
    client = OpenAI(
        base_url=API_BASE_URL,
        api_key=HF_TOKEN
    )
    
    try:
        tasks_response = requests.get(f"{ENV_BASE_URL}/tasks").json()
        tasks = [task["id"] for task in tasks_response.get("tasks", [])]
    except Exception:
        tasks = ["task_1_easy", "task_2_medium", "task_3_hard"]
    
    for task_id in tasks:
        print(f"[START] task={task_id} env={BENCHMARK} model={MODEL_NAME}", flush=True)
        
        try:
            obs = requests.post(f"{ENV_BASE_URL}/reset", json={"task_id": task_id}).json()
        except requests.exceptions.ConnectionError:
            print(f"Error connecting to environment at {ENV_BASE_URL}.")
            break
            
        history = []
        rewards = []
        steps_taken = 0
        error_val = "null"
        
        for step in range(1, 31):
            steps_taken = step
            safe_obs = {k: v for k, v in obs.items() if k not in ['symptom_description']}
            safe_obs['symptom_description'] = obs.get('symptom_description', '')[:500]

            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": json.dumps(safe_obs)},
                    ],
                    response_format={"type": "json_object"},
                )
                action_text = response.choices[0].message.content
                action = json.loads(action_text)
                action_str = json.dumps(action)
            except Exception as e:
                action = {"action_type": "wait_observe", "reasoning": "Fallback"}
                action_str = json.dumps(action)
                error_val = str(e).replace('\n', ' ')

            result = requests.post(f"{ENV_BASE_URL}/step", json=action).json()
            history.append(result)
            
            reward = result.get("reward", 0.0)
            done = result.get("done", False)
            done_val = str(done).lower()
            rewards.append(reward)
            
            print(f"[STEP] step={step} action={action_str} reward={reward:.2f} done={done_val} error={error_val}", flush=True)
            
            if done:
                break
            obs = result.get("observation", {})

        score_resp = requests.post(
            f"{ENV_BASE_URL}/grader",
            json={"task_id": task_id, "history": history}
        ).json()
        
        score = score_resp.get("score", 0.0)
        success = score > 0.0
        success_val = str(success).lower()
        rewards_str = ",".join(f"{r:.2f}" for r in rewards)
        
        print(f"[END] success={success_val} steps={steps_taken} score={score:.3f} rewards={rewards_str}", flush=True)

if __name__ == "__main__":
    if HF_TOKEN is None:
        pass
    run_inference()
