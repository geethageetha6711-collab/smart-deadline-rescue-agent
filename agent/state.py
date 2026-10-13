from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel, Field, field_validator, model_validator
import datetime
import uuid


class TaskInput(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., min_length=1, description="Task or assignment name")
    category: str = Field(default="General", description="Subject or category")
    deadline: str = Field(..., description="Deadline date in YYYY-MM-DD format")
    estimated_total_hours: float = Field(..., gt=0, le=200, description="Estimated total work hours")
    completion_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage completed")
    difficulty: str = Field(default="Medium", description="Easy, Medium, Hard")
    importance: str = Field(default="Medium", description="Low, Medium, High")
    notes: Optional[str] = Field(default="", description="Optional task notes")
    completed: bool = Field(default=False, description="Whether task is completed")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        val = v.strip()
        if not val:
            raise ValueError("Task name cannot be empty or blank")
        return val

    @field_validator("deadline")
    @classmethod
    def validate_deadline_format(cls, v: str) -> str:
        try:
            datetime.date.fromisoformat(v)
        except ValueError:
            raise ValueError("Deadline must be a valid date in YYYY-MM-DD format")
        return v

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        norm = v.strip().capitalize()
        if norm not in ["Easy", "Medium", "Hard"]:
            return "Medium"
        return norm

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: str) -> str:
        norm = v.strip().capitalize()
        if norm not in ["Low", "Medium", "High"]:
            return "Medium"
        return norm

    @model_validator(mode="after")
    def sync_completion(self):
        if self.completion_percentage >= 100.0:
            self.completed = True
        elif self.completed and self.completion_percentage < 100.0:
            self.completion_percentage = 100.0
        return self


class PreferencesInput(BaseModel):
    available_hours_per_day: float = Field(default=4.0, gt=0, le=24, description="Available study hours per day")
    study_start_time: Optional[str] = Field(default="17:00", description="Preferred study start time, e.g. 17:00")
    busy_days: List[str] = Field(default_factory=list, description="Dates with 0 available study hours in YYYY-MM-DD")
    start_date: str = Field(default_factory=lambda: datetime.date.today().isoformat(), description="Planning start date (YYYY-MM-DD)")
    include_weekends: bool = Field(default=True, description="Whether weekends are available for studying")

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: str) -> str:
        try:
            datetime.date.fromisoformat(v)
        except ValueError:
            raise ValueError("Start date must be in YYYY-MM-DD format")
        return v

    @field_validator("busy_days")
    @classmethod
    def validate_busy_days(cls, v: List[str]) -> List[str]:
        cleaned = []
        for day in v:
            try:
                datetime.date.fromisoformat(day)
                cleaned.append(day)
            except ValueError:
                pass
        return cleaned


class CreatePlanRequest(BaseModel):
    tasks: List[TaskInput] = Field(..., min_length=1, description="List of tasks to schedule")
    preferences: Optional[PreferencesInput] = Field(default_factory=PreferencesInput)


class ReplanRequest(BaseModel):
    tasks: Optional[List[TaskInput]] = None
    preferences: Optional[PreferencesInput] = None
    change_description: Optional[str] = Field(default="Plan updated by user", description="Description of the change")


class CompleteTaskRequest(BaseModel):
    task_id: str
    completion_percentage: Optional[float] = 100.0


# LangGraph Shared Agent State TypedDict
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
    plan_status: str
    final_report: Dict[str, Any]
    history_changes: Optional[str]
