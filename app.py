"""FastAPI Application for Smart Deadline Rescue Agent."""
import os
import uuid
import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from agent.state import (
    CreatePlanRequest,
    ReplanRequest,
    CompleteTaskRequest,
    AgentState,
)
from agent.graph import compiled_workflow
from agent.llm_service import is_gemini_available, get_gemini_model_name
from services.report_service import create_pdf_report

load_dotenv()

app = FastAPI(
    title="Smart Deadline Rescue Agent API",
    description="Adaptive AI-powered task recovery and planning system for students.",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# In-Memory Session Store
# NOTE: As documented, sessions are stored in memory and reset on server restart.
SESSION_STORE: Dict[str, Dict[str, Any]] = {}


@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    """Serves the dashboard user interface."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "gemini_available": is_gemini_available(),
            "gemini_model": get_gemini_model_name(),
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint providing runtime status and configuration."""
    return {
        "status": "healthy",
        "service": "Smart Deadline Rescue Agent",
        "timestamp": datetime.datetime.now().isoformat(),
        "active_sessions_count": len(SESSION_STORE),
        "storage_mode": "in-memory (sessions reset on server restart)",
        "gemini_integration": {
            "configured": is_gemini_available(),
            "model": get_gemini_model_name(),
            "mode": "Google Gemini API" if is_gemini_available() else "Deterministic Engine Fallback",
        },
    }


@app.get("/workflow")
async def get_workflow_topology():
    """Describes the LangGraph workflow nodes, transitions, and conditional routing."""
    return {
        "workflow_name": "Smart Deadline Rescue Agent LangGraph",
        "nodes": [
            {"name": "task_input_validator", "description": "Validates inputs, cleans fields, flags completed tasks"},
            {"name": "deadline_risk_analyzer", "description": "Deterministic capacity-to-deadline analysis and risk categorization"},
            {"name": "workload_estimator", "description": "Calculates remaining hours and aggregate effort"},
            {"name": "priority_decision_engine", "description": "Computes normalized multi-factor priority scores (0-100) and rankings"},
            {"name": "recovery_plan_generator", "description": "Date-wise scheduling respecting daily capacity and unavailable days"},
            {"name": "schedule_feasibility_checker", "description": "Detects deadline conflicts, overloads, and feasibility"},
            {"name": "plan_optimizer", "description": "Adjusts allocations, enforces bounded 3-cycle optimization retry limit"},
            {"name": "final_plan_evaluator", "description": "Validates final plan status honestly (FEASIBLE, OPTIMIZED, or INFEASIBLE_OVERLOADED)"},
            {"name": "report_generator", "description": "Synthesizes Gemini AI reasoning or deterministic insights and recommendations"},
        ],
        "edges": [
            {"from": "START", "to": "task_input_validator"},
            {"from": "task_input_validator", "to": "deadline_risk_analyzer"},
            {"from": "deadline_risk_analyzer", "to": "workload_estimator"},
            {"from": "workload_estimator", "to": "priority_decision_engine"},
            {"from": "priority_decision_engine", "to": "recovery_plan_generator"},
            {"from": "recovery_plan_generator", "to": "schedule_feasibility_checker"},
            {"from": "plan_optimizer", "to": "schedule_feasibility_checker"},
            {"from": "report_generator", "to": "END"},
        ],
        "conditional_edges": [
            {
                "from": "schedule_feasibility_checker",
                "condition": "If schedule exceeds available time and attempts < 3",
                "branches": {
                    "optimize": "plan_optimizer",
                    "evaluate": "final_plan_evaluator",
                },
            },
            {
                "from": "final_plan_evaluator",
                "condition": "If unresolved conflicts remain and attempts < 3",
                "branches": {
                    "optimize": "plan_optimizer",
                    "report": "report_generator",
                },
            },
        ],
        "max_optimization_attempts": 3,
        "shared_state_schema": [
            "session_id", "tasks", "preferences", "available_time_per_day",
            "daily_schedule", "deadline_risks", "estimated_task_hours",
            "priority_scores", "completed_tasks", "remaining_work",
            "conflicts", "optimization_attempts", "recommendations",
            "plan_status", "final_report", "history_changes"
        ],
    }


@app.post("/plan")
async def create_plan(request: CreatePlanRequest):
    """Creates a new recovery plan using the LangGraph workflow."""
    if not request.tasks:
        raise HTTPException(status_code=422, detail="At least one task must be provided.")

    session_id = str(uuid.uuid4())[:10]
    tasks_data = [t.model_dump() for t in request.tasks]
    prefs_data = request.preferences.model_dump() if request.preferences else {}

    initial_state: AgentState = {
        "session_id": session_id,
        "tasks": tasks_data,
        "preferences": prefs_data,
        "available_time_per_day": float(prefs_data.get("available_hours_per_day", 4.0)),
        "daily_schedule": [],
        "deadline_risks": {},
        "estimated_task_hours": {},
        "priority_scores": {},
        "completed_tasks": [],
        "remaining_work": 0.0,
        "conflicts": [],
        "optimization_attempts": 0,
        "recommendations": [],
        "plan_status": "PENDING",
        "final_report": {},
        "history_changes": "Initial recovery plan generated.",
    }

    try:
        final_state = compiled_workflow.invoke(initial_state)
        SESSION_STORE[session_id] = final_state
        return final_state
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}")


