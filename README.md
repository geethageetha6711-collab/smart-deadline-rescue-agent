# Smart Deadline Rescue Agent (Agent 1)

> **Adaptive AI Academic Recovery & Schedule Feasibility Engine**  
> Built with **LangGraph**, **Google Gemini**, **FastAPI**, **ReportLab**, and **Vanilla Modern Frontend**.

---

## 1. Project Overview

Students frequently encounter severe academic pressure when assignments, lab records, term papers, and exams coincide within tight deadlines. Standard task-management apps merely list deadlines without calculating whether the workload is physically feasible given a student's daily study hours.

**Smart Deadline Rescue Agent** is a dedicated agentic system that transforms a student's chaotic task backlog into an honest, capacity-constrained recovery plan. It calculates remaining workload, evaluates deadline risks, ranks tasks with explainable priority scores, schedules study sessions chronologically, and adaptively replans when assignments are finished or deadlines shift.

---

## 2. Problem Statement

1. **Illusion of Time:** Students underestimate remaining hours and overestimate daily capacity.
2. **Competing Deadlines:** Multiple assignments due on the same date create bottlenecks that cannot be resolved without triage or renegotiation.
3. **Rigid Static Planners:** Traditional schedulers do not adapt dynamically when tasks are completed early or deadlines are extended.
4. **Hallucinated or Unrealistic Advice:** Chatbot-only tools often recommend impossible study schedules (e.g., studying 14 hours in an 8-hour day) without deterministic validation.

---

## 3. Key Features

- **Real LangGraph State Workflow:** 9 discrete nodes with typed state transitions, conditional branching, and bounded retry loops (maximum 3 optimization attempts).
- **Deterministic Risk Engine:** Transparent formulas classify deadline urgency as `LOW`, `MODERATE`, `HIGH`, or `CRITICAL`.
- **Explainable Priority Decision Scoring:** Multi-factor scoring ($0 - 100$) balancing urgency, workload volume, importance, and difficulty.
- **Capacity-Constrained Recovery Scheduling:** Strictly respects user's daily study hours, excludes blacked-out busy dates, and honors weekend preferences.
- **Adaptive Dynamic Replanning:** Instant schedule recalculation on task completion, progress change, deadline alteration, or capacity adjustment.
- **Google Gemini Integration with Deterministic Fallback:** Employs `langchain-google-genai` for natural-language reasoning when `GEMINI_API_KEY` is provided; automatically falls back to deterministic rule generation when unconfigured or offline.
- **Downloadable PDF Reports:** Professional ReportLab-generated recovery reports ready for offline review.
- **Polished Web Dashboard:** Responsive desktop and mobile UI with clean typography, metric cards, timeline schedules, and workflow topology inspection.

---

## 4. Architecture & LangGraph Workflow

### Agent State Schema (`AgentState`)

```python
class AgentState(TypedDict):
    session_id: str
    tasks: List[Dict[str, Any]]
    preferences: Dict[str, Any]
    available_time_per_day: float
    daily_schedule: List[Dict[str, Any]]
    deadline_risks: Dict[str, Dict[str, Any]]
    estimated_task_hours: Dict[str, float]
    priority_scores: Dict[str, Dict[str, Any]]
    completed_tasks: List[str]
    remaining_work: float
    conflicts: List[Dict[str, Any]]
    optimization_attempts: int
    recommendations: List[str]
    plan_status: str  # FEASIBLE | OPTIMIZED | INFEASIBLE_OVERLOADED
    final_report: Dict[str, Any]
    history_changes: Optional[str]
```

### Workflow Diagram

```mermaid
flowchart TD
    START([START]) --> N1[1. Task Input Validator]
    N1 --> N2[2. Deadline Risk Analyzer]
    N2 --> N3[3. Workload Estimator]
    N3 --> N4[4. Priority Decision Engine]
    N4 --> N5[5. Recovery Plan Generator]
    N5 --> N6{6. Schedule Feasibility Checker}
    
    N6 -- "Schedule Exceeds Capacity / Conflicts (< 3 cycles)" --> N7[7. Plan Optimizer]
    N7 --> N6
    
    N6 -- "Feasible or Max Cycles Reached (>= 3)" --> N8[8. Final Plan Evaluator]
    
    N8 -- "Unresolved Conflicts (< 3 cycles)" --> N7
    N8 -- "Evaluated Honest Status" --> N9[9. Report Generator\n(Gemini / Fallback)]
    N9 --> END([END])
```

---

## 5. Mathematical Formulas & Logic

### 5.1 Remaining Workload Calculation

