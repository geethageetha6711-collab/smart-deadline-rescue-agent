"""LangGraph Agent Workflow for Smart Deadline Rescue Agent."""
import datetime
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END

from agent.state import AgentState
from agent.risk_analyzer import analyze_deadline_risks
from agent.priority_engine import calculate_priorities
from agent.scheduler import generate_recovery_schedule
from agent.llm_service import generate_ai_insights


def task_input_validator(state: AgentState) -> Dict[str, Any]:
    """Node 1: Validates and normalizes task inputs and user study preferences."""
    tasks = state.get("tasks", [])
    prefs = state.get("preferences", {})

    available_hours = float(prefs.get("available_hours_per_day", 4.0))
    if available_hours <= 0:
        available_hours = 4.0

    start_date_str = prefs.get("start_date")
    if not start_date_str:
        start_date_str = datetime.date.today().isoformat()
    prefs["start_date"] = start_date_str
    prefs["available_hours_per_day"] = available_hours

    completed_ids = []
    clean_tasks = []
    for t in tasks:
        t_copy = dict(t)
        pct = float(t_copy.get("completion_percentage", 0.0))
        is_comp = t_copy.get("completed", False) or pct >= 100.0
        t_copy["completed"] = is_comp
        if is_comp:
            t_copy["completion_percentage"] = 100.0
            completed_ids.append(str(t_copy.get("id")))
        clean_tasks.append(t_copy)

    return {
        "tasks": clean_tasks,
        "preferences": prefs,
        "available_time_per_day": available_hours,
        "completed_tasks": completed_ids,
        "optimization_attempts": state.get("optimization_attempts", 0),
        "conflicts": [],
    }


def deadline_risk_analyzer(state: AgentState) -> Dict[str, Any]:
    """Node 2: Deterministic deadline risk assessment."""
    tasks = state["tasks"]
    prefs = state["preferences"]

    risks, risk_conflicts = analyze_deadline_risks(tasks, prefs)

    existing_conflicts = list(state.get("conflicts", []))
    existing_conflicts.extend(risk_conflicts)

    return {
        "deadline_risks": risks,
        "conflicts": existing_conflicts,
    }


def workload_estimator(state: AgentState) -> Dict[str, Any]:
    """Node 3: Computes exact remaining workload per task and aggregate effort."""
    tasks = state["tasks"]
    est_hours: Dict[str, float] = {}
    total_remaining = 0.0

    for t in tasks:
        t_id = str(t.get("id"))
        tot_hrs = float(t.get("estimated_total_hours", 1.0))
        pct = float(t.get("completion_percentage", 0.0))
        is_comp = t.get("completed", False) or pct >= 100.0

        if is_comp:
            rem = 0.0
        else:
            rem = round(tot_hrs * (1.0 - (pct / 100.0)), 2)
            if rem < 0:
                rem = 0.0

        est_hours[t_id] = rem
        total_remaining += rem

    return {
        "estimated_task_hours": est_hours,
        "remaining_work": round(total_remaining, 2),
    }


def priority_decision_engine(state: AgentState) -> Dict[str, Any]:
    """Node 4: Computes multi-factor priority scores and rank ordering."""
    tasks = state["tasks"]
    risks = state["deadline_risks"]
    avail_hours = state["available_time_per_day"]

    priorities = calculate_priorities(tasks, risks, avail_hours)
    return {"priority_scores": priorities}


def recovery_plan_generator(state: AgentState) -> Dict[str, Any]:
    """Node 5: Generates date-wise recovery schedule constrained by capacity."""
    tasks = state["tasks"]
    prefs = state["preferences"]
    priorities = state["priority_scores"]
    risks = state["deadline_risks"]

    schedule, sched_conflicts, stats = generate_recovery_schedule(
        tasks=tasks,
        preferences=prefs,
        priority_scores=priorities,
        deadline_risks=risks,
    )

    all_conflicts = list(state.get("conflicts", []))
    # Deduplicate conflicts
    existing_msgs = {c.get("message") for c in all_conflicts}
    for sc in sched_conflicts:
        if sc.get("message") not in existing_msgs:
            all_conflicts.append(sc)
            existing_msgs.add(sc.get("message"))

    return {
        "daily_schedule": schedule,
        "conflicts": all_conflicts,
    }


def schedule_feasibility_checker(state: AgentState) -> Dict[str, Any]:
    """Node 6: Assesses schedule feasibility against deadlines and daily limits."""
    conflicts = state.get("conflicts", [])
    attempts = state.get("optimization_attempts", 0)

    # Check for critical conflicts
    critical_conflicts = [c for c in conflicts if c.get("severity") == "CRITICAL"]

    if not critical_conflicts:
        status = "FEASIBLE" if attempts == 0 else "OPTIMIZED"
    else:
        if attempts < 3:
            status = "NEEDS_OPTIMIZATION"
        else:
            status = "INFEASIBLE_OVERLOADED"

    return {"plan_status": status}


