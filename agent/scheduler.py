"""Deterministic Recovery Scheduler for Smart Deadline Rescue Agent."""
import datetime
from typing import List, Dict, Any, Tuple


def _add_minutes_to_time(time_str: str, minutes: int) -> str:
    """Helper to add minutes to a HH:MM string."""
    try:
        parts = time_str.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        total_m = hh * 60 + mm + minutes
        new_hh = (total_m // 60) % 24
        new_mm = total_m % 60
        return f"{new_hh:02d}:{new_mm:02d}"
    except Exception:
        return time_str


def generate_recovery_schedule(
    tasks: List[Dict[str, Any]],
    preferences: Dict[str, Any],
    priority_scores: Dict[str, Dict[str, Any]],
    deadline_risks: Dict[str, Dict[str, Any]],
    max_days_horizon: int = 21,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Generates a date-wise, capacity-constrained recovery schedule.
    
    Returns:
        daily_schedule: List of day objects with date, sessions, capacity, notes
        conflicts: List of detected scheduling conflicts (e.g. past deadline)
        stats: Summary statistics of the generated schedule
    """
    start_date_str = preferences.get("start_date", datetime.date.today().isoformat())
    try:
        start_date = datetime.date.fromisoformat(start_date_str)
    except Exception:
        start_date = datetime.date.today()

    available_hours_per_day = float(preferences.get("available_hours_per_day", 4.0))
    busy_days_set = set(preferences.get("busy_days", []))
    include_weekends = bool(preferences.get("include_weekends", True))
    preferred_start_time = preferences.get("study_start_time") or "17:00"

    # Prepare active tasks that have remaining work
    active_tasks = []
    for t in tasks:
        t_id = str(t.get("id"))
        tot_hrs = float(t.get("estimated_total_hours", 1.0))
        pct = float(t.get("completion_percentage", 0.0))
        completed = t.get("completed", False) or (pct >= 100.0)
        rem_hrs = round(tot_hrs * (1.0 - (pct / 100.0)), 2)
        if completed or rem_hrs <= 0.0:
            continue

        try:
            d_date = datetime.date.fromisoformat(t.get("deadline"))
        except Exception:
            d_date = start_date

        p_info = priority_scores.get(t_id, {})
        rank = p_info.get("rank", 999)
        score = p_info.get("score", 0.0)

        active_tasks.append({
            "id": t_id,
            "name": t.get("name", "Untitled"),
            "category": t.get("category", "General"),
            "deadline": d_date,
            "remaining_hours": rem_hrs,
            "unscheduled_hours": rem_hrs,
            "rank": rank,
            "score": score,
            "difficulty": t.get("difficulty", "Medium"),
            "importance": t.get("importance", "Medium"),
        })

    # If no tasks require work
    if not active_tasks:
        return [], [], {
            "total_scheduled_hours": 0.0,
            "total_days_used": 0,
            "all_tasks_scheduled": True,
            "tasks_scheduled_past_deadline": 0,
        }

    # Sort tasks: highest score first, then earlier deadline
    active_tasks.sort(key=lambda x: (x["rank"], x["deadline"], -x["remaining_hours"]))

    daily_schedule: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    scheduled_tasks_after_deadline_set = set()

    current_date = start_date
    day_count = 0
    total_remaining_to_schedule = sum(t["unscheduled_hours"] for t in active_tasks)

    # Schedule day by day until all work is allocated or horizon limit reached
    while total_remaining_to_schedule > 0.001 and day_count < max_days_horizon:
        iso_date = current_date.isoformat()
        is_weekend = current_date.weekday() in (5, 6)
        day_name = current_date.strftime("%A")

        is_busy = iso_date in busy_days_set
        is_weekend_disabled = is_weekend and not include_weekends

        if is_busy:
            daily_schedule.append({
                "date": iso_date,
                "day_name": day_name,
                "is_busy": True,
                "is_weekend": is_weekend,
                "capacity_hours": 0.0,
                "allocated_hours": 0.0,
                "status": "BUSY",
                "notes": "Day marked as unavailable/busy by user.",
                "sessions": [],
            })
            current_date += datetime.timedelta(days=1)
            day_count += 1
            continue

        if is_weekend_disabled:
            daily_schedule.append({
                "date": iso_date,
                "day_name": day_name,
                "is_busy": False,
                "is_weekend": True,
                "capacity_hours": 0.0,
                "allocated_hours": 0.0,
                "status": "WEEKEND_OFF",
                "notes": "Weekend study disabled in preferences.",
                "sessions": [],
            })
            current_date += datetime.timedelta(days=1)
            day_count += 1
            continue

        # Day is available
        day_capacity = available_hours_per_day
        allocated_today = 0.0
        sessions: List[Dict[str, Any]] = []
        current_clock = preferred_start_time

        # Allocate time to active tasks
        # Dynamic prioritization: Give highest priority to tasks due today or overdue, then ranked order
        def sorting_key_for_day(task):
            is_overdue = task["deadline"] < current_date
            is_due_today = task["deadline"] == current_date
            # Overdue and due today jump to front
            if is_overdue:
                return (0, task["deadline"], task["rank"])
            if is_due_today:
                return (1, task["deadline"], task["rank"])
            return (2, task["deadline"], task["rank"])

        candidate_tasks = [t for t in active_tasks if t["unscheduled_hours"] > 0.001]
        candidate_tasks.sort(key=sorting_key_for_day)

        for task in candidate_tasks:
            if allocated_today >= day_capacity - 0.01:
                break

            time_left_today = round(day_capacity - allocated_today, 2)
            task_needs = round(task["unscheduled_hours"], 2)

            # Max chunk per session: let's avoid scheduling > 3.0h in one block unless task fits
            # If time left today is <= 2.5h, take all of it if needed
            chunk = min(time_left_today, task_needs)
            if chunk <= 0.01:
                continue

            # Check if this session is on or after the deadline
            is_after_deadline = current_date > task["deadline"]
            is_on_deadline = current_date == task["deadline"]

            if is_after_deadline:
                scheduled_tasks_after_deadline_set.add(task["id"])

            duration_mins = int(round(chunk * 60))
            end_clock = _add_minutes_to_time(current_clock, duration_mins)

            session_info = {
                "task_id": task["id"],
                "task_name": task["name"],
                "category": task["category"],
                "duration_hours": round(chunk, 2),
                "duration_minutes": duration_mins,
                "start_time": current_clock,
                "end_time": end_clock,
                "deadline": task["deadline"].isoformat(),
                "is_after_deadline": is_after_deadline,
                "is_on_deadline": is_on_deadline,
                "status_badge": "OVERDUE_RESCUE" if is_after_deadline else ("DUE_TODAY" if is_on_deadline else "ON_TRACK"),
            }
            sessions.append(session_info)

            allocated_today = round(allocated_today + chunk, 2)
            task["unscheduled_hours"] = round(task["unscheduled_hours"] - chunk, 2)

            # Add short 10-minute break between sessions if time remains today
            current_clock = _add_minutes_to_time(end_clock, 10)

        total_remaining_to_schedule = sum(t["unscheduled_hours"] for t in active_tasks)

        daily_schedule.append({
            "date": iso_date,
            "day_name": day_name,
            "is_busy": False,
            "is_weekend": is_weekend,
            "capacity_hours": day_capacity,
            "allocated_hours": allocated_today,
            "free_hours": round(day_capacity - allocated_today, 2),
            "status": "FULL" if allocated_today >= day_capacity - 0.01 else ("PARTIAL" if allocated_today > 0 else "FREE"),
            "notes": f"{len(sessions)} study session(s) scheduled ({allocated_today}h total).",
            "sessions": sessions,
        })

        current_date += datetime.timedelta(days=1)
        day_count += 1

    # Record conflicts for tasks that were scheduled past their deadline
    for task in active_tasks:
        t_id = task["id"]
        t_name = task["name"]
        d_str = task["deadline"].isoformat()

        if t_id in scheduled_tasks_after_deadline_set:
            conflicts.append({
                "type": "SCHEDULED_PAST_DEADLINE",
                "task_id": t_id,
                "task_name": t_name,
                "severity": "CRITICAL",
                "message": f"Task '{t_name}' could not be completed before its deadline ({d_str}). Part of the work was pushed into rescue sessions after the deadline.",
            })

        if task["unscheduled_hours"] > 0.01:
            conflicts.append({
                "type": "UNSCHEDULED_WORKLOAD_OVERFLOW",
                "task_id": t_id,
                "task_name": t_name,
                "severity": "CRITICAL",
                "message": f"Task '{t_name}' has {round(task['unscheduled_hours'], 2)}h unallocated because planning horizon ({max_days_horizon} days) capacity was exhausted.",
            })

    total_scheduled_hrs = round(sum(d.get("allocated_hours", 0.0) for d in daily_schedule), 2)
    days_used = len([d for d in daily_schedule if d.get("allocated_hours", 0.0) > 0])
    all_scheduled = all(t["unscheduled_hours"] <= 0.01 for t in active_tasks)

    stats = {
        "total_scheduled_hours": total_scheduled_hrs,
        "total_days_used": days_used,
        "all_tasks_scheduled": all_scheduled,
        "tasks_scheduled_past_deadline": len(scheduled_tasks_after_deadline_set),
        "unallocated_hours": round(sum(t["unscheduled_hours"] for t in active_tasks), 2),
    }

    return daily_schedule, conflicts, stats