@app.get("/plan/{session_id}")
async def get_plan(session_id: str):
    """Retrieves an existing session and its current plan."""
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return SESSION_STORE[session_id]


@app.post("/plan/{session_id}/replan")
async def replan_session(session_id: str, request: ReplanRequest):
    """Updates tasks or preferences in an existing session and triggers adaptive replanning."""
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    prev_state = SESSION_STORE[session_id]

    # Update tasks if provided
    if request.tasks is not None:
        tasks_data = [t.model_dump() for t in request.tasks]
    else:
        tasks_data = prev_state.get("tasks", [])

    # Update preferences if provided
    if request.preferences is not None:
        prefs_data = request.preferences.model_dump()
    else:
        prefs_data = prev_state.get("preferences", {})

    change_desc = request.change_description or "Plan re-evaluated following user updates."

    replan_state: AgentState = {
        "session_id": session_id,
        "tasks": tasks_data,
        "preferences": prefs_data,
        "available_time_per_day": float(prefs_data.get("available_hours_per_day", 4.0)),
        "daily_schedule": [],
        "deadline_risks": {},
        "estimated_task_hours": {},
        "priority_scores": {},
        "completed_tasks": [],
        "remaining_work": 0.0,
        "conflicts": [],
        "optimization_attempts": 0,
        "recommendations": [],
        "plan_status": "REPLANNING",
        "final_report": {},
        "history_changes": change_desc,
    }

    try:
        new_state = compiled_workflow.invoke(replan_state)
        SESSION_STORE[session_id] = new_state
        return new_state
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to replan: {str(e)}")


@app.post("/plan/{session_id}/complete-task")
async def complete_task(session_id: str, request: CompleteTaskRequest):
    """Marks a task completed or updates its progress and replans."""
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    prev_state = SESSION_STORE[session_id]
    tasks = list(prev_state.get("tasks", []))
    target_task = None

    for t in tasks:
        if str(t.get("id")) == str(request.task_id):
            target_task = t
            pct = request.completion_percentage if request.completion_percentage is not None else 100.0
            t["completion_percentage"] = pct
            t["completed"] = pct >= 100.0
            break

    if not target_task:
        raise HTTPException(status_code=404, detail=f"Task '{request.task_id}' not found in session.")

    status_note = "marked 100% complete" if target_task["completed"] else f"progress updated to {target_task['completion_percentage']}%"
    change_desc = f"Task '{target_task.get('name')}' {status_note}. Schedule rebalanced."

    replan_state: AgentState = {
        "session_id": session_id,
        "tasks": tasks,
        "preferences": prev_state.get("preferences", {}),
        "available_time_per_day": prev_state.get("available_time_per_day", 4.0),
        "daily_schedule": [],
        "deadline_risks": {},
        "estimated_task_hours": {},
        "priority_scores": {},
        "completed_tasks": [],
        "remaining_work": 0.0,
        "conflicts": [],
        "optimization_attempts": 0,
        "recommendations": [],
        "plan_status": "REPLANNING",
        "final_report": {},
        "history_changes": change_desc,
    }

    try:
        new_state = compiled_workflow.invoke(replan_state)
        SESSION_STORE[session_id] = new_state
        return new_state
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to replan task completion: {str(e)}")


@app.get("/plan/{session_id}/report")
async def download_report(session_id: str):
    """Generates and downloads a professional PDF recovery report for the session."""
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    state = SESSION_STORE[session_id]

    try:
        pdf_bytes = create_pdf_report(state)
        filename = f"deadline_rescue_plan_{session_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")
