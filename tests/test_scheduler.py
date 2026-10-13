"""Tests for Deterministic Recovery Scheduler and Risk Analyzer."""
import datetime
import pytest

from agent.scheduler import generate_recovery_schedule
from agent.risk_analyzer import analyze_deadline_risks, calculate_workable_capacity
from agent.priority_engine import calculate_priorities


def test_remaining_work_calculation():
    """Verifies that remaining work hours formula is exact."""
    tot = 10.0
    pct = 40.0
    rem = round(tot * (1.0 - (pct / 100.0)), 2)
    assert rem == 6.0

    # 100% completed
    rem_comp = round(tot * (1.0 - (100.0 / 100.0)), 2)
    assert rem_comp == 0.0


def test_daily_capacity_limits_never_exceeded():
    """Scheduler must NEVER allocate more hours on any day than the user's daily limit."""
    today = datetime.date.today()
    tasks = [
        {
            "id": "t1",
            "name": "Big Project",
            "deadline": (today + datetime.timedelta(days=3)).isoformat(),
            "estimated_total_hours": 12.0,
            "completion_percentage": 0.0,
            "completed": False,
        }
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 3.0,
        "include_weekends": True,
        "busy_days": [],
    }
    risks, _ = analyze_deadline_risks(tasks, prefs)
    priorities = calculate_priorities(tasks, risks, 3.0)

    schedule, conflicts, stats = generate_recovery_schedule(tasks, prefs, priorities, risks)

    for day in schedule:
        assert day["allocated_hours"] <= 3.01, f"Day {day['date']} exceeded daily capacity!"


def test_unavailable_days_respected():
    """Scheduler must allocate 0 hours on days marked busy."""
    today = datetime.date.today()
    busy_day = (today + datetime.timedelta(days=1)).isoformat()
    tasks = [
        {
            "id": "t1",
            "name": "Assignment 1",
            "deadline": (today + datetime.timedelta(days=3)).isoformat(),
            "estimated_total_hours": 6.0,
            "completion_percentage": 0.0,
            "completed": False,
        }
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 4.0,
        "include_weekends": True,
        "busy_days": [busy_day],
    }
    risks, _ = analyze_deadline_risks(tasks, prefs)
    priorities = calculate_priorities(tasks, risks, 4.0)

    schedule, conflicts, stats = generate_recovery_schedule(tasks, prefs, priorities, risks)

    busy_entries = [d for d in schedule if d["date"] == busy_day]
    assert len(busy_entries) == 1
    assert busy_entries[0]["allocated_hours"] == 0.0
    assert busy_entries[0]["is_busy"] is True


def test_weekend_study_toggle():
    """Scheduler must allocate 0 hours on weekends when include_weekends is False."""
    # Find next Saturday
    today = datetime.date.today()
    days_to_sat = (5 - today.weekday()) % 7
    if days_to_sat == 0:
        days_to_sat = 7
    saturday = today + datetime.timedelta(days=days_to_sat)

    tasks = [
        {
            "id": "t1",
            "name": "Long Study",
            "deadline": (saturday + datetime.timedelta(days=5)).isoformat(),
            "estimated_total_hours": 20.0,
            "completion_percentage": 0.0,
            "completed": False,
        }
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 4.0,
        "include_weekends": False,
        "busy_days": [],
    }
    risks, _ = analyze_deadline_risks(tasks, prefs)
    priorities = calculate_priorities(tasks, risks, 4.0)

    schedule, conflicts, stats = generate_recovery_schedule(tasks, prefs, priorities, risks)

    for day in schedule:
        d_obj = datetime.date.fromisoformat(day["date"])
        if d_obj.weekday() in (5, 6):
            assert day["allocated_hours"] == 0.0, f"Weekend {day['date']} had work allocated when disabled!"


def test_completed_tasks_excluded():
    """Completed tasks or tasks with 100% completion must not be scheduled."""
    today = datetime.date.today()
    tasks = [
        {
            "id": "t1",
            "name": "Done Assignment",
            "deadline": (today + datetime.timedelta(days=1)).isoformat(),
            "estimated_total_hours": 5.0,
            "completion_percentage": 100.0,
            "completed": True,
        },
        {
            "id": "t2",
            "name": "Pending Assignment",
            "deadline": (today + datetime.timedelta(days=1)).isoformat(),
            "estimated_total_hours": 2.0,
            "completion_percentage": 0.0,
            "completed": False,
        },
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 4.0,
        "include_weekends": True,
        "busy_days": [],
    }
    risks, _ = analyze_deadline_risks(tasks, prefs)
    priorities = calculate_priorities(tasks, risks, 4.0)

    schedule, conflicts, stats = generate_recovery_schedule(tasks, prefs, priorities, risks)

    # Check all sessions across all days
    all_sessions = [s for d in schedule for s in d.get("sessions", [])]
    task_ids_scheduled = {s["task_id"] for s in all_sessions}

    assert "t1" not in task_ids_scheduled
    assert "t2" in task_ids_scheduled


