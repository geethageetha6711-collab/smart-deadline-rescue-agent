"""Gemini AI Integration and Deterministic Fallback Service."""
import os
import json
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("deadline_rescue_agent.llm")


def is_gemini_available() -> bool:
    """Checks if GEMINI_API_KEY is configured."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key and key != "your_gemini_api_key_here")


def get_gemini_model_name() -> str:
    """Returns configured Gemini model name."""
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"


def _generate_deterministic_insights(
    tasks: List[Dict[str, Any]],
    preferences: Dict[str, Any],
    daily_schedule: List[Dict[str, Any]],
    deadline_risks: Dict[str, Dict[str, Any]],
    priority_scores: Dict[str, Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    plan_status: str,
    optimization_attempts: int,
) -> Dict[str, Any]:
    """Generates comprehensive, explainable insights deterministically without LLM."""
    incomplete_tasks = [t for t in tasks if not t.get("completed", False) and float(t.get("completion_percentage", 0.0)) < 100.0]
    total_remaining_hours = sum(
        round(float(t.get("estimated_total_hours", 1.0)) * (1.0 - (float(t.get("completion_percentage", 0.0)) / 100.0)), 2)
        for t in incomplete_tasks
    )

    critical_tasks = [
        t.get("name") for t in incomplete_tasks
        if deadline_risks.get(str(t.get("id")), {}).get("risk_level") == "CRITICAL"
    ]
    high_tasks = [
        t.get("name") for t in incomplete_tasks
        if deadline_risks.get(str(t.get("id")), {}).get("risk_level") == "HIGH"
    ]

    # Executive Summary
    if not incomplete_tasks:
        exec_summary = "All academic tasks are marked 100% complete. No pending recovery schedule needed."
    elif plan_status == "FEASIBLE":
        exec_summary = (
            f"Recovery schedule is fully feasible! All {len(incomplete_tasks)} remaining tasks ({round(total_remaining_hours, 1)}h total) "
            f"can be completed on time within your daily study allocation of {preferences.get('available_hours_per_day', 4.0)}h/day."
        )
    elif plan_status == "OPTIMIZED":
        exec_summary = (
            f"Recovery plan was optimized across {optimization_attempts} adjustment cycles to eliminate bottlenecks. "
            f"{len(incomplete_tasks)} tasks scheduled within daily capacity limits."
        )
    else:
        exec_summary = (
            f"CRITICAL WARNING: The current schedule is infeasible without adjustments. You have {round(total_remaining_hours, 1)}h "
            f"of pending work with {len(critical_tasks)} critical task(s). Several deadlines cannot be met under current constraints."
        )

    # Priority Explanation
    ranked_explanations = []
    # Sort by rank
    sorted_tasks = sorted(
        incomplete_tasks,
        key=lambda x: priority_scores.get(str(x.get("id")), {}).get("rank", 999)
    )
    for t in sorted_tasks[:4]:
        p = priority_scores.get(str(t.get("id")), {})
        r_reasons = p.get("reasons", [])
        top_reason = r_reasons[0] if r_reasons else "High overall score"
        ranked_explanations.append(f"Rank #{p.get('rank', 1)} '{t.get('name')}': {top_reason}.")
    priority_explanation = " ".join(ranked_explanations) if ranked_explanations else "No pending tasks to prioritize."

    # Risk Summary
    if critical_tasks:
        risk_summary = f"{len(critical_tasks)} task(s) in CRITICAL risk ({', '.join(critical_tasks[:3])}). Immediate action is required."
    elif high_tasks:
        risk_summary = f"{len(high_tasks)} task(s) in HIGH risk ({', '.join(high_tasks[:3])}). Moderate buffer remains, but consistency is required."
    else:
        risk_summary = "All pending tasks have MODERATE or LOW deadline risks. Workload is well-paced."

    # Schedule Rationale
    days_used = len([d for d in daily_schedule if d.get("allocated_hours", 0) > 0])
    schedule_rationale = (
        f"The scheduler distributed work across {days_used} calendar day(s), strictly honoring your "
        f"{preferences.get('available_hours_per_day', 4.0)}h daily limit. High-priority and imminent tasks were given front-row time slots."
    )

    # Actionable Recommendations
    recommendations: List[str] = []
    if critical_tasks:
        recommendations.append(f"Urgent Focus: Dedicate today's first study block exclusively to '{critical_tasks[0]}'.")
        if conflicts:
            recommendations.append("Deadline Extension: Request a 24-48h extension on overdue or overloaded assignments.")
            recommendations.append("Capacity Increase: Temporarily increase daily study time by 1.5 - 2 hours to clear the backlog.")
    else:
        recommendations.append("Maintain Momentum: Stick strictly to the daily session start times.")
        recommendations.append("Study Pacing: Use 45-minute Pomodoro intervals with 10-minute breaks between scheduled sessions.")

    if preferences.get("busy_days"):
        recommendations.append(f"Unavailable Days Respected: Zero hours allocated on {len(preferences.get('busy_days'))} blacked-out day(s).")
    if not preferences.get("include_weekends", True):
        recommendations.append("Weekend Rest: Weekends are preserved with no academic study sessions scheduled.")

    # Alternatives & Trade-offs
    alternatives = None
    if conflicts:
        alternatives = (
            "Suggested Trade-offs: 1) Negotiate a deadline extension for low-importance tasks. "
            "2) Reduce scope on non-critical project components to save effort. "
            "3) Unlock weekend study sessions if currently disabled."
        )

    return {
        "source": "deterministic_engine",
        "model": "rule_based_fallback",
        "executive_summary": exec_summary,
        "priority_explanation": priority_explanation,
        "risk_summary": risk_summary,
        "schedule_rationale": schedule_rationale,
        "recommendations": recommendations,
        "trade_offs_and_alternatives": alternatives,
    }


def generate_ai_insights(
    tasks: List[Dict[str, Any]],
    preferences: Dict[str, Any],
    daily_schedule: List[Dict[str, Any]],
    deadline_risks: Dict[str, Dict[str, Any]],
    priority_scores: Dict[str, Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    plan_status: str,
    optimization_attempts: int = 0,
) -> Dict[str, Any]:
    """Generates AI insights using Google Gemini if available, or falls back deterministically."""
    if not is_gemini_available():
        res = _generate_deterministic_insights(
            tasks=tasks,
            preferences=preferences,
            daily_schedule=daily_schedule,
            deadline_risks=deadline_risks,
            priority_scores=priority_scores,
            conflicts=conflicts,
            plan_status=plan_status,
            optimization_attempts=optimization_attempts,
        )
        res["note"] = "Deterministic engine used (GEMINI_API_KEY not configured)."
        return res

    model_name = get_gemini_model_name()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2,
            timeout=12,
        )

        system_prompt = (
            "You are the reasoning engine of 'Smart Deadline Rescue Agent', an AI academic planning assistant. "
            "Provide insightful, concise, empathetic yet realistic guidance for the student. "
            "Do NOT invent tasks, numbers, or dates. Rely strictly on the computed facts provided. "
            "Return your response ONLY as valid JSON with these exact keys: "
            "executive_summary (string), priority_explanation (string), risk_summary (string), "
            "schedule_rationale (string), recommendations (list of strings), trade_offs_and_alternatives (string or null)."
        )

        facts_payload = {
            "tasks_count": len(tasks),
            "plan_status": plan_status,
            "optimization_attempts": optimization_attempts,
            "daily_capacity_hours": preferences.get("available_hours_per_day", 4.0),
            "conflicts_count": len(conflicts),
            "conflicts": [c.get("message") for c in conflicts[:5]],
            "top_priorities": [
                {
                    "name": t.get("name"),
                    "rank": priority_scores.get(str(t.get("id")), {}).get("rank"),
                    "score": priority_scores.get(str(t.get("id")), {}).get("score"),
                    "risk": deadline_risks.get(str(t.get("id")), {}).get("risk_level"),
                }
                for t in tasks if not t.get("completed", False)
            ][:5],
            "schedule_days_count": len(daily_schedule),
        }

        user_prompt = f"Analyze the following computed academic schedule data and produce student recommendations:\n{json.dumps(facts_payload, indent=2)}"

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        raw_text = response.content.strip()
        # Clean markdown codeblocks if model wraps output
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        parsed = json.loads(raw_text)

        return {
            "source": "gemini",
            "model": model_name,
            "executive_summary": parsed.get("executive_summary", ""),
            "priority_explanation": parsed.get("priority_explanation", ""),
            "risk_summary": parsed.get("risk_summary", ""),
            "schedule_rationale": parsed.get("schedule_rationale", ""),
            "recommendations": parsed.get("recommendations", []),
            "trade_offs_and_alternatives": parsed.get("trade_offs_and_alternatives"),
        }

    except Exception as e:
        logger.warning(f"Gemini API call failed or timed out: {e}. Falling back to deterministic engine.")
        fallback = _generate_deterministic_insights(
            tasks=tasks,
            preferences=preferences,
            daily_schedule=daily_schedule,
            deadline_risks=deadline_risks,
            priority_scores=priority_scores,
            conflicts=conflicts,
            plan_status=plan_status,
            optimization_attempts=optimization_attempts,
        )
        fallback["source"] = "deterministic_fallback"
        fallback["note"] = f"Deterministic fallback activated (Gemini query skipped or failed: {str(e)[:80]})."
        return fallback