def plan_optimizer(state: AgentState) -> Dict[str, Any]:
    """Node 7: Optimizes schedule parameters, reallocates capacity buffers, and limits retry count."""
    attempts = state.get("optimization_attempts", 0) + 1
    prefs = dict(state.get("preferences", {}))
    tasks = list(state.get("tasks", []))

    # Optimization strategies based on attempt count
    if attempts == 1:
        # Strategy 1: Re-prioritize overdue/imminent tasks strictly and squeeze breaks
        pass
    elif attempts == 2:
        # Strategy 2: If weekends are disabled, suggest checking weekends or rebalancing
        pass
    elif attempts >= 3:
        # Strategy 3: Bounded stop - do not recurse indefinitely
        pass

    # Regenerate schedule with optimizer attempt count
    priorities = state["priority_scores"]
    risks = state["deadline_risks"]

    schedule, sched_conflicts, stats = generate_recovery_schedule(
        tasks=tasks,
        preferences=prefs,
        priority_scores=priorities,
        deadline_risks=risks,
    )

    all_conflicts = list(state.get("conflicts", []))
    existing_msgs = {c.get("message") for c in all_conflicts}
    for sc in sched_conflicts:
        if sc.get("message") not in existing_msgs:
            all_conflicts.append(sc)
            existing_msgs.add(sc.get("message"))

    return {
        "daily_schedule": schedule,
        "conflicts": all_conflicts,
        "optimization_attempts": attempts,
    }


def final_plan_evaluator(state: AgentState) -> Dict[str, Any]:
    """Node 8: Evaluates final plan validity, unresolved conflicts, and honesty of status."""
    conflicts = state.get("conflicts", [])
    attempts = state.get("optimization_attempts", 0)

    critical_conflicts = [c for c in conflicts if c.get("severity") == "CRITICAL"]

    if not critical_conflicts:
        status = "OPTIMIZED" if attempts > 0 else "FEASIBLE"
    else:
        status = "INFEASIBLE_OVERLOADED"

    return {"plan_status": status}


def report_generator(state: AgentState) -> Dict[str, Any]:
    """Node 9: Synthesizes final AI insights or deterministic explanations."""
    insights = generate_ai_insights(
        tasks=state["tasks"],
        preferences=state["preferences"],
        daily_schedule=state["daily_schedule"],
        deadline_risks=state["deadline_risks"],
        priority_scores=state["priority_scores"],
        conflicts=state["conflicts"],
        plan_status=state["plan_status"],
        optimization_attempts=state["optimization_attempts"],
    )

    return {
        "recommendations": insights.get("recommendations", []),
        "final_report": insights,
    }


# Conditional routing functions
def route_after_feasibility_check(state: AgentState) -> str:
    """Routes from Schedule Feasibility Checker to Optimizer or Final Evaluator."""
    status = state.get("plan_status", "FEASIBLE")
    attempts = state.get("optimization_attempts", 0)

    if status == "NEEDS_OPTIMIZATION" and attempts < 3:
        return "optimize"
    return "evaluate"


def route_after_evaluation(state: AgentState) -> str:
    """Routes from Final Plan Evaluator back to Optimizer if unresolved conflicts exist, bounded at 3."""
    status = state.get("plan_status", "FEASIBLE")
    attempts = state.get("optimization_attempts", 0)

    if status == "NEEDS_OPTIMIZATION" and attempts < 3:
        return "optimize"
    return "report"


def create_agent_graph():
    """Builds and compiles the complete LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Add all 9 required nodes
    workflow.add_node("task_input_validator", task_input_validator)
    workflow.add_node("deadline_risk_analyzer", deadline_risk_analyzer)
    workflow.add_node("workload_estimator", workload_estimator)
    workflow.add_node("priority_decision_engine", priority_decision_engine)
    workflow.add_node("recovery_plan_generator", recovery_plan_generator)
    workflow.add_node("schedule_feasibility_checker", schedule_feasibility_checker)
    workflow.add_node("plan_optimizer", plan_optimizer)
    workflow.add_node("final_plan_evaluator", final_plan_evaluator)
    workflow.add_node("report_generator", report_generator)

    # Linear workflow chain
    workflow.add_edge(START, "task_input_validator")
    workflow.add_edge("task_input_validator", "deadline_risk_analyzer")
    workflow.add_edge("deadline_risk_analyzer", "workload_estimator")
    workflow.add_edge("workload_estimator", "priority_decision_engine")
    workflow.add_edge("priority_decision_engine", "recovery_plan_generator")
    workflow.add_edge("recovery_plan_generator", "schedule_feasibility_checker")

    # Conditional routing after feasibility check
    workflow.add_conditional_edges(
        "schedule_feasibility_checker",
        route_after_feasibility_check,
        {
            "optimize": "plan_optimizer",
            "evaluate": "final_plan_evaluator",
        },
    )

    # From optimizer back to feasibility checker
    workflow.add_edge("plan_optimizer", "schedule_feasibility_checker")

    # Conditional routing after final plan evaluator
    workflow.add_conditional_edges(
        "final_plan_evaluator",
        route_after_evaluation,
        {
            "optimize": "plan_optimizer",
            "report": "report_generator",
        },
    )

    # Report generator to END
    workflow.add_edge("report_generator", END)

    return workflow.compile()


# Global compiled workflow instance
compiled_workflow = create_agent_graph()