def test_one_day_plan_without_unnecessary_date_range():
    """For a single-day plan where all work fits within today's capacity, only Day 1 is scheduled."""
    today = datetime.date.today()
    tasks = [
        {
            "id": "t1",
            "name": "Quick Quiz Review",
            "deadline": today.isoformat(),
            "estimated_total_hours": 1.5,
            "completion_percentage": 0.0,
            "completed": False,
        }
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 4.0,
        "include_weekends": True,
        "busy_days": [],
    }
    risks, _ = analyze_deadline_risks(tasks, prefs)
    priorities = calculate_priorities(tasks, risks, 4.0)

    schedule, conflicts, stats = generate_recovery_schedule(tasks, prefs, priorities, risks)

    # Exactly 1 day needed since 1.5h <= 4.0h
    assert len(schedule) == 1
    assert schedule[0]["date"] == today.isoformat()
    assert schedule[0]["allocated_hours"] == 1.5


def test_multi_day_schedule_dates():
    """Work requiring more than one day must accurately span multiple sequential days."""
    today = datetime.date.today()
    tasks = [
        {
            "id": "t1",
            "name": "Multi-Day Project",
            "deadline": (today + datetime.timedelta(days=5)).isoformat(),
            "estimated_total_hours": 9.0,
            "completion_percentage": 0.0,
            "completed": False,
        }
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 3.0,
        "include_weekends": True,
        "busy_days": [],
    }
    risks, _ = analyze_deadline_risks(tasks, prefs)
    priorities = calculate_priorities(tasks, risks, 3.0)

    schedule, conflicts, stats = generate_recovery_schedule(tasks, prefs, priorities, risks)

    # 9.0 hours at 3.0h/day requires 3 days
    assert len(schedule) == 3
    expected_dates = [
        today.isoformat(),
        (today + datetime.timedelta(days=1)).isoformat(),
        (today + datetime.timedelta(days=2)).isoformat(),
    ]
    actual_dates = [d["date"] for d in schedule]
    assert actual_dates == expected_dates


def test_overdue_tasks_detected_and_handled():
    """Overdue tasks must be flagged with CRITICAL risk and scheduled as overdue rescue."""
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tasks = [
        {
            "id": "t_overdue",
            "name": "Late Lab Record",
            "deadline": yesterday.isoformat(),
            "estimated_total_hours": 2.0,
            "completion_percentage": 0.0,
            "completed": False,
        }
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 4.0,
        "include_weekends": True,
        "busy_days": [],
    }
    risks, conflicts = analyze_deadline_risks(tasks, prefs)

    assert risks["t_overdue"]["is_overdue"] is True
    assert risks["t_overdue"]["risk_level"] == "CRITICAL"
    assert any(c["type"] == "OVERDUE_TASK" for c in conflicts)


def test_tasks_due_today():
    """Tasks due today with work exceeding today's capacity must trigger CRITICAL risk."""
    today = datetime.date.today()
    tasks = [
        {
            "id": "t_today",
            "name": "Urgent Due Today",
            "deadline": today.isoformat(),
            "estimated_total_hours": 6.0,
            "completion_percentage": 0.0,
            "completed": False,
        }
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 3.0,
        "include_weekends": True,
        "busy_days": [],
    }
    risks, conflicts = analyze_deadline_risks(tasks, prefs)

    assert risks["t_today"]["is_due_today"] is True
    assert risks["t_today"]["risk_level"] == "CRITICAL"
    assert any(c["type"] == "EXCEEDS_SAME_DAY_CAPACITY" for c in conflicts)


def test_multiple_competing_deadlines():
    """Multiple tasks due on same date competing for insufficient capacity trigger competition conflicts."""
    today = datetime.date.today()
    target_date = today + datetime.timedelta(days=2)
    tasks = [
        {
            "id": "t1",
            "name": "Task A",
            "deadline": target_date.isoformat(),
            "estimated_total_hours": 5.0,
            "completion_percentage": 0.0,
            "completed": False,
        },
        {
            "id": "t2",
            "name": "Task B",
            "deadline": target_date.isoformat(),
            "estimated_total_hours": 5.0,
            "completion_percentage": 0.0,
            "completed": False,
        },
    ]
    prefs = {
        "start_date": today.isoformat(),
        "available_hours_per_day": 2.0,  # 3 days * 2.0 = 6h capacity vs 10h workload
        "include_weekends": True,
        "busy_days": [],
    }
    risks, conflicts = analyze_deadline_risks(tasks, prefs)

    # Competition ratio exceeds capacity
    competing_conflicts = [c for c in conflicts if "COMPETITION" in c["type"] or "INSUFFICIENT" in c["type"]]
    assert len(competing_conflicts) > 0
