import requests, json

BASE = "http://localhost:7860"

print("=== GET /tasks ===")
r = requests.get(f"{BASE}/tasks")
assert r.status_code == 200
tasks = r.json()
print(f"  Found {len(tasks['tasks'])} tasks: {[t['id'] for t in tasks['tasks']]}")

print("\n=== POST /reset (task_1_easy) ===")
r = requests.post(f"{BASE}/reset", json={"task_id": "task_1_easy"})
assert r.status_code == 200
obs = r.json()
print(f"  crop_type={obs['crop_type']}, stage={obs['growth_stage']}, step={obs['step_number']}")

print("\n=== POST /step (request_soil_test) ===")
r = requests.post(f"{BASE}/step", json={
    "action_type": "request_soil_test",
    "target": "soil",
    "dosage_or_amount": 0,
    "timing": "immediate",
    "reasoning": "Testing soil nitrogen levels to rule out deficiency"
})
assert r.status_code == 200
result = r.json()
print(f"  reward={result['reward']}, done={result['done']}")
print(f"  symptom: {result['observation']['symptom_description'][:80]}...")

print("\n=== POST /step (spray_fungicide - correct) ===")
r = requests.post(f"{BASE}/step", json={
    "action_type": "spray_fungicide",
    "target": "rust_fungus",
    "dosage_or_amount": 2.5,
    "timing": "morning",
    "reasoning": "Soil test showed normal nitrogen. Brown pustules indicate wheat rust."
})
assert r.status_code == 200
result = r.json()
print(f"  reward={result['reward']}, done={result['done']}")
print(f"  crop_health={result['info']['crop_health_pct']}")

print("\n=== GET /state ===")
r = requests.get(f"{BASE}/state")
assert r.status_code == 200
state = r.json()
print(f"  task_id={state['task_id']}, cumulative_reward={state['cumulative_reward']}")

print("\n=== POST /grader ===")
r = requests.post(f"{BASE}/grader", json={
    "task_id": "task_1_easy",
    "history": state["episode_history"]
})
assert r.status_code == 200
grade = r.json()
print(f"  score={grade['score']}")
print(f"  breakdown={json.dumps(grade['breakdown'], indent=4)}")

print("\n=== Determinism Check ===")
obs1 = requests.post(f"{BASE}/reset", json={"task_id": "task_1_easy"}).json()
obs2 = requests.post(f"{BASE}/reset", json={"task_id": "task_1_easy"}).json()
assert obs1 == obs2, "FAILED: Same task_id should produce identical observations"
print("  PASSED: Same task_id produces identical initial observations")

print("\n=== Task 2 (cotton) reset ===")
obs = requests.post(f"{BASE}/reset", json={"task_id": "task_2_medium"}).json()
print(f"  crop={obs['crop_type']}, stage={obs['growth_stage']}, budget={obs['budget_remaining_inr']}")

print("\n=== Task 3 (soybean crisis) reset ===")
obs = requests.post(f"{BASE}/reset", json={"task_id": "task_3_hard"}).json()
print(f"  crop={obs['crop_type']}, stage={obs['growth_stage']}, pest={obs['pest_probability_observed']}")
print(f"  symptom: {obs['symptom_description'][:100]}...")

print("\n ALL ENDPOINT TESTS PASSED!")
