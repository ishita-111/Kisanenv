---
title: KisanEnv
emoji: 🌍
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
license: mit
short_description: A Production-Grade Agricultural Decision-Making Simulator
---

## 🌾 KisanEnv

A simulation environment for evaluating multi-step decision-making in agriculture under uncertainty.

---

## Overview

KisanEnv is designed to test how well an agent (rule-based or AI) can make decisions in realistic agricultural scenarios.

Unlike traditional benchmarks that focus on single-step predictions, KisanEnv evaluates **sequential decision-making**, where each action affects future outcomes. The environment simulates real-world farming conditions such as uncertain symptoms, changing weather, limited budgets, and delayed consequences.

Agents interact with the environment through a structured API and must continuously observe, reason, and act.

---

## Motivation

Agricultural decision-making is inherently complex:

* The same symptom can have multiple causes
* Information is often incomplete or noisy
* Actions incur costs and may have delayed effects
* Environmental conditions change over time

KisanEnv captures these challenges to evaluate whether an agent can:

* reason under uncertainty
* make cost-aware decisions
* adapt across multiple steps
* maintain consistent performance over time

---

## Environment Design

KisanEnv follows a step-based interaction loop:

1. The agent receives the current state
2. The agent selects an action
3. The environment updates based on the action
4. The agent receives feedback (new state + reward)
5. The process repeats until termination

This setup models real-world sequential decision-making rather than isolated predictions.

---

## Observation Space

At each step, the agent receives a structured observation representing the current farm state:

```json id="obs123"
{
  "crop_type": "wheat",
  "growth_stage": "vegetative",
  "symptom_description": "Yellowing leaves on lower canopy",
  "weather": {...},
  "soil": {...},
  "budget_remaining_inr": 5000,
  "yield_estimate_pct": 84.5
}
```

### Key characteristics:

* Observations may be **incomplete or noisy**
* Multiple conditions can produce similar symptoms
* The agent must infer the underlying issue before acting

---

## Action Space

Agents must respond with structured actions:

```json id="act123"
{
  "action_type": "apply_fertilizer",
  "dosage_or_amount": 2.0,
  "timing": "morning",
  "reasoning": "Symptoms suggest nitrogen deficiency"
}
```

### Action components:

* **action_type**: type of intervention (e.g., irrigation, pesticide, fertilizer)
* **dosage_or_amount**: quantity applied
* **timing**: when the action is executed
* **reasoning**: explanation for the decision

The reasoning field enables evaluation of both correctness and decision quality.

---

## Tasks and Difficulty Levels

KisanEnv includes multiple scenarios with increasing complexity:

### Task 1 — Easy

* Single issue
* Relatively clear signals
* Short decision horizon

### Task 2 — Medium

* Multi-step decision-making
* Changing environmental conditions
* Budget trade-offs

### Task 3 — Hard

* Multiple simultaneous issues
* Ambiguous signals
* Complex trade-offs and prioritization

Difficulty increases through:

* higher uncertainty
* longer time horizons
* competing constraints

---

## Reward and Evaluation

Agents are evaluated across multiple dimensions:

* Diagnostic accuracy
* Correctness of action
* Timing of intervention
* Resource efficiency (budget usage)
* Adaptability to changing conditions
* Quality of reasoning

The scoring system provides **partial credit**, allowing nuanced evaluation rather than binary success/failure.

---

## Example Scenario

**Observation:**

* Yellowing leaves
* Low nitrogen levels
* Humid weather

**Correct action:**
→ Apply fertilizer

**Incorrect action:**
→ Apply fungicide

**Impact:**

* Correct decisions improve yield and reward
* Incorrect decisions waste resources and reduce score

---

## Running the Environment

### Local Setup

```bash id="run1"
pip install -r requirements.txt
uvicorn env:app --host 0.0.0.0 --port 7860
```

---

### Docker Setup

```bash id="run2"
docker build -t kisanenv .
docker run -p 7860:7860 kisanenv
```

---

## API Usage

Once running, open:

```
http://localhost:7860/docs
```

### Basic workflow:

1. Call `/tasks` → view available scenarios
2. Call `/reset`:

```json id="api1"
{ "task_id": "task_1_easy" }
```

3. Call `/step` with an action

This enables interactive testing without building an agent.

---

## Agent Evaluation

### Heuristic Agent (Baseline)

A deterministic rule-based agent for validation:

```bash id="agent1"
python run.py --heuristic-only
```

---

### LLM-Based Agent

Runs the environment using a language model:

```bash id="agent2"
export HF_TOKEN="hf_..."
export MODEL_NAME="gpt-4o"
python inference.py
```

The model:

* interprets the environment state
* generates reasoning
* selects actions iteratively

---

## Baseline Performance

Approximate scores from the heuristic agent:

* Task 1 (Easy): ~0.62
* Task 2 (Medium): ~0.37
* Task 3 (Hard): ~0.40

These results demonstrate:

* Increasing difficulty across tasks
* Non-trivial decision requirements
* Meaningful evaluation signals

---

## Project Structure

```bash id="struct"
.
├── env.py             # FastAPI environment (API endpoints)
├── dynamics.py        # Simulation logic and state transitions
├── tasks.py           # Scenario definitions
├── grader.py          # Reward and evaluation logic
├── run.py             # Agent runner (heuristic agent baseline)
├── inference.py       # Official OpenEnv LLM-based evaluation script
├── openenv.yaml       # OpenEnv specification configuration
├── test_endpoints.py  # API testing
├── requirements.txt   # Dependencies
├── Dockerfile         # Container setup
└── README.md
```

---

## Summary

KisanEnv is a structured environment for evaluating how well agents perform in **dynamic, uncertain, multi-step decision problems**.

It moves beyond simple prediction tasks and focuses on:

* reasoning
* adaptability
* cost-awareness
* long-term decision quality

The core question it answers:

**Can an AI system make effective decisions over time in realistic, uncertain conditions?**