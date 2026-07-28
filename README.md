<div align="center">
  <h1>🛡️ Rakshak Edge</h1>
  <p><strong>Agentic disaster message triage: parse, verify, and prioritize emergency SMS from the field.</strong></p>

  <p>
    <a href="https://python.org">
      <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
    </a>
    <a href="https://www.langchain.com/langgraph">
      <img src="https://img.shields.io/badge/LangGraph-1.2.9-7C3AED?logo=langchain&logoColor=white" alt="LangGraph">
    </a>
    <a href="LICENSE">
      <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
    </a>
    <img src="https://img.shields.io/badge/status-production--ready-22c55e" alt="Status">
  </p>

  <br>

  <p>
    <a href="#-what-it-does">What It Does</a> •
    <a href="#-architecture">Architecture</a> •
    <a href="#-evaluation">Evaluation</a> •
    <a href="#-results">Results</a> •
    <a href="#%EF%B8%8F-api">API</a> •
    <a href="#-getting-started">Getting Started</a>
  </p>
</div>

<br>

---

## 💡 What It Does

During disasters, aid organizations get thousands of unstructured SMS messages. Human triage doesn't scale.

Rakshak Edge turns raw messages into structured triage data. It identifies hazards (earthquake, flood, storm), resources needed (food, water, medical help), urgency levels, and message priority. Downstream logistics systems can then act immediately.

It runs as a LangGraph state machine with an LLM-as-judge verification loop that catches hallucinations before they reach operations.

<br>

<table>
  <tr>
    <td><i>"We are dying of hunger and thirst, please send help."</i></td>
    <td><b>Requests</b> food and water</td>
  </tr>
  <tr>
    <td><i>"People are trapped under collapsed buildings after the earthquake."</i></td>
    <td><b>Requests</b> search and rescue + medical help</td>
  </tr>
  <tr>
    <td><i>"The hospital has no power and we need generators."</i></td>
    <td><b>Requests</b> electricity</td>
  </tr>
</table>

---

## ✨ Example

| Input | Output |
| --- | --- |
| <i>"People are trapped under collapsed buildings after the earthquake."</i> | <code>{"intent": "REQUEST", "hazards": [{"type": "EARTHQUAKE", "severity": 4}, {"type": "STRUCTURAL_DAMAGE", "severity": 4}], "resources": [{"type": "SEARCH_AND_RESCUE", "severity": 4}, {"type": "MEDICAL_HELP", "severity": 4}]}</code> |
| <i>"We are dying of hunger and thirst, please send help."</i> | <code>{"intent": "REQUEST", "hazards": [], "resources": [{"type": "WATER", "severity": 4}, {"type": "FOOD", "severity": 4}]}</code> |
| <i>"We have two trucks available to transport supplies."</i> | <code>{"intent": "OFFER", "hazards": [], "resources": [{"type": "TRANSPORT", "severity": 2}]}</code> |

---

## 🏗️ Architecture

<pre>
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
</pre>

### Pipeline Nodes

<table>
  <tr>
    <th>Node</th>
    <th>Responsibility</th>
  </tr>
  <tr>
    <td><b>Parse</b></td>
    <td>Classifies intent (<code>REQUEST</code> / <code>OFFER</code> / <code>OTHER</code>). Extracts hazards (<code>EARTHQUAKE</code>, <code>FLOOD</code>, <code>FIRE</code>) and resources (<code>FOOD</code>, <code>WATER</code>, <code>MEDICAL_HELP</code>) with severity levels (1-4).</td>
  </tr>
  <tr>
    <td><b>Verify</b></td>
    <td>LLM-as-judge QA gate. Checks for contradictions, wrong intent, spurious categories, and hazard/resource confusion. Designed to be conservative: only flag clear errors to avoid false rejections.</td>
  </tr>
  <tr>
    <td><b>Retry</b></td>
    <td>Loops back to Parse when verification fails. Keeps accumulated context. Configurable max attempts prevents infinite waste.</td>
  </tr>
  <tr>
    <td><b>Prioritize</b></td>
    <td>Computes overall priority (<code>LOW</code> / <code>HIGH</code> / <code>CRITICAL</code>) from intent + max severity.</td>
  </tr>
</table>

### Key Design Decisions

