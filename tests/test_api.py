"""Tests for FastAPI endpoints and response schemas."""
import datetime
import pytest
from fastapi.testclient import TestClient

from app import app, SESSION_STORE

client = TestClient(app)


def test_home_page_renders():
    """GET / should render the HTML user interface."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Smart Deadline Rescue Agent" in response.text
    assert "<!DOCTYPE html>" in response.text


def test_health_check_endpoint():
    """GET /health should return runtime status and configuration."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "active_sessions_count" in data
    assert "gemini_integration" in data


def test_workflow_topology_endpoint():
    """GET /workflow describes the LangGraph workflow structure."""
    response = client.get("/workflow")
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 9
    assert len(data["edges"]) >= 7
    assert len(data["conditional_edges"]) == 2
    assert data["max_optimization_attempts"] == 3


def test_create_plan_valid():
    """POST /plan should create and return a valid recovery plan."""
    today = datetime.date.today()
    payload = {
        "tasks": [
            {
                "name": "Operating Systems Lab",
                "category": "OS",
                "deadline": (today + datetime.timedelta(days=2)).isoformat(),
                "estimated_total_hours": 3.0,
                "completion_percentage": 0.0,
                "difficulty": "Hard",
                "importance": "High",
                "notes": "Threads implementation",
            }
        ],
        "preferences": {
            "available_hours_per_day": 4.0,
            "study_start_time": "17:00",
            "busy_days": [],
            "start_date": today.isoformat(),
            "include_weekends": True,
        },
    }

    response = client.post("/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["plan_status"] in ("FEASIBLE", "OPTIMIZED")
    assert len(data["daily_schedule"]) >= 1
    assert "final_report" in data
    assert data["session_id"] in SESSION_STORE


def test_create_plan_empty_tasks():
    """POST /plan with empty task list must return 422."""
    payload = {
        "tasks": [],
        "preferences": {"available_hours_per_day": 4.0},
    }
    response = client.post("/plan", json=payload)
    assert response.status_code == 422


def test_create_plan_invalid_fields():
    """POST /plan with invalid fields (e.g. empty name, negative hours) must return 422."""
    # Blank name
    payload1 = {
        "tasks": [
            {
                "name": "   ",
                "deadline": "2026-10-15",
                "estimated_total_hours": 4.0,
            }
        ]
    }
    res1 = client.post("/plan", json=payload1)
    assert res1.status_code == 422

    # Negative hours
    payload2 = {
        "tasks": [
            {
                "name": "Invalid Hours Task",
                "deadline": "2026-10-15",
                "estimated_total_hours": -2.0,
            }
        ]
    }
    res2 = client.post("/plan", json=payload2)
    assert res2.status_code == 422

    # Invalid deadline format
    payload3 = {
        "tasks": [
            {
                "name": "Invalid Date Task",
                "deadline": "not-a-date",
                "estimated_total_hours": 3.0,
            }
        ]
    }
    res3 = client.post("/plan", json=payload3)
    assert res3.status_code == 422


def test_get_session_plan_and_not_found():
    """GET /plan/{session_id} retrieves plan or returns 404."""
    # 404 test
    res_404 = client.get("/plan/non-existent-session-id")
    assert res_404.status_code == 404

    # Create and retrieve
    today = datetime.date.today()
    create_res = client.post(
        "/plan",
        json={
            "tasks": [
                {
                    "name": "Quick Task",
                    "deadline": today.isoformat(),
                    "estimated_total_hours": 1.0,
                }
            ]
        },
    )
    s_id = create_res.json()["session_id"]

    get_res = client.get(f"/plan/{s_id}")
    assert get_res.status_code == 200
    assert get_res.json()["session_id"] == s_id


def test_replan_session_endpoint():
    """POST /plan/{session_id}/replan triggers replanning with modified preferences."""
    today = datetime.date.today()
    create_res = client.post(
        "/plan",
        json={
            "tasks": [
                {
                    "name": "Task to Replan",
                    "deadline": (today + datetime.timedelta(days=2)).isoformat(),
                    "estimated_total_hours": 5.0,
                }
            ],
            "preferences": {"available_hours_per_day": 2.0},
        },
    )
    s_id = create_res.json()["session_id"]

    # Replan with increased daily hours
    replan_res = client.post(
        f"/plan/{s_id}/replan",
        json={
            "preferences": {"available_hours_per_day": 6.0},
            "change_description": "User increased daily study capacity to 6h.",
        },
    )
    assert replan_res.status_code == 200
    data = replan_res.json()
    assert data["available_time_per_day"] == 6.0
    assert "increased" in data["history_changes"]


def test_complete_task_endpoint():
    """POST /plan/{session_id}/complete-task updates progress and replans."""
    today = datetime.date.today()
    create_res = client.post(
        "/plan",
        json={
            "tasks": [
                {
                    "id": "task-alpha",
                    "name": "Alpha Task",
                    "deadline": (today + datetime.timedelta(days=2)).isoformat(),
                    "estimated_total_hours": 3.0,
                }
            ]
        },
    )
    s_id = create_res.json()["session_id"]

    complete_res = client.post(
        f"/plan/{s_id}/complete-task",
        json={"task_id": "task-alpha", "completion_percentage": 100.0},
    )
    assert complete_res.status_code == 200
    data = complete_res.json()
    assert "task-alpha" in data["completed_tasks"]
    assert data["remaining_work"] == 0.0


def test_download_pdf_report_endpoint():
    """GET /plan/{session_id}/report downloads a valid PDF report."""
    today = datetime.date.today()
    create_res = client.post(
        "/plan",
        json={
            "tasks": [
                {
                    "name": "AI Project Proposal",
                    "category": "AI",
                    "deadline": (today + datetime.timedelta(days=3)).isoformat(),
                    "estimated_total_hours": 4.0,
                }
            ]
        },
    )
    s_id = create_res.json()["session_id"]

    report_res = client.get(f"/plan/{s_id}/report")
    assert report_res.status_code == 200
    assert report_res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in report_res.headers.get("content-disposition", "")
    assert len(report_res.content) > 1000
    assert report_res.content.startswith(b"%PDF")