$$\text{Remaining Hours} = \text{Estimated Total Hours} \times \left(1 - \frac{\text{Completion Percentage}}{100}\right)$$

### 5.2 Workable Capacity Before Deadline

$$\text{Capacity}(t) = \sum_{d = \text{start}}^{\text{deadline}} \text{Hours}(d)$$

Where:
- $\text{Hours}(d) = 0$ if $d \in \text{Busy Days}$
- $\text{Hours}(d) = 0$ if $d \in \{\text{Saturday}, \text{Sunday}\}$ and $\text{include\_weekends} = \text{False}$
- $\text{Hours}(d) = \text{available\_hours\_per\_day}$ otherwise

### 5.3 Risk Classification Matrix

- **`CRITICAL`**:
  - Overdue: $\text{days\_until\_deadline} < 0$ and $\text{remaining\_hours} > 0$
  - Due today with $\text{remaining\_hours} > \text{today's available capacity}$
  - $\text{remaining\_hours} > \text{workable capacity before deadline}$ (physically impossible)
- **`HIGH`**:
  - Due today within available hours
  - $\text{remaining\_hours} > 0.7 \times \text{capacity before deadline}$
  - Competing workload from multiple tasks exceeds available capacity before deadline
- **`MODERATE`**:
  - Tight buffer ($0.4 \times \text{capacity} < \text{remaining\_hours} \le 0.7 \times \text{capacity}$)
- **`LOW`**:
  - Comfortable buffer ($\le 0.4 \times \text{capacity}$) or 100% completed

### 5.4 Priority Score Formula ($0 - 100$ Points)

$$\text{Priority Score} = \min(100, \text{Urgency} + \text{Workload} + \text{Importance} + \text{Risk/Difficulty})$$

1. **Urgency Points ($0 - 35$):**
   - Overdue: $35$ | Due today: $32$ | Tomorrow: $28$ | $2$ days: $22$ | $3-4$ days: $16$ | $5-7$ days: $10$
2. **Workload Demand Points ($0 - 25$):**
   - $\ge 2.0 \times \text{daily capacity}$: $25$ pts
   - $\ge 1.0 \times \text{daily capacity}$: $18$ pts
   - $\ge 0.5 \times \text{daily capacity}$: $12$ pts
3. **Importance Points ($0 - 20$):**
   - High: $20$ pts | Medium: $12$ pts | Low: $5$ pts
4. **Risk & Difficulty Points ($0 - 20$):**
   - Critical Risk: $14$ pts | High Risk: $10$ pts | Moderate: $5$ pts
   - Hard Difficulty: $+6$ pts | Medium: $+3$ pts | Easy: $+1$ pt

---

## 6. Project Structure

```
Agent - 1/
├── app.py                     # FastAPI server, endpoints, in-memory session store
├── requirements.txt           # Python dependencies
├── README.md                  # Comprehensive documentation and viva prep
├── .gitignore                 # Excludes secrets, caches, and temp files
├── .env.example               # Environment variables template
├── Procfile                   # Process configuration for cloud deployment
├── render.yaml                # Render platform deployment manifest
├── agent/
│   ├── __init__.py
│   ├── state.py               # Pydantic models and AgentState TypedDict
│   ├── graph.py               # 9-node LangGraph workflow and conditional routing
│   ├── risk_analyzer.py       # Deterministic deadline risk engine
│   ├── priority_engine.py     # Normalized priority scoring algorithm
│   ├── scheduler.py           # Capacity-constrained chronological recovery scheduler
│   └── llm_service.py         # Google Gemini integration and deterministic fallback
├── services/
│   ├── __init__.py
│   └── report_service.py      # Professional PDF report generator (ReportLab)
├── templates/
│   └── index.html             # Responsive student dashboard template
├── static/
│   ├── style.css              # Custom design system with soft violet/slate palette
│   └── script.js              # Interactive client application and adaptive replanning
└── tests/
    ├── __init__.py
    ├── test_scheduler.py      # Scheduler capacity, weekend, and date tests
    ├── test_api.py            # FastAPI endpoints and PDF downloads
    └── test_agent_workflow.py # LangGraph transitions, bounded retry, and replanning
```

---

## 7. Gemini Integration & Deterministic Fallback

- **Library:** `langchain-google-genai` (`ChatGoogleGenerativeAI`).
- **Configuration:** Reads `GEMINI_API_KEY` and `GEMINI_MODEL` securely from the environment using `load_dotenv()`.
- **Dual-Engine Architecture:**
  - When `GEMINI_API_KEY` is present and valid: Gemini produces natural-language executive summaries, deadline trade-offs, and strategic advice.
  - When `GEMINI_API_KEY` is absent, quota-limited, or fails: The agent transparently activates the built-in deterministic rule engine.
  - The UI explicitly marks the insight origin as `GEMINI` or `DETERMINISTIC_ENGINE` so no output is deceptively attributed.

---

## 8. Local Setup & Execution

### 8.1 Prerequisites
- Python 3.10+ (tested on Python 3.12)
- pip

### 8.2 Installation
```bash
# Clone or enter workspace
cd "e:/Chaitanyaa/Geethuu/Agent - 1"

# Create virtual environment (optional)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 8.3 Environment Configuration (Optional)
```bash
cp .env.example .env
# Edit .env and enter GEMINI_API_KEY if desired
```
*Note: The application functions completely without an API key in Deterministic Fallback Mode.*

### 8.4 Run Automated Tests
```bash
pytest -v
```
*(All 25 unit and integration tests run in ~1 second).*

### 8.5 Start Application
```bash
uvicorn app:app --reload --port 8000
```
Open your browser at: **`http://localhost:8000`**

---

## 9. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves dashboard web application |
| `GET` | `/health` | Health status, storage mode, and Gemini status |
| `GET` | `/workflow` | Returns LangGraph nodes, edges, and state schema |
| `POST` | `/plan` | Accepts tasks and preferences; executes workflow; returns plan |
| `GET` | `/plan/{session_id}` | Retrieves plan for specified session |
| `POST` | `/plan/{session_id}/replan` | Updates preferences or tasks and adaptively replans |
| `POST` | `/plan/{session_id}/complete-task` | Marks task complete / updates progress and replans |
| `GET` | `/plan/{session_id}/report` | Generates and downloads ReportLab PDF recovery plan |

---

## 10. Deployment to Render

1. Push this repository to GitHub.
2. In [Render Dashboard](https://dashboard.render.com), create a new **Web Service**.
3. Select your repository.
4. Render will automatically detect `render.yaml` or you can manually configure:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. *(Optional)* Add Environment Variables in Render:
   - `GEMINI_API_KEY`: Your Google Gemini API key.
   - `GEMINI_MODEL`: `gemini-2.5-flash`

---

## 11. Known Limitations

- **In-Memory Session Store:** Session states are held in memory and will reset if the server restarts. (Documented intentionally; no external database is mandated).
- **Time-Zone Assumption:** Dates are calculated based on the host server's local calendar dates.

---

## 12. Viva / Interview Questions & Concise Answers

### Q1: Why did you use LangGraph instead of a simple linear pipeline or basic LLM prompt?
**Answer:** LangGraph provides cyclic state graph orchestration with conditional branching, bounded retry loops, and typed state persistence. When a proposed schedule is overloaded, the graph routes execution back to the `Plan Optimizer` node with an incremented attempt counter, stopping strictly after 3 attempts. A standard LLM prompt cannot enforce mathematical scheduling constraints or deterministic capacity boundaries.

### Q2: How does the agent prevent hallucinated schedules?
**Answer:** All core scheduling, time calculation, risk assessment, and capacity allocation are computed deterministically in Python. The LLM is used strictly for contextual reasoning, qualitative summaries, and student guidance. If the math shows that 12 hours of work are due today with only 4 hours available, the deterministic engine flags the plan as `INFEASIBLE_OVERLOADED`, overriding any potential LLM optimism.

### Q3: What happens if Google Gemini is unavailable or quota is exceeded?
**Answer:** The system features zero-downtime deterministic resilience. If `GEMINI_API_KEY` is missing or the API call raises an exception, `llm_service.py` falls back to the deterministic insight engine, which outputs structured summaries, priority rationales, and emergency recommendations labeled honestly with source `deterministic_engine`.

### Q4: How does adaptive replanning work when a task is completed?
**Answer:** When the user marks a task completed via `/plan/{session_id}/complete-task`, the agent zeroes out the remaining hours for that task, updates the session state, and invokes the compiled LangGraph workflow. The workload estimator recalibrates aggregate effort, and the recovery scheduler shifts upcoming tasks into the newly freed study blocks.

### Q5: What algorithm does the scheduler use?
**Answer:** It uses a greedy, deadline-aware, capacity-constrained chronological scheduler. It traverses day-by-day starting from the user's start date, checks busy days and weekend flags, allocates up to the exact daily capacity limit, prioritizes overdue and due-today tasks first, and splits large tasks across sessions. If an allocation must take place after a deadline, it logs a critical `SCHEDULED_PAST_DEADLINE` conflict.