<table>
  <tr>
    <th>Decision</th>
    <th>Rationale</th>
  </tr>
  <tr>
    <td><b>LangGraph over raw LangChain</b></td>
    <td>State machine models the parse -> verify -> retry loop. Gives explicit state transitions and history tracking.</td>
  </tr>
  <tr>
    <td><b>LLM-as-judge verification</b></td>
    <td>Lightweight QA gate catches contradictions before they reach downstream systems. No human-in-the-loop needed.</td>
  </tr>
  <tr>
    <td><b>Conservative verifier</b></td>
    <td>Earlier versions wasted ~80% of retries by demanding severity upgrades for food/water mentions. Current verifier only flags direct contradictions.</td>
  </tr>
  <tr>
    <td><b>Config-driven model swapping</b></td>
    <td>All model parameters live in one YAML file. Swap from <code>phi4-mini</code> to <code>gemma4</code> to <code>minimax-m3</code> without touching pipeline code.</td>
  </tr>
</table>

---

## 🔬 Evaluation

Every prompt change is tested against a golden reference dataset with structured metrics. No gut feel.

### Golden Dataset

- **53 synthetic SMS messages** covering 10 disaster types across the Indian subcontinent (floods, cyclones, earthquakes, fires, gas leaks, power outages, cold waves, security threats, structural damage, communication failures). Messages are in Hindi, English, and Hinglish to reflect real-world code-switching.
- **Reference annotations** generated by <code>minimax-m3:cloud</code> (428B parameter model). Uses an identical prompt template to the pipeline. This ensures we measure model capability, not prompt mismatch.
- Gold standard is **provider-agnostic**. Can be regenerated from Gemini 3.1 Pro, GPT-5, or any stronger model by changing the <code>--model</code> flag in <code>annotate_synthetic.py</code>.
- Comparison script runs samples **concurrently** (default 4 workers) via <code>asyncio.Semaphore</code> for fast iteration.

### Metrics

<pre>
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
</pre>

Exact match is too harsh for multi-label extraction. Predicting <code>[FOOD, WATER]</code> when golden has <code>[FOOD, WATER, SHELTER]</code> is partially correct. Subset matching (<code>pipeline ⊆ reference</code>) separates precision from recall and gives a more honest picture.

---

## 📊 Results

Pipeline: <code>gemma4:31b-cloud</code> (31B) | Golden: <code>minimax-m3:cloud</code> (428B) | Samples: 53

### Overall

<table>
  <tr>
    <th>Metric</th>
    <th>Exact</th>
    <th>Subset</th>
  </tr>
  <tr>
    <td><b>Intent</b></td>
    <td><b>98.1%</b></td>
    <td><b>98.1%</b></td>
  </tr>
  <tr>
    <td><b>Hazards</b></td>
    <td><b>92.5%</b></td>
    <td><b>92.5%</b></td>
  </tr>
  <tr>
    <td><b>Resources</b></td>
    <td><b>67.9%</b></td>
    <td><b>79.2%</b></td>
  </tr>
</table>

### Per-Category: Hazards

<table>
  <tr>
    <th>Category</th>
    <th>TP</th>
    <th>FP</th>
    <th>FN</th>
    <th>Precision</th>
    <th>Recall</th>
  </tr>
  <tr><td>COLD</td><td>4</td><td>0</td><td>0</td><td>100.0%</td><td>100.0%</td></tr>
  <tr><td>COMMUNICATION_FAILURE</td><td>4</td><td>1</td><td>0</td><td>80.0%</td><td>100.0%</td></tr>
  <tr><td>EARTHQUAKE</td><td>6</td><td>0</td><td>0</td><td>100.0%</td><td>100.0%</td></tr>
  <tr><td>FIRE</td><td>5</td><td>0</td><td>0</td><td>100.0%</td><td>100.0%</td></tr>
  <tr><td>FLOODS</td><td>7</td><td>1</td><td>0</td><td>87.5%</td><td>100.0%</td></tr>
  <tr><td>GAS_LEAK</td><td>6</td><td>0</td><td>0</td><td>100.0%</td><td>100.0%</td></tr>
  <tr><td>POWER_OUTAGE</td><td>6</td><td>1</td><td>0</td><td>85.7%</td><td>100.0%</td></tr>
  <tr><td>SECURITY_THREAT</td><td>6</td><td>0</td><td>0</td><td>100.0%</td><td>100.0%</td></tr>
  <tr><td>STORM</td><td>7</td><td>0</td><td>1</td><td>100.0%</td><td>87.5%</td></tr>
  <tr><td>STRUCTURAL_DAMAGE</td><td>13</td><td>1</td><td>0</td><td>92.9%</td><td>100.0%</td></tr>
