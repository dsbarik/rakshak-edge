# 🛡️ Rakshak Edge

**Agentic disaster message triage: parse, verify, and prioritize emergency SMS from the field.**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.9-7C3AED?logo=langchain&logoColor=white)](https://www.langchain.com/langgraph)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![](https://img.shields.io/badge/status-production--ready-22c55e)

---

## 💡 What It Does

During disasters, aid organizations get thousands of unstructured SMS messages. Human triage doesn't scale.

Rakshak Edge turns raw messages into structured triage data. It identifies hazards (earthquake, flood, storm), resources needed (food, water, medical help), urgency levels, and message priority. Downstream logistics systems can then act immediately.

It runs as a LangGraph state machine with an LLM-as-judge verification loop that catches hallucinations before they reach operations.

> _"We are dying of hunger and thirst, please send help."_
> _"People are trapped under collapsed buildings after the earthquake."_
> _"The hospital has no power and we need generators."_

---

## ✨ Example

| Input                                                                  | Output                                                                                                                                                                                                                          |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| _"People are trapped under collapsed buildings after the earthquake."_ | `{"intent": "REQUEST", "hazards": [{"type": "EARTHQUAKE", "severity": 4}, {"type": "STRUCTURAL_DAMAGE", "severity": 4}], "resources": [{"type": "SEARCH_AND_RESCUE", "severity": 4}, {"type": "MEDICAL_HELP", "severity": 4}]}` |
| _"We are dying of hunger and thirst, please send help."_               | `{"intent": "REQUEST", "hazards": [], "resources": [{"type": "WATER", "severity": 4}, {"type": "FOOD", "severity": 4}]}`                                                                                                        |
| _"We have two trucks available to transport supplies."_                | `{"intent": "OFFER", "hazards": [], "resources": [{"type": "TRANSPORT", "severity": 2}]}`                                                                                                                                       |

---

## 🏗️ Architecture

```
                      ┌──────────────┐
                      │   MESSAGE    │
                      │  (raw SMS)   │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
              ┌──────▶│    PARSE     │
              │       │  (classify   │
              │       │   + extract) │
              │       └──────┬───────┘
              │              │
              │              ▼
              │       ┌──────────────┐
         ┌────┴───────┤   VERIFY     │
         │   RETRY    │  (QA gate)   │
         │  (max 3×)  └──────┬───────┘
         └───────────────────┘      │
                      ┌──────────────┐
                      │  PRIORITIZE  │
                      │  (intent +   │
                      │   severity)  │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │   OUTPUT     │
                      │  (structured │
                      │   triage)    │
                      └──────────────┘
```

### Pipeline Nodes

| Node           | Responsibility                                                                                                                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Parse**      | Classifies intent (`REQUEST` / `OFFER` / `OTHER`). Extracts hazards (`EARTHQUAKE`, `FLOOD`, `FIRE`) and resources (`FOOD`, `WATER`, `MEDICAL_HELP`) with severity levels (1-4).                   |
| **Verify**     | LLM-as-judge QA gate. Checks for contradictions, wrong intent, spurious categories, and hazard/resource confusion. Designed to be conservative: only flag clear errors to avoid false rejections. |
| **Retry**      | Loops back to Parse when verification fails. Keeps accumulated context. Configurable max attempts prevents infinite waste.                                                                        |
| **Prioritize** | Computes overall priority (`LOW` / `HIGH` / `CRITICAL`) from intent + max severity.                                                                                                               |

### Key Design Decisions

| Decision                         | Rationale                                                                                                                                          |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **LangGraph over raw LangChain** | State machine models the parse -> verify -> retry loop. Gives explicit state transitions and history tracking.                                     |
| **LLM-as-judge verification**    | Lightweight QA gate catches contradictions before they reach downstream systems. No human-in-the-loop needed.                                      |
| **Conservative verifier**        | Earlier versions wasted ~80% of retries by demanding severity upgrades for food/water mentions. Current verifier only flags direct contradictions. |
| **Config-driven model swapping** | All model parameters live in one YAML file. Swap from `phi4-mini` to `gemma4` to `minimax-m3` without touching pipeline code.                      |

---

## 🔬 Evaluation

Every prompt change is tested against a golden reference dataset with structured metrics. No gut feel.

### Golden Dataset

- **50 real SMS messages** from the 2010 Haiti earthquake. Includes requests, offers, and updates across English, Creole, and mixed-language texts with truncation and noise.
- **Reference annotations** generated by `minimax-m3:cloud` (428B parameter model). Uses an identical prompt template to the pipeline. This ensures we measure model capability, not prompt mismatch.
- Gold standard is **provider-agnostic**. Can be regenerated from Gemini 3.1 Pro, GPT-5, or any stronger model by changing one line in `generate_golden.py`.

### Metrics

```
                  ┌─────────────────────────────────┐
                  │       Pipeline Output           │
                  │  (gemma4:cloud, phi4-mini, etc.)│
                  └────────────┬────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────────────┐
                  │       Comparison Engine         │
                  │  . Exact match (strict equality)│
                  │  . Subset match (pipeline in ref)│
                  │  . Per-category TP/FP/FN/P/R    │
                  └────────────┬────────────────────┘
                               │
                               ▼
                  ┌─────────────────────────────────┐
                  │      Golden Reference           │
                  │  (minimax-m3:cloud annotations) │
                  └─────────────────────────────────┘
```

Exact match is too harsh for multi-label extraction. Predicting `[FOOD, WATER]` when golden has `[FOOD, WATER, SHELTER]` is partially correct. Subset matching (`pipeline in reference`) separates precision from recall and gives a more honest picture.

---

## 📊 Results

Pipeline: `gemma4:cloud` (20B) | Golden: `minimax-m3:cloud` (428B) | Samples: 50

### Overall

| Metric   | Intent    | Hazards   | Resources |
| -------- | --------- | --------- | --------- |
| Accuracy | **88.0%** | **98.0%** | **90.0%** |

### Per-Category Breakdown

#### Resources

| Category           | Precision | Recall | Samples |
| ------------------ | --------- | ------ | ------- |
| FOOD               | 100.0%    | 96.2%  | 26      |
| WATER              | 100.0%    | 94.7%  | 19      |
| MEDICAL_HELP       | 90.9%     | 100.0% | 11      |
| SHELTER            | 100.0%    | 83.3%  | 6       |
| SEARCH_AND_RESCUE  | 50.0%     | 100.0% | 4       |
| CLOTHING           | 100.0%    | 100.0% | 1       |
| ELECTRICITY        | 100.0%    | 100.0% | 1       |
| TRANSPORT          | 50.0%     | 100.0% | 2       |
| SECURITY_PERSONNEL | 100.0%    | 100.0% | 1       |

#### Hazards

| Category              | Precision | Recall | Samples |
| --------------------- | --------- | ------ | ------- |
| EARTHQUAKE            | 100.0%    | 100.0% | 1       |
| SECURITY_THREAT       | 100.0%    | 100.0% | 2       |
| STRUCTURAL_DAMAGE     | 100.0%    | 100.0% | 1       |
| COMMUNICATION_FAILURE | 75.0%     | 100.0% | 4       |

### Verification Efficiency

| Metric                           | Value                          |
| -------------------------------- | ------------------------------ |
| Avg retries per message          | **0.24**                       |
| Retries exhausted (max 3)        | 4 / 50                         |
| Reduction from previous verifier | **~80% fewer wasted attempts** |

---

## 🧪 Prompt Optimization: A Case Study

The most impactful optimization came from treating prompts as testable hypotheses.

**Problem**: The model hallucinated `HEALTH_CRISIS` as a hazard in every message mentioning hunger, thirst, or injury. This caused 48% false negatives on resource extraction for those cases.

**Root Cause**: `HEALTH_CRISIS` was dual-classified as both a hazard and implicitly referenced by resource needs (food, water, medical help). The model learned to use it as a catch-all.

**Fix**: Removed `HEALTH_CRISIS` from the hazard ontology entirely. Added explicit instruction:

> _"Hunger, thirst, injury, illness, and dying people are NOT hazards. These are consequences that should be reflected in resource needs."_

**Validation**: Ran the full comparison engine before deploying. Hazard accuracy went from marginal to 98%. Resource accuracy stabilized at 90%. Retries dropped by 80%. All numbers measured against the golden dataset.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- [Ollama](https://ollama.com/) with a model pulled (e.g., `gemma4:cloud` or `phi4-mini`)

### Setup

```bash
# Clone
git clone https://github.com/your-username/rakshak-edge
cd rakshak-edge

# Install dependencies
uv sync

# Set your Ollama API key
echo "OLLAMA_API_KEY=your-key-here" > .env
```

### Usage

```bash
# Triage a single message
uv run python -m rakshak_edge "Need food and water, we are stranded after the storm"

# Triage a batch of messages
uv run python -m rakshak_edge --batch data/structured/disaster_response_messages_validation.json

# Generate golden annotations (reference labels)
uv run python scripts/generate_golden.py

# Compare pipeline output against golden dataset
uv run python scripts/compare_golden.py

# Explore the raw dataset
uv run python scripts/dataset_analysis.py
```

### Configuration

```yaml
# configs/base.yaml
llm:
  model_name: "gemma4:cloud" # swap models here
  temperature: 0.0
  use_auth: true

nodes:
  max_retries: 3 # verify -> retry loop cap
```

---

## 📁 Project Structure

```
rakshak-edge/
├── src/rakshak_edge/         # Core pipeline
│   ├── graph.py              # LangGraph state machine
│   ├── nodes.py              # Parse -> Verify -> Retry -> Prioritize
│   ├── prompts.py            # System prompts (triage + verification)
│   ├── schema.py             # Pydantic models
│   ├── state.py              # Graph state definition
│   ├── config.py             # YAML config loader
│   ├── llm.py                # Ollama + cloud LLM client
│   └── main.py               # CLI entry point
├── scripts/                  # Evaluation & data tools
│   ├── generate_golden.py    # Golden annotation generation
│   ├── compare_golden.py     # Golden vs. pipeline comparison engine
│   ├── prepare_datasets.py   # CSV -> JSON preprocessing
│   └── dataset_analysis.py   # Dataset exploration
├── data/
│   ├── raw/                  # Original CSV data
│   ├── structured/           # Preprocessed JSON
│   └── golden/               # Golden annotations + comparison reports
├── configs/
│   └── base.yaml             # Model + node configuration
└── pyproject.toml
```

---

## 🛠️ Built With

- **Python 3.12** + [uv](https://docs.astral.sh/uv/) for fast dependency management
- **[LangGraph](https://www.langchain.com/langgraph)** for state machine orchestration
- **[LangChain](https://www.langchain.com/)** for LLM integration and prompt templating
- **[Pydantic](https://docs.pydantic.dev/)** for structured output parsing
- **[Ollama](https://ollama.com/)** for local LLM inference
- **[Rich](https://rich.readthedocs.io/)** for CLI output formatting

---

## 📄 License

MIT [Dibya S. Barik](mailto:barikdibyasamapd@gmail.com)
