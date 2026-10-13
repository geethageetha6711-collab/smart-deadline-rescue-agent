/**
 * Smart Deadline Rescue Agent — Client Application
 * Handles task management, API interaction, adaptive replanning, and UI rendering.
 */

(function () {
  'use strict';

  // Application State
  const state = {
    tasks: [],
    preferences: {
      available_hours_per_day: 4.0,
      start_date: new Date().toISOString().split('T')[0],
      study_start_time: '17:00',
      busy_days: [],
      include_weekends: true,
    },
    currentSessionId: null,
    editingTaskId: null,
    lastPlanData: null,
  };

  // DOM Elements
  const elements = {
    // Preferences
    prefDailyHours: document.getElementById('pref-daily-hours'),
    prefStartDate: document.getElementById('pref-start-date'),
    prefStudyTime: document.getElementById('pref-study-time'),
    prefBusyDates: document.getElementById('pref-busy-dates'),
    prefIncludeWeekends: document.getElementById('pref-include-weekends'),

    // Task Form
    taskForm: document.getElementById('task-form'),
    taskId: document.getElementById('task-id'),
    taskName: document.getElementById('task-name'),
    taskCategory: document.getElementById('task-category'),
    taskDeadline: document.getElementById('task-deadline'),
    taskHours: document.getElementById('task-hours'),
    taskCompletion: document.getElementById('task-completion'),
    taskDifficulty: document.getElementById('task-difficulty'),
    taskImportance: document.getElementById('task-importance'),
    taskNotes: document.getElementById('task-notes'),
    formActionTitle: document.getElementById('form-action-title'),
    submitBtnText: document.getElementById('submit-btn-text'),
    cancelEditBtn: document.getElementById('cancel-edit-btn'),
    loadSampleBtn: document.getElementById('load-sample-btn'),

    // Task List
    taskListContainer: document.getElementById('task-list-container'),
    tasksEmptyState: document.getElementById('tasks-empty-state'),
    taskCount: document.getElementById('task-count'),
    clearAllBtn: document.getElementById('clear-all-btn'),
    generatePlanBtn: document.getElementById('generate-plan-btn'),

    // Metrics
    statTotalTasks: document.getElementById('stat-total-tasks'),
    statCompletedTasks: document.getElementById('stat-completed-tasks'),
    statCriticalTasks: document.getElementById('stat-critical-tasks'),
    statRemainingHours: document.getElementById('stat-remaining-hours'),
    statFeasibility: document.getElementById('stat-feasibility'),

    // Output Sections
    planActionBar: document.getElementById('plan-action-bar'),
    currentSessionId: document.getElementById('current-session-id'),
    lastChangeDesc: document.getElementById('last-change-desc'),
    downloadPdfBtn: document.getElementById('download-pdf-btn'),
    agentLoading: document.getElementById('agent-loading'),
    loadingIndicatorText: document.getElementById('loading-node-indicator'),

    conflictsCard: document.getElementById('conflicts-card'),
    conflictsList: document.getElementById('conflicts-list'),

    insightsCard: document.getElementById('insights-card'),
    insightsSourcePill: document.getElementById('insights-source-pill'),
    insightExecSummary: document.getElementById('insight-exec-summary'),
    insightPriorityText: document.getElementById('insight-priority-text'),
    insightAlternatives: document.getElementById('insight-alternatives'),
    alternativesBlock: document.getElementById('alternatives-block'),
    recommendationsList: document.getElementById('recommendations-list'),

    priorityCard: document.getElementById('priority-card'),
    priorityList: document.getElementById('priority-list'),

    scheduleCard: document.getElementById('schedule-card'),
    scheduleSummaryBadge: document.getElementById('schedule-summary-badge'),
    dailyScheduleTimeline: document.getElementById('daily-schedule-timeline'),
    outputPlaceholder: document.getElementById('output-placeholder'),

    // Workflow Modal
    viewWorkflowBtn: document.getElementById('view-workflow-btn'),
    workflowModal: document.getElementById('workflow-modal'),
    closeModalBtn: document.getElementById('close-modal-btn'),

    // Toast
    toast: document.getElementById('toast'),
  };

  // Initialize
  function init() {
    // Set default start date to today
    const todayStr = new Date().toISOString().split('T')[0];
    elements.prefStartDate.value = todayStr;
    elements.taskDeadline.value = todayStr;
    state.preferences.start_date = todayStr;

    bindEvents();
    renderTasks();
    updateMetrics();
  }

  // Event Listeners
  function bindEvents() {
    // Form submit
    elements.taskForm.addEventListener('submit', handleTaskSubmit);
    elements.cancelEditBtn.addEventListener('click', cancelEditing);
    elements.loadSampleBtn.addEventListener('click', loadSampleTasks);
    elements.clearAllBtn.addEventListener('click', clearAllTasks);
    elements.generatePlanBtn.addEventListener('click', handleGeneratePlan);
    elements.downloadPdfBtn.addEventListener('click', handleDownloadPdf);

    // Preferences change listeners
    elements.prefDailyHours.addEventListener('change', updatePreferencesFromUI);
    elements.prefStartDate.addEventListener('change', updatePreferencesFromUI);
    elements.prefStudyTime.addEventListener('change', updatePreferencesFromUI);
    elements.prefBusyDates.addEventListener('change', updatePreferencesFromUI);
    elements.prefIncludeWeekends.addEventListener('change', updatePreferencesFromUI);

    // Workflow modal
    elements.viewWorkflowBtn.addEventListener('click', () => elements.workflowModal.classList.remove('hidden'));
    elements.closeModalBtn.addEventListener('click', () => elements.workflowModal.classList.add('hidden'));
    elements.workflowModal.addEventListener('click', (e) => {
      if (e.target === elements.workflowModal) elements.workflowModal.classList.add('hidden');
    });
  }

  // Toast Helper
  function showToast(message, type = 'info') {
    elements.toast.textContent = message;
    elements.toast.className = `toast toast-${type}`;
    elements.toast.classList.remove('hidden');

    setTimeout(() => {
      elements.toast.classList.add('hidden');
    }, 4000);
  }

  // Update Preferences Object
  function updatePreferencesFromUI() {
    const hours = parseFloat(elements.prefDailyHours.value) || 4.0;
    const sDate = elements.prefStartDate.value || new Date().toISOString().split('T')[0];
    const sTime = elements.prefStudyTime.value || '17:00';
    const busyRaw = elements.prefBusyDates.value || '';
    const busyList = busyRaw
      .split(',')
      .map((s) => s.trim())
      .filter((s) => /^\d{4}-\d{2}-\d{2}$/.test(s));
    const weekends = elements.prefIncludeWeekends.checked;

    state.preferences = {
      available_hours_per_day: hours,
      start_date: sDate,
      study_start_time: sTime,
      busy_days: busyList,
      include_weekends: weekends,
    };

    // If an active session exists, trigger adaptive replanning
    if (state.currentSessionId) {
      replanCurrentSession('Study preferences updated (capacity or busy dates adjusted).');
    }
  }

  // Handle Add / Edit Task
  function handleTaskSubmit(e) {
    e.preventDefault();

    const name = elements.taskName.value.trim();
    if (!name) {
      showToast('Task name is required', 'error');
      return;
    }

    const category = elements.taskCategory.value.trim() || 'General';
    const deadline = elements.taskDeadline.value;
    const hours = parseFloat(elements.taskHours.value);
    const completion = parseFloat(elements.taskCompletion.value) || 0.0;
    const difficulty = elements.taskDifficulty.value;
    const importance = elements.taskImportance.value;
    const notes = elements.taskNotes.value.trim();

    if (isNaN(hours) || hours <= 0) {
      showToast('Estimated work hours must be greater than 0', 'error');
      return;
    }

    if (state.editingTaskId) {
      // Update existing task
      const targetIndex = state.tasks.findIndex((t) => t.id === state.editingTaskId);
      if (targetIndex !== -1) {
        state.tasks[targetIndex] = {
          ...state.tasks[targetIndex],
          name,
          category,
          deadline,
          estimated_total_hours: hours,
          completion_percentage: completion,
          completed: completion >= 100,
          difficulty,
          importance,
          notes,
        };
        showToast(`Task '${name}' updated successfully`, 'success');
      }
      cancelEditing();
    } else {
      // Add new task
      const newTask = {
        id: 't-' + Math.random().toString(36).substr(2, 7),
        name,
        category,
        deadline,
        estimated_total_hours: hours,
        completion_percentage: completion,
        completed: completion >= 100,
        difficulty,
        importance,
        notes,
      };
      state.tasks.push(newTask);
      showToast(`Added '${name}'`, 'success');
      resetForm();
    }

    renderTasks();
    updateMetrics();

    // Trigger adaptive replanning if session is active
    if (state.currentSessionId) {
      replanCurrentSession(`Task '${name}' modified or added.`);
    }
  }

  // Reset form
  function resetForm() {
    elements.taskId.value = '';
    elements.taskName.value = '';
    elements.taskHours.value = '';
    elements.taskCompletion.value = '0';
    elements.taskNotes.value = '';
    elements.taskForm.reset();

    // restore defaults
    const todayStr = state.preferences.start_date || new Date().toISOString().split('T')[0];
    elements.taskDeadline.value = todayStr;
    elements.taskCategory.value = 'Computer Science';
    elements.taskDifficulty.value = 'Medium';
    elements.taskImportance.value = 'Medium';
  }

  function cancelEditing() {
    state.editingTaskId = null;
    elements.formActionTitle.textContent = 'Add Academic Task';
    elements.submitBtnText.textContent = 'Add to Task List';
    elements.cancelEditBtn.classList.add('hidden');
    resetForm();
  }

  // Edit Task
  function editTask(taskId) {
    const task = state.tasks.find((t) => t.id === taskId);
    if (!task) return;

    state.editingTaskId = taskId;
    elements.taskId.value = task.id;
    elements.taskName.value = task.name;
    elements.taskCategory.value = task.category;
    elements.taskDeadline.value = task.deadline;
    elements.taskHours.value = task.estimated_total_hours;
    elements.taskCompletion.value = task.completion_percentage;
    elements.taskDifficulty.value = task.difficulty;
    elements.taskImportance.value = task.importance;
    elements.taskNotes.value = task.notes || '';

    elements.formActionTitle.textContent = 'Edit Task';
    elements.submitBtnText.textContent = 'Save Changes';
    elements.cancelEditBtn.classList.remove('hidden');

    elements.taskName.focus();
  }

  // Delete Task
  function deleteTask(taskId) {
    const task = state.tasks.find((t) => t.id === taskId);
    const taskName = task ? task.name : 'Task';

    state.tasks = state.tasks.filter((t) => t.id !== taskId);
    if (state.editingTaskId === taskId) {
      cancelEditing();
    }

    renderTasks();
    updateMetrics();
    showToast(`Removed '${taskName}'`, 'info');

    if (state.currentSessionId) {
      replanCurrentSession(`Task '${taskName}' removed from recovery list.`);
    }
  }

  // Toggle Complete Task
  async function toggleCompleteTask(taskId) {
    const task = state.tasks.find((t) => t.id === taskId);
    if (!task) return;

    const willBeCompleted = !task.completed;
    task.completed = willBeCompleted;
    task.completion_percentage = willBeCompleted ? 100.0 : 0.0;

    renderTasks();
    updateMetrics();

    if (state.currentSessionId) {
      try {
        setLoading(true, `Rebalancing schedule after updating '${task.name}'...`);
        const res = await fetch(`/plan/${state.currentSessionId}/complete-task`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_id: taskId,
            completion_percentage: task.completion_percentage,
          }),
        });

        if (!res.ok) throw new Error('Failed to update task completion');
        const planData = await res.json();
        renderPlanResults(planData);
        showToast(
          willBeCompleted ? `'${task.name}' marked complete!` : `'${task.name}' reopened for work`,
          'success'
        );
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        setLoading(false);
      }
    }
  }

  // Clear All Tasks
  function clearAllTasks() {
    if (!state.tasks.length) return;
    if (confirm('Clear all tasks from the list?')) {
      state.tasks = [];
      cancelEditing();
      renderTasks();
      updateMetrics();
      showToast('All tasks cleared', 'info');
    }
  }

  // Load Realistic Student Sample Tasks
  function loadSampleTasks() {
    const today = new Date();
    const addDays = (d) => {
      const target = new Date(today);
      target.setDate(target.getDate() + d);
      return target.toISOString().split('T')[0];
    };

    const samples = [
      {
        id: 't-sample-1',
        name: 'Operating Systems Lab Record & Plot Analysis',
        category: 'Operating Systems',
        deadline: addDays(1),
        estimated_total_hours: 4.0,
        completion_percentage: 25.0,
        difficulty: 'Hard',
        importance: 'High',
        notes: 'CPU scheduling algorithms and gantt chart verification',
        completed: false,
      },
      {
        id: 't-sample-2',
        name: 'Database Schema & Normalization Assignment',
        category: 'Databases',
        deadline: addDays(2),
        estimated_total_hours: 3.5,
        completion_percentage: 0.0,
        difficulty: 'Medium',
        importance: 'High',
        notes: 'BCNF and 3NF functional dependencies proof',
        completed: false,
      },
      {
        id: 't-sample-3',
        name: 'Computer Networks Quiz Review',
        category: 'Networks',
        deadline: addDays(3),
        estimated_total_hours: 2.0,
        completion_percentage: 50.0,
        difficulty: 'Easy',
        importance: 'Medium',
        notes: 'TCP/IP socket protocol headers',
        completed: false,
      },
      {
        id: 't-sample-4',
        name: 'AI Agent Architecture Project Milestone',
        category: 'Artificial Intelligence',
        deadline: addDays(4),
        estimated_total_hours: 6.0,
        completion_percentage: 10.0,
        difficulty: 'Hard',
        importance: 'High',
        notes: 'LangGraph multi-agent flow and state checkpointing',
        completed: false,
      },
    ];

    state.tasks = samples;
    renderTasks();
    updateMetrics();
    showToast('Loaded 4 realistic academic sample tasks!', 'success');
  }

  // Render Tasks List
  function renderTasks() {
    elements.taskCount.textContent = state.tasks.length;
    elements.generatePlanBtn.disabled = state.tasks.length === 0;

    if (state.tasks.length === 0) {
      elements.taskListContainer.innerHTML = '';
      elements.taskListContainer.appendChild(elements.tasksEmptyState);
      return;
    }

    elements.taskListContainer.innerHTML = '';

    state.tasks.forEach((task) => {
      const item = document.createElement('div');
      item.className = `task-item ${task.completed ? 'task-completed' : ''}`;

      const remHours = (task.estimated_total_hours * (1 - task.completion_percentage / 100)).toFixed(1);

      // Determine risk badge if last plan evaluated it
      let riskBadgeHtml = '';
      if (state.lastPlanData && state.lastPlanData.deadline_risks && state.lastPlanData.deadline_risks[task.id]) {
        const r = state.lastPlanData.deadline_risks[task.id];
        const rClass =
          r.risk_level === 'CRITICAL'
            ? 'badge-critical'
            : r.risk_level === 'HIGH'
            ? 'badge-high'
            : r.risk_level === 'MODERATE'
            ? 'badge-moderate'
            : 'badge-low';
        riskBadgeHtml = `<span class="badge ${rClass}">${r.risk_level}</span>`;
      }

      item.innerHTML = `
        <div class="task-item-header">
          <div class="task-item-title">${escapeHtml(task.name)}</div>
          <div>${riskBadgeHtml}</div>
        </div>
        <div class="task-item-meta">
          <span class="task-meta-tag">${escapeHtml(task.category)}</span>
          <span class="task-meta-tag">Due: ${task.deadline}</span>
          <span class="task-meta-tag">${task.difficulty}</span>
          <span class="task-meta-tag">${remHours}h left (${task.estimated_total_hours}h total)</span>
        </div>
        <div class="task-progress-bar-wrap">
          <div class="task-progress-fill" style="width: ${task.completion_percentage}%"></div>
        </div>
        <div class="task-item-actions">
          <button class="btn btn-secondary btn-xs btn-complete" data-id="${task.id}" title="${
        task.completed ? 'Reopen task' : 'Mark as complete'
      }">
            ${task.completed ? '↺ Reopen' : '✓ Done'}
          </button>
          <button class="btn btn-outline btn-xs btn-edit" data-id="${task.id}" title="Edit task">
            Edit
          </button>
          <button class="btn btn-text btn-xs text-danger btn-delete" data-id="${task.id}" title="Delete task">
            Delete
          </button>
        </div>
      `;

      item.querySelector('.btn-complete').addEventListener('click', () => toggleCompleteTask(task.id));
      item.querySelector('.btn-edit').addEventListener('click', () => editTask(task.id));
      item.querySelector('.btn-delete').addEventListener('click', () => deleteTask(task.id));

      elements.taskListContainer.appendChild(item);
    });
  }

  // Update Summary Metrics
  function updateMetrics() {
    const total = state.tasks.length;
    const completed = state.tasks.filter((t) => t.completed).length;

    let remHours = 0;
    state.tasks.forEach((t) => {
      if (!t.completed) {
        remHours += t.estimated_total_hours * (1 - t.completion_percentage / 100);
      }
    });

    elements.statTotalTasks.textContent = total;
    elements.statCompletedTasks.textContent = completed;
    elements.statRemainingHours.textContent = remHours.toFixed(1) + 'h';

    // Critical count from plan data if available
    let critCount = 0;
    if (state.lastPlanData && state.lastPlanData.deadline_risks) {
      Object.values(state.lastPlanData.deadline_risks).forEach((r) => {
        if (r.risk_level === 'CRITICAL') critCount++;
      });
    }
    elements.statCriticalTasks.textContent = critCount;

    if (state.lastPlanData && state.lastPlanData.plan_status) {
      elements.statFeasibility.textContent = state.lastPlanData.plan_status;
      elements.statFeasibility.className = `metric-value metric-status ${
        state.lastPlanData.plan_status === 'FEASIBLE'
          ? 'text-emerald'
          : state.lastPlanData.plan_status === 'OPTIMIZED'
          ? 'text-blue'
          : 'text-danger'
      }`;
    }
  }

  // Set Loading UI
  function setLoading(isLoading, message = 'Executing LangGraph nodes...') {
    if (isLoading) {
      elements.agentLoading.classList.remove('hidden');
      elements.loadingIndicatorText.textContent = message;
      elements.generatePlanBtn.disabled = true;
    } else {
      elements.agentLoading.classList.add('hidden');
      elements.generatePlanBtn.disabled = state.tasks.length === 0;
    }
  }

  // POST /plan
  async function handleGeneratePlan() {
    if (!state.tasks.length) {
      showToast('Please add at least one task first.', 'error');
      return;
    }

    updatePreferencesFromUI();
    setLoading(true, 'Running LangGraph: Analyzing deadline risks and constructing optimal schedule...');

    try {
      const response = await fetch('/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tasks: state.tasks,
          preferences: state.preferences,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Plan generation failed');
      }

      const planData = await response.json();
      state.currentSessionId = planData.session_id;
      renderPlanResults(planData);
      showToast('Smart Rescue Plan Generated Successfully!', 'success');
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }

  // POST /plan/{session_id}/replan
  async function replanCurrentSession(changeDescription) {
    if (!state.currentSessionId) return;

    setLoading(true, `Adaptive replanning: ${changeDescription}`);

    try {
      const response = await fetch(`/plan/${state.currentSessionId}/replan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tasks: state.tasks,
          preferences: state.preferences,
          change_description: changeDescription,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Replanning failed');
      }

      const planData = await response.json();
      renderPlanResults(planData);
      showToast('Plan updated and rebalanced!', 'info');
    } catch (err) {
      showToast(`Replanning error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }

  // Download PDF
  function handleDownloadPdf() {
    if (!state.currentSessionId) {
      showToast('Please generate a plan first.', 'error');
      return;
    }
    window.open(`/plan/${state.currentSessionId}/report`, '_blank');
  }

  // Render Plan Results
  function renderPlanResults(data) {
    state.lastPlanData = data;
    elements.outputPlaceholder.classList.add('hidden');
    elements.planActionBar.classList.remove('hidden');

    elements.currentSessionId.textContent = data.session_id;
    elements.lastChangeDesc.textContent = data.history_changes || 'Plan Active';

    // 1. Conflicts
    const conflicts = data.conflicts || [];
    if (conflicts.length > 0) {
      elements.conflictsCard.classList.remove('hidden');
      elements.conflictsList.innerHTML = conflicts
        .map(
          (c) =>
            `<li class="conflict-item"><b>[${escapeHtml(c.severity || 'WARNING')}]</b> ${escapeHtml(c.message)}</li>`
        )
        .join('');
    } else {
      elements.conflictsCard.classList.add('hidden');
    }

    // 2. Insights
    const report = data.final_report || {};
    elements.insightsCard.classList.remove('hidden');
    elements.insightsSourcePill.textContent = (report.source || 'DETERMINISTIC').toUpperCase();
    elements.insightExecSummary.textContent = report.executive_summary || 'Schedule generated successfully.';
    elements.insightPriorityText.textContent = report.priority_explanation || '';

    if (report.trade_offs_and_alternatives) {
      elements.alternativesBlock.classList.remove('hidden');
      elements.insightAlternatives.textContent = report.trade_offs_and_alternatives;
    } else {
      elements.alternativesBlock.classList.add('hidden');
    }

    const recs = report.recommendations || [];
    elements.recommendationsList.innerHTML = recs
      .map((r) => `<li class="rec-item">✓ ${escapeHtml(r)}</li>`)
      .join('');

    // 3. Priority Decisions
    const priorities = data.priority_scores || {};
    elements.priorityCard.classList.remove('hidden');

    const sortedPriorityEntries = Object.entries(priorities).sort(
      (a, b) => (a[1].rank || 999) - (b[1].rank || 999)
    );

    elements.priorityList.innerHTML = sortedPriorityEntries
      .map(([tId, p]) => {
        const task = state.tasks.find((t) => t.id === tId) || { name: 'Task ' + tId };
        const reasonsList = (p.reasons || [])
          .map((r) => `<li>${escapeHtml(r)}</li>`)
          .join('');

        return `
        <div class="priority-item">
          <div class="priority-header">
            <span class="priority-rank-badge">Rank #${p.rank || '-'} &bull; ${escapeHtml(task.name)}</span>
            <span class="priority-score-pill">Score: ${p.score} / 100 (${p.level})</span>
          </div>
          <ul class="priority-reasons">${reasonsList}</ul>
        </div>
      `;
      })
      .join('');

    // 4. Daily Schedule
    const schedule = data.daily_schedule || [];
    elements.scheduleCard.classList.remove('hidden');
    elements.scheduleSummaryBadge.textContent = `${schedule.length} Day(s)`;

    if (schedule.length === 0) {
      elements.dailyScheduleTimeline.innerHTML =
        '<p class="text-muted">All tasks completed. No pending study sessions.</p>';
    } else {
      elements.dailyScheduleTimeline.innerHTML = schedule
        .map((day) => {
          let sessionsHtml = '';

          if (day.is_busy) {
            sessionsHtml = '<p class="text-muted text-xs"><i>Busy / Unavailable Day (0h allocated)</i></p>';
          } else if (day.is_weekend && !state.preferences.include_weekends) {
            sessionsHtml = '<p class="text-muted text-xs"><i>Weekend Off (0h allocated)</i></p>';
          } else if (!day.sessions || day.sessions.length === 0) {
            sessionsHtml = '<p class="text-muted text-xs"><i>No study sessions scheduled for this day</i></p>';
          } else {
            sessionsHtml = day.sessions
              .map((s) => {
                const sClass = s.is_after_deadline
                  ? 'session-overdue'
                  : s.is_on_deadline
                  ? 'session-today'
                  : '';
                const overdueTag = s.is_after_deadline
                  ? '<span class="badge badge-critical" style="margin-left:6px">OVERDUE RESCUE</span>'
                  : '';

                return `
                <div class="session-block ${sClass}">
                  <span class="session-time">${s.start_time} - ${s.end_time}</span>
                  <div class="session-details">
                    <b>${escapeHtml(s.task_name)}</b> (${escapeHtml(s.category)}) ${overdueTag}
                  </div>
                  <span class="session-duration">${s.duration_hours}h</span>
                </div>
              `;
              })
              .join('');
          }

          return `
          <div class="day-timeline-card">
            <div class="day-header">
              <span class="day-title">${day.date} (${day.day_name})</span>
              <span class="day-capacity-chip">${day.allocated_hours}h / ${day.capacity_hours}h Capacity</span>
            </div>
            <div class="day-sessions-list">${sessionsHtml}</div>
          </div>
        `;
        })
        .join('');
    }

    renderTasks();
    updateMetrics();
  }

  // Security Helper
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Run init on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