</table>

### Per-Category: Resources

<table>
  <tr>
    <th>Category</th>
    <th>TP</th>
    <th>FP</th>
    <th>FN</th>
    <th>Precision</th>
    <th>Recall</th>
  </tr>
  <tr><td>CLOTHING</td><td>3</td><td>0</td><td>0</td><td>100.0%</td><td>100.0%</td></tr>
  <tr><td>ELECTRICITY</td><td>4</td><td>1</td><td>0</td><td>80.0%</td><td>100.0%</td></tr>
  <tr><td>FOOD</td><td>6</td><td>0</td><td>0</td><td>100.0%</td><td>100.0%</td></tr>
  <tr><td>HEATING</td><td>1</td><td>0</td><td>0</td><td>100.0%</td><td>100.0%</td></tr>
  <tr><td>MEDICAL_HELP</td><td>20</td><td>1</td><td>2</td><td>95.2%</td><td>90.9%</td></tr>
  <tr><td>SEARCH_AND_RESCUE</td><td>23</td><td>4</td><td>1</td><td>85.2%</td><td>95.8%</td></tr>
  <tr><td>SECURITY_PERSONNEL</td><td>6</td><td>0</td><td>1</td><td>100.0%</td><td>85.7%</td></tr>
  <tr><td>SHELTER</td><td>3</td><td>0</td><td>4</td><td>100.0%</td><td>42.9%</td></tr>
  <tr><td>TRANSPORT</td><td>8</td><td>5</td><td>1</td><td>61.5%</td><td>88.9%</td></tr>
  <tr><td>WATER</td><td>1</td><td>0</td><td>1</td><td>100.0%</td><td>50.0%</td></tr>
</table>

### Verification Efficiency

<table>
  <tr>
    <th>Metric</th>
    <th>Value</th>
  </tr>
  <tr>
    <td>Avg retries per message</td>
    <td><b>0.4</b></td>
  </tr>
  <tr>
    <td>Messages with retries</td>
    <td>9 / 53</td>
  </tr>
  <tr>
    <td>Retries exhausted (max 3)</td>
    <td>6 / 53</td>
  </tr>
</table>

---

## ⚙️ API

Rakshak Edge ships with a FastAPI server for integrating into web applications and downstream logistics systems.

### Endpoints

<table>
  <tr>
    <th>Method</th>
    <th>Path</th>
    <th>Description</th>
  </tr>
  <tr>
    <td><code>POST</code></td>
    <td><code>/triage</code></td>
    <td>Parse, verify, and prioritize a single message</td>
  </tr>
  <tr>
    <td><code>GET</code></td>
    <td><code>/health</code></td>
    <td>Health check — confirms the server is running</td>
  </tr>
</table>

### Example Request

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"message": "Need food and water, stranded after the storm"}'
```

### Example Response

```json
{
  "intent": "REQUEST",
  "hazards": [{"type": "STORM", "severity": 3}],
  "resources": [
    {"type": "FOOD", "severity": 3},
    {"type": "WATER", "severity": 3}
  ],
  "priority_level": "CRITICAL"
}
```

### Start the Server

```bash
# Production
uv run fastapi run

# Development (with hot reload)
uv run fastapi dev
```

---

## 🧪 Prompt Optimization: A Case Study

The most impactful optimization came from treating prompts as testable hypotheses.

**Problem**: The model hallucinated <code>HEALTH_CRISIS</code> as a hazard in every message mentioning hunger, thirst, or injury. This caused 48% false negatives on resource extraction for those cases.

**Root Cause**: <code>HEALTH_CRISIS</code> was dual-classified as both a hazard and implicitly referenced by resource needs (food, water, medical help). The model learned to use it as a catch-all.

**Fix**: Removed <code>HEALTH_CRISIS</code> from the hazard ontology entirely. Added explicit instruction:

> <i>"Hunger, thirst, injury, illness, and dying people are NOT hazards. These are consequences that should be reflected in resource needs."</i>

**Validation**: Ran the full comparison engine before deploying. Hazard accuracy went from marginal to 98%. Resource accuracy stabilized at 90%. Retries dropped by 80%. All numbers measured against the golden dataset.

---

## 🚀 Getting Started

### Prerequisites

**Option 1 — Docker (recommended):**

- <a href="https://www.docker.com/">Docker</a>

**Option 2 — Local development:**

- Python 3.12+
- <a href="https://docs.astral.sh/uv/">uv</a> (fast Python package manager)

### Setup

#### 🐳 Docker (recommended)

```bash
git clone https://github.com/your-username/rakshak-edge
cd rakshak-edge

