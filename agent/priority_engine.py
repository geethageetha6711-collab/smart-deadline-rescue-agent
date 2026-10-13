"""Priority Decision Engine for Smart Deadline Rescue Agent."""
from typing import List, Dict, Any


def calculate_priorities(
    tasks: List[Dict[str, Any]],
    deadline_risks: Dict[str, Dict[str, Any]],
    available_hours_per_day: float = 4.0,
) -> Dict[str, Dict[str, Any]]:
    """Calculates normalized priority scores (0-100), ranks, and explanations for tasks.
    
    Returns:
        mapping of task_id -> {
            "score": float,
            "rank": int,
            "level": str,
            "reasons": List[str],
            "breakdown": Dict[str, float]
        }
    """
    scored_items = []

    for t in tasks:
        t_id = str(t.get("id"))
        t_name = t.get("name", "Untitled")
        tot_hrs = float(t.get("estimated_total_hours", 1.0))
        pct = float(t.get("completion_percentage", 0.0))
        completed = t.get("completed", False) or (pct >= 100.0)
        rem_hrs = round(tot_hrs * (1.0 - (pct / 100.0)), 2)
        if completed or rem_hrs <= 0.0:
            rem_hrs = 0.0

        risk_info = deadline_risks.get(t_id, {})
        days_until = risk_info.get("days_until_deadline", 7)
        risk_level = risk_info.get("risk_level", "LOW")
        importance = str(t.get("importance", "Medium")).capitalize()
        difficulty = str(t.get("difficulty", "Medium")).capitalize()

        if completed:
            scored_items.append({
                "id": t_id,
                "name": t_name,
                "score": 0.0,
                "level": "COMPLETED",
                "reasons": ["Task is already completed."],
                "breakdown": {"urgency": 0, "workload": 0, "importance": 0, "risk_difficulty": 0},
                "days_until": days_until,
                "remaining_hours": 0.0,
            })
            continue

        # 1. Urgency Score (0 - 35)
        reasons: List[str] = []
        if risk_info.get("is_overdue", False) or days_until < 0:
            urgency_score = 35.0
            reasons.append("Overdue task needing immediate attention (+35 pts)")
        elif risk_info.get("is_due_today", False) or days_until == 0:
            urgency_score = 32.0
            reasons.append("Due today (+32 pts)")
        elif days_until == 1:
            urgency_score = 28.0
            reasons.append("Due tomorrow (+28 pts)")
        elif days_until == 2:
            urgency_score = 22.0
            reasons.append("Due in 2 days (+22 pts)")
        elif 3 <= days_until <= 4:
            urgency_score = 16.0
            reasons.append(f"Due in {days_until} days (+16 pts)")
        elif 5 <= days_until <= 7:
            urgency_score = 10.0
            reasons.append(f"Approaching deadline in {days_until} days (+10 pts)")
        else:
            urgency_score = max(3.0, 8.0 - (days_until - 7) * 0.5)
            reasons.append(f"Comfortable deadline ({days_until} days out)")

        # 2. Workload & Effort Impact (0 - 25)
        workload_ratio = rem_hrs / max(0.5, available_hours_per_day)
        if workload_ratio >= 2.0:
            workload_score = 25.0
            reasons.append(f"Heavy workload ({rem_hrs}h remaining demands >2 full study days) (+25 pts)")
        elif workload_ratio >= 1.0:
            workload_score = 18.0
            reasons.append(f"Substantial workload ({rem_hrs}h demands full study day) (+18 pts)")
        elif workload_ratio >= 0.5:
            workload_score = 12.0
            reasons.append(f"Moderate workload ({rem_hrs}h remaining) (+12 pts)")
        else:
            workload_score = 6.0
            reasons.append(f"Quick turnaround task ({rem_hrs}h remaining) (+6 pts)")

        # 3. Importance Weight (0 - 20)
        if importance == "High":
            importance_score = 20.0
            reasons.append("High academic importance (+20 pts)")
        elif importance == "Medium":
            importance_score = 12.0
            reasons.append("Standard academic importance (+12 pts)")
        else:
            importance_score = 5.0
            reasons.append("Lower urgency/importance tier (+5 pts)")

        # 4. Risk & Difficulty Factor (0 - 20)
        risk_map = {"CRITICAL": 14.0, "HIGH": 10.0, "MODERATE": 5.0, "LOW": 2.0}
        diff_map = {"Hard": 6.0, "Medium": 3.0, "Easy": 1.0}
        r_pts = risk_map.get(risk_level, 2.0)
        d_pts = diff_map.get(difficulty, 3.0)
        risk_diff_score = min(20.0, r_pts + d_pts)

        if risk_level in ("CRITICAL", "HIGH"):
            reasons.append(f"{risk_level} deadline risk factor (+{r_pts} pts)")
        if difficulty == "Hard":
            reasons.append("Hard difficulty subject requiring deep focus (+6 pts)")

        total_score = min(100.0, max(0.0, round(urgency_score + workload_score + importance_score + risk_diff_score, 1)))

        if total_score >= 80:
            level = "URGENT"
        elif total_score >= 60:
            level = "HIGH"
        elif total_score >= 35:
            level = "MEDIUM"
        else:
            level = "LOW"

        scored_items.append({
            "id": t_id,
            "name": t_name,
            "score": total_score,
            "level": level,
            "reasons": reasons,
            "breakdown": {
                "urgency": urgency_score,
                "workload": workload_score,
                "importance": importance_score,
                "risk_difficulty": risk_diff_score,
            },
            "days_until": days_until,
            "remaining_hours": rem_hrs,
        })

    # Sort: Incomplete tasks first sorted by score DESC, then earlier deadline, then higher remaining hours
    incomplete = [item for item in scored_items if item["level"] != "COMPLETED"]
    completed = [item for item in scored_items if item["level"] == "COMPLETED"]

    incomplete.sort(key=lambda x: (-x["score"], x["days_until"], -x["remaining_hours"]))
    completed.sort(key=lambda x: x["name"].lower())

    results: Dict[str, Dict[str, Any]] = {}
    current_rank = 1

    for item in incomplete:
        results[item["id"]] = {
            "score": item["score"],
            "rank": current_rank,
            "level": item["level"],
            "reasons": item["reasons"],
            "breakdown": item["breakdown"],
        }
        current_rank += 1

    for item in completed:
        results[item["id"]] = {
            "score": 0.0,
            "rank": current_rank,
            "level": "COMPLETED",
            "reasons": item["reasons"],
            "breakdown": item["breakdown"],
        }
        current_rank += 1

    return results
