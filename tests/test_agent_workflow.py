"""Tests for LangGraph Agent Workflow, Conditional Routing, and Bounded Optimization."""
import datetime
import pytest

from agent.graph import compiled_workflow
from agent.state import AgentState
from agent.llm_service import _generate_deterministic_insights, generate_ai_insights


def test_langgraph_full_workflow_feasible():
    """Tests complete LangGraph execution on a realistic feasible academic task."""
    today = datetime.date.today()
    state: AgentState = {
        "session_id": "test-wf-1",
        "tasks": [
            {
                "id": "t1",
                "name": "Linear Algebra Homework",
                "category": "Math",
                "deadline": (today + datetime.timedelta(days=3)).isoformat(),
                "estimated_total_hours": 3.0,
                "completion_percentage": 0.0,
                "difficulty": "Medium",
                "importance": "High",
                "notes": "",
                "completed": False,
            }
        ],
        "preferences": {
            "available_hours_per_day": 4.0,
            "study_start_time": "17:00",
            "busy_days": [],
            "start_date": today.isoformat(),
            "include_weekends": True,
        },
        "available_time_per_day": 4.0,
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
        "history_changes": None,
    }

    result = compiled_workflow.invoke(state)

    # Verify state transitions and results
    assert result["plan_status"] == "FEASIBLE"
    assert result["remaining_work"] == 3.0
    assert "t1" in result["deadline_risks"]
    assert "t1" in result["priority_scores"]
    assert len(result["daily_schedule"]) >= 1
    assert len(result["recommendations"]) > 0
    assert result["final_report"]["source"] in ("deterministic_engine", "gemini")


def test_bounded_optimization_max_three_attempts():
    """Workflow must stop optimization after at most 3 attempts and report conflicts honestly."""
    today = datetime.date.today()
    # Task requires 20 hours due today with only 2 hours capacity
    state: AgentState = {
        "session_id": "test-wf-bounded",
        "tasks": [
            {
                "id": "t_impossible",
                "name": "Massive Dissertation Chapter",
                "category": "Writing",
                "deadline": today.isoformat(),
                "estimated_total_hours": 20.0,
                "completion_percentage": 0.0,
                "difficulty": "Hard",
                "importance": "High",
                "notes": "",
                "completed": False,
            }
        ],
        "preferences": {
            "available_hours_per_day": 2.0,
            "study_start_time": "18:00",
            "busy_days": [],
            "start_date": today.isoformat(),
            "include_weekends": True,
        },
        "available_time_per_day": 2.0,
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
        "history_changes": None,
    }

    result = compiled_workflow.invoke(state)

    # Bounded retries: must stop at 3 and report status as INFEASIBLE_OVERLOADED
    assert result["optimization_attempts"] == 3
    assert result["plan_status"] == "INFEASIBLE_OVERLOADED"
    assert len(result["conflicts"]) > 0
    # Must offer trade-offs and alternatives
    assert result["final_report"]["trade_offs_and_alternatives"] is not None


def test_adaptive_replanning_task_completion():
    """Marking a task complete reduces remaining work and rebalances schedule."""
    today = datetime.date.today()
    # Initial state with 2 tasks
    tasks = [
        {
            "id": "t1",
            "name": "Task 1",
            "deadline": (today + datetime.timedelta(days=1)).isoformat(),
            "estimated_total_hours": 3.0,
            "completion_percentage": 0.0,
            "completed": False,
        },
        {
            "id": "t2",
            "name": "Task 2",
            "deadline": (today + datetime.timedelta(days=2)).isoformat(),
            "estimated_total_hours": 4.0,
            "completion_percentage": 0.0,
            "completed": False,
        },
    ]

    prefs = {
        "available_hours_per_day": 4.0,
        "start_date": today.isoformat(),
        "include_weekends": True,
    }

    init_state: AgentState = {
        "session_id": "test-replan",
        "tasks": tasks,
        "preferences": prefs,
        "available_time_per_day": 4.0,
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
        "history_changes": None,
    }

    res1 = compiled_workflow.invoke(init_state)
    assert res1["remaining_work"] == 7.0

    # Simulate marking Task 1 completed
    tasks_updated = [
        {
            "id": "t1",
            "name": "Task 1",
            "deadline": (today + datetime.timedelta(days=1)).isoformat(),
            "estimated_total_hours": 3.0,
            "completion_percentage": 100.0,
            "completed": True,
        },
        {
            "id": "t2",
            "name": "Task 2",
            "deadline": (today + datetime.timedelta(days=2)).isoformat(),
            "estimated_total_hours": 4.0,
            "completion_percentage": 0.0,
            "completed": False,
        },
    ]

    replan_state: AgentState = {
        **res1,
        "tasks": tasks_updated,
        "optimization_attempts": 0,
        "conflicts": [],
    }

    res2 = compiled_workflow.invoke(replan_state)
    assert res2["remaining_work"] == 4.0
    assert "t1" in res2["completed_tasks"]


def test_deadline_change_replan():
    """Moving a deadline further out reduces risk from CRITICAL to MODERATE/LOW."""
    today = datetime.date.today()
    # Initially due today (tight)
    task = {
        "id": "t1",
        "name": "Urgent Math",
        "deadline": today.isoformat(),
        "estimated_total_hours": 3.0,
        "completion_percentage": 0.0,
        "completed": False,
    }

    state1: AgentState = {
        "session_id": "test-deadline-chg",
        "tasks": [task],
        "preferences": {"available_hours_per_day": 4.0, "start_date": today.isoformat(), "include_weekends": True},
        "available_time_per_day": 4.0,
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
        "history_changes": None,
    }

    res1 = compiled_workflow.invoke(state1)
    risk1 = res1["deadline_risks"]["t1"]["risk_level"]

    # Now extend deadline by 5 days
    extended_task = {
        **task,
        "deadline": (today + datetime.timedelta(days=5)).isoformat(),
    }
    state2: AgentState = {
        **res1,
        "tasks": [extended_task],
        "optimization_attempts": 0,
        "conflicts": [],
    }

    res2 = compiled_workflow.invoke(state2)
    risk2 = res2["deadline_risks"]["t1"]["risk_level"]

    assert risk2 in ("LOW", "MODERATE")
    assert res2["priority_scores"]["t1"]["score"] < res1["priority_scores"]["t1"]["score"]


def test_gemini_fallback_behavior():
    """Service gracefully falls back to deterministic engine without crashing when key is absent."""
    today = datetime.date.today()
    tasks = [
        {
            "id": "t1",
            "name": "Chemistry Quiz",
            "deadline": (today + datetime.timedelta(days=2)).isoformat(),
            "estimated_total_hours": 2.0,
            "completion_percentage": 0.0,
            "completed": False,
        }
    ]
    prefs = {"available_hours_per_day": 4.0, "start_date": today.isoformat()}

    # Call fallback directly
    insights = _generate_deterministic_insights(
        tasks=tasks,
        preferences=prefs,
        daily_schedule=[],
        deadline_risks={"t1": {"risk_level": "LOW", "days_until_deadline": 2}},
        priority_scores={"t1": {"score": 45.0, "rank": 1, "reasons": ["Comfortable deadline"]}},
        conflicts=[],
        plan_status="FEASIBLE",
        optimization_attempts=0,
    )

    assert insights["source"] == "deterministic_engine"
    assert insights["model"] == "rule_based_fallback"
    assert len(insights["executive_summary"]) > 10
    assert len(insights["recommendations"]) > 0