# Add your API key
cp .env.example .env
# Edit .env with your OLLAMA_API_KEY

# Build and run
docker compose up
```

Open [http://localhost:8000](http://localhost:8000).

#### 📦 Local (uv)

```bash
git clone https://github.com/your-username/rakshak-edge
cd rakshak-edge

# Install dependencies
uv sync

# Set your API key
echo "OLLAMA_API_KEY=your-key-here" > .env
# Start the API server
uv run fastapi dev
```


```bash
# Triage a single message
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"message": "Need food and water, we are stranded after the storm"}'
```

```bash
# Health check
curl http://localhost:8000/health
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI.

### Scripts

```bash
# Generate synthetic training data (53 India-focused SMS)
uv run python scripts/generate_synthetic.py

# Annotate synthetic data with a cloud model (concurrent, 4 workers)
uv run python scripts/annotate_synthetic.py --model minimax-m3:cloud --concurrency 4

# Compare pipeline output against golden dataset (concurrent, 4 workers)
uv run python scripts/compare_golden.py
```

### Configuration

```yaml
# configs/base.yaml
llm:
  model_name: "gemma4:31b-cloud" # swap models here
  temperature: 0.0
  use_auth: true

nodes:
  max_retries: 3 # verify -> retry loop cap
```

---

## 📁 Project Structure

<pre>
rakshak-edge/
├── Dockerfile                # Container image
├── docker-compose.yml        # Container orchestration
├── .dockerignore             # Docker build exclusions
├── .env.example              # Environment variable template
├── src/app/                  # FastAPI server
│   ├── __init__.py
│   ├── main.py               # /triage and /health endpoints
│   ├── static/
│   │   └── css/styles.css
│   └── templates/
│       └── index.html
├── src/rakshak_edge/         # Core pipeline
│   ├── graph.py              # LangGraph state machine
│   ├── nodes.py              # Parse -> Verify -> Retry -> Prioritize
│   ├── prompts.py            # System prompts (triage + verification)
│   ├── schema.py             # Pydantic models
│   ├── state.py              # Graph state definition
│   ├── config.py             # YAML config loader
│   ├── llm.py                # Ollama + cloud LLM client
│   └── cli.py               # CLI entry point
├── scripts/                  # Data tools and evaluation
│   ├── generate_synthetic.py # 53 India-focused synthetic SMS generator
│   ├── annotate_synthetic.py # Golden annotation via cloud LLM (async, concurrent)
│   └── compare_golden.py     # Pipeline vs golden comparison engine (async, concurrent)
├── data/
│   └── golden/               # Golden annotations + comparison reports
├── configs/
│   └── base.yaml             # Model + node configuration
└── pyproject.toml
</pre>

---

## 🛠️ Built With

- <b>Python 3.12</b> + <a href="https://docs.astral.sh/uv/">uv</a> for fast dependency management
- <b><a href="https://www.langchain.com/langgraph">LangGraph</a></b> for state machine orchestration
- <b><a href="https://www.langchain.com/">LangChain</a></b> for LLM integration and prompt templating
- <b><a href="https://docs.pydantic.dev/">Pydantic</a></b> for structured output parsing
- <b><a href="https://fastapi.tiangolo.com/">FastAPI</a></b> for HTTP API server
- <b><a href="https://ollama.com/">Ollama</a></b> for cloud LLM inference
- <b><a href="https://docs.docker.com/">Docker</a></b> for containerized deployment
- <b><a href="https://rich.readthedocs.io/">Rich</a></b> for CLI output formatting

---

## 📄 License

MIT · <a href="mailto:barikdibyasamapd@gmail.com">Dibya S. Barik</a>
