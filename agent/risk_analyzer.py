"""Deterministic Deadline Risk Analyzer for Smart Deadline Rescue Agent."""
import datetime
from typing import List, Dict, Any, Tuple


def calculate_workable_capacity(
    start_date: datetime.date,
    end_date: datetime.date,
    available_hours_per_day: float,
    busy_days_set: set,
    include_weekends: bool,
) -> float:
    """Calculates total workable hours available between start_date and end_date (inclusive)."""
    if end_date < start_date:
        return 0.0

    current = start_date
    total_hours = 0.0
    while current <= end_date:
        iso_str = current.isoformat()
        is_weekend = current.weekday() in (5, 6)
        if iso_str in busy_days_set:
            pass  # 0 hours on busy day
        elif is_weekend and not include_weekends:
            pass  # 0 hours on weekend if excluded
        else:
            total_hours += available_hours_per_day
        current += datetime.timedelta(days=1)
    return total_hours


def analyze_deadline_risks(
    tasks: List[Dict[str, Any]],
    preferences: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """Analyzes deadline risk for each task using deterministic rules.
    
    Returns:
        deadline_risks: mapping of task_id -> risk assessment dict
        conflicts: list of detected system-wide or task-specific conflicts
    """
    start_date_str = preferences.get("start_date", datetime.date.today().isoformat())
    try:
        start_date = datetime.date.fromisoformat(start_date_str)
    except Exception:
        start_date = datetime.date.today()

    available_hours = float(preferences.get("available_hours_per_day", 4.0))
    busy_days_set = set(preferences.get("busy_days", []))
    include_weekends = bool(preferences.get("include_weekends", True))

    risks: Dict[str, Dict[str, Any]] = {}
    conflicts: List[Dict[str, Any]] = []

    # Pre-calculate remaining hours for each task
    parsed_tasks = []
    for t in tasks:
        t_id = str(t.get("id"))
        t_name = t.get("name", "Untitled")
        tot_hrs = float(t.get("estimated_total_hours", 1.0))
        pct = float(t.get("completion_percentage", 0.0))
        rem_hrs = round(tot_hrs * (1.0 - (pct / 100.0)), 2)
        if rem_hrs < 0:
            rem_hrs = 0.0
        if t.get("completed", False):
            rem_hrs = 0.0

        try:
            d_date = datetime.date.fromisoformat(t.get("deadline"))
        except Exception:
            d_date = start_date

        parsed_tasks.append({
            "id": t_id,
            "name": t_name,
            "category": t.get("category", "General"),
            "deadline": d_date,
            "total_hours": tot_hrs,
            "completion_percentage": pct,
            "remaining_hours": rem_hrs,
            "difficulty": t.get("difficulty", "Medium"),
            "importance": t.get("importance", "Medium"),
            "completed": t.get("completed", False) or (pct >= 100.0),
        })

    # Group incomplete tasks by deadline to detect competition
    deadline_groups: Dict[datetime.date, List[Dict[str, Any]]] = {}
    for pt in parsed_tasks:
        if not pt["completed"] and pt["remaining_hours"] > 0:
            deadline_groups.setdefault(pt["deadline"], []).append(pt)

    for pt in parsed_tasks:
        t_id = pt["id"]
        t_name = pt["name"]
        rem_hrs = pt["remaining_hours"]
        d_date = pt["deadline"]
        completed = pt["completed"]

        if completed or rem_hrs == 0.0:
            risks[t_id] = {
                "risk_level": "LOW",
                "remaining_hours": 0.0,
                "days_until_deadline": (d_date - start_date).days,
                "available_capacity_before_deadline": 0.0,
                "capacity_ratio": 0.0,
                "is_overdue": False,
                "is_due_today": False,
                "factors": ["Task is 100% completed."],
                "explanation": f"Task '{t_name}' is already finished. No deadline risk.",
            }
            continue

        days_until = (d_date - start_date).days
        is_overdue = days_until < 0
        is_due_today = days_until == 0

        cap_before_deadline = calculate_workable_capacity(
            start_date=start_date,
            end_date=d_date,
            available_hours_per_day=available_hours,
            busy_days_set=busy_days_set,
            include_weekends=include_weekends,
        )

        cap_ratio = round(rem_hrs / max(0.1, cap_before_deadline), 2)

        # Competing work due on or before this task's deadline
        competing_tasks = [
            other for other in parsed_tasks
            if not other["completed"]
            and other["remaining_hours"] > 0
            and other["deadline"] <= d_date
        ]
        total_competing_hours = round(sum(other["remaining_hours"] for other in competing_tasks), 2)
        competing_ratio = round(total_competing_hours / max(0.1, cap_before_deadline), 2)

        factors: List[str] = []
        risk_level = "LOW"

        # Overdue detection
        if is_overdue:
            risk_level = "CRITICAL"
            factors.append(f"OVERDUE by {abs(days_until)} day(s). Deadline passed on {d_date.isoformat()}.")
            conflicts.append({
                "type": "OVERDUE_TASK",
                "task_id": t_id,
                "task_name": t_name,
                "severity": "CRITICAL",
                "message": f"Task '{t_name}' was due on {d_date.isoformat()} and still requires {rem_hrs}h of work.",
            })

        # Due today detection
        elif is_due_today:
            today_capacity = calculate_workable_capacity(
                start_date=start_date,
                end_date=start_date,
                available_hours_per_day=available_hours,
                busy_days_set=busy_days_set,
                include_weekends=include_weekends,
            )
            if rem_hrs > today_capacity:
                risk_level = "CRITICAL"
                factors.append(
                    f"Due TODAY ({d_date.isoformat()}). Remaining effort ({rem_hrs}h) exceeds today's workable study capacity ({today_capacity}h)."
                )
                conflicts.append({
                    "type": "EXCEEDS_SAME_DAY_CAPACITY",
                    "task_id": t_id,
                    "task_name": t_name,
                    "severity": "CRITICAL",
                    "message": f"Task '{t_name}' requires {rem_hrs}h today, but only {today_capacity}h are available.",
                })
            else:
                risk_level = "HIGH"
                factors.append(f"Due TODAY ({d_date.isoformat()}). Needs {rem_hrs}h out of {today_capacity}h available today.")

        # Exceeds standalone capacity
        elif rem_hrs > cap_before_deadline:
            risk_level = "CRITICAL"
            factors.append(
                f"Remaining work ({rem_hrs}h) exceeds TOTAL workable hours ({cap_before_deadline}h) available before deadline ({d_date.isoformat()})."
            )
            conflicts.append({
                "type": "INSUFFICIENT_TIME_BEFORE_DEADLINE",
                "task_id": t_id,
                "task_name": t_name,
                "severity": "CRITICAL",
                "message": f"Task '{t_name}' cannot be finished before deadline without extending deadline or increasing study hours.",
            })

        # Multi-task competition exceeding capacity
        elif total_competing_hours > cap_before_deadline:
            risk_level = "HIGH" if days_until > 2 else "CRITICAL"
            factors.append(
                f"Resource competition: {len(competing_tasks)} tasks require {total_competing_hours}h before {d_date.isoformat()}, but available capacity is only {cap_before_deadline}h."
            )
            conflicts.append({
                "type": "DEADLINE_COMPETITION_OVERLOAD",
                "task_id": t_id,
                "task_name": t_name,
                "severity": risk_level,
                "message": f"Total competing work ({total_competing_hours}h) exceeds capacity ({cap_before_deadline}h) up to {d_date.isoformat()}.",
            })

        # Tight schedule capacity ratio
        elif cap_ratio > 0.7:
            risk_level = "HIGH"
            factors.append(f"High workload density: Task consumes {int(cap_ratio * 100)}% of all available study hours before deadline.")
        elif cap_ratio > 0.4 or days_until <= 3:
            risk_level = "MODERATE"
            factors.append(f"Moderate workload density: Consumes {int(cap_ratio * 100)}% of available time with {days_until} days remaining.")
        else:
            risk_level = "LOW"
            factors.append(f"Comfortable buffer: {days_until} days remaining with {cap_before_deadline}h capacity for {rem_hrs}h work.")

        # Difficulty & importance context
        if pt["difficulty"] == "Hard" and risk_level != "CRITICAL":
            factors.append("Hard difficulty task: Requires higher cognitive focus and contingency margin.")
            if risk_level == "LOW" and cap_ratio > 0.3:
                risk_level = "MODERATE"

        # Build natural explanation
        explanation = (
            f"Risk classified as {risk_level}. "
            + " ".join(factors)
        )

        risks[t_id] = {
            "risk_level": risk_level,
            "remaining_hours": rem_hrs,
            "days_until_deadline": days_until,
            "available_capacity_before_deadline": cap_before_deadline,
            "capacity_ratio": cap_ratio,
            "competing_tasks_count": len(competing_tasks),
            "total_competing_hours": total_competing_hours,
            "is_overdue": is_overdue,
            "is_due_today": is_due_today,
            "factors": factors,
            "explanation": explanation,
        }

    return risks, conflicts
