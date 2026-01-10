// State
let currentTab = 'today';
let rawData = { today: {}, tomorrow: {} };  // Raw modality data
let entriesData = { today: [], tomorrow: [] };  // Grouped by worker -> shifts (time-based)
let workerCounts = { today: {}, tomorrow: {} };  // Count entries per worker for duplicate detection
let currentEditEntry = null;
let dataLoaded = { today: false, tomorrow: false };  // Track which tabs have been loaded
let editMode = { today: false, tomorrow: false };  // Inline edit mode defaults to OFF - user decides which edit mode to use
let pendingChanges = { today: {}, tomorrow: {} };  // Track unsaved inline changes
let tableFilters = { today: { modality: '', skill: '', hideZero: false }, tomorrow: { modality: '', skill: '', hideZero: false } };
let displayOrder = 'modality-first';  // 'modality-first' or 'skill-first'
let sortState = { today: { column: 'worker', direction: 'asc' }, tomorrow: { column: 'worker', direction: 'asc' } };
let modalMode = 'edit';

// Add Worker Modal state
let addWorkerModalState = {
  tab: null,
  tasks: [],  // Array of { task, modality, start_time, end_time, modifier, skills }
  containerId: 'modal-content'
};

/**
 * Parse worker input like "Dr. Name (ID)" or just "ID".
 * Returns { id, fullName } where id is the canonical worker ID.
 */
function parseWorkerInput(inputValue) {
  const trimmed = (inputValue || '').trim();
  // Match pattern: "anything (ID)" where ID is inside parentheses
  const match = trimmed.match(/^(.+?)\s*\(([^)]+)\)$/);
  if (match) {
    return { id: match[2].trim(), fullName: trimmed };
  }
  // No parentheses - treat as plain ID
  return { id: trimmed, fullName: null };
}

/**
 * Get display name for a worker ID.
 * Returns "Full Name (ID)" format if name is known, otherwise just the ID.
 */
function getWorkerDisplayName(workerId) {
  const fullName = WORKER_NAMES[workerId];
  if (fullName && fullName !== workerId) {
    // If full name already contains the ID in parentheses, use it as-is
    if (fullName.includes('(' + workerId + ')')) {
      return fullName;
    }
    // Otherwise, append ID in parentheses
    return fullName + ' (' + workerId + ')';
  }
  return workerId;
}

/**
 * Get shift times from task config.
 * Structure: task.times = { default: "07:00-15:00", Freitag: "07:00-13:00", ... }
 * @param {Object} taskConfig - The task role configuration
 * @param {string} targetDay - German weekday name (Montag, Dienstag, etc.)
 * @returns {Object} { start: "07:00", end: "15:00" }
 */
function getShiftTimes(taskConfig, targetDay) {
  const defaultTimes = { start: '07:00', end: '15:00' };

  if (!taskConfig) return defaultTimes;

  const times = taskConfig.times || {};
  if (Object.keys(times).length === 0) return defaultTimes;

  // Check day-specific first, then 'friday' alias, then default
  let timeStr = times[targetDay] || times.default || '07:00-15:00';
  // Also check for 'friday' alias when targetDay is 'Freitag'
  if (targetDay === 'Freitag' && times.friday && !times.Freitag) {
    timeStr = times.friday;
  }
  const [start, end] = timeStr.split('-');
  return { start: start?.trim() || '07:00', end: end?.trim() || '15:00' };
}

// Active skill values for filtering - excludes 0 and -1 (only shows explicitly active workers)
const ACTIVE_SKILL_VALUES = new Set([1, '1', 'w', 'W']);

function normalizeSkillValueJS(value) {
  if (value === undefined || value === null) return 0;
  if (value === 'w' || value === 'W') return 'w';
  if (typeof value === 'string' && value.trim() === '') return 0;
  const parsed = parseInt(value, 10);
  if (!isNaN(parsed) && parsed === 2) return 'w';
  return isNaN(parsed) ? value : parsed;
}

function isWeightedSkill(value) {
  return value === 'w' || value === 'W' || value === 2;
}

function getModalShifts(group) {
  if (!group) return [];
  return group.modalShiftsArray || group.shiftsArray || [];
}

function displaySkillValue(value) {
  return isWeightedSkill(value) ? 'w' : value;
}

function isActiveSkillValue(value) {
  return ACTIVE_SKILL_VALUES.has(value);
}

// Check if skill value is non-negative (0, 1, or weighted)
function isNonNegativeSkillValue(value) {
  const v = normalizeSkillValueJS(value);
  return v === 0 || v === 1 || isWeightedSkill(v);
}

// Helper: Get shifts (type='shift')
function getShiftRoles() {
  return TASK_ROLES.filter(t => t.type === 'shift');
}

// Helper: Get gaps (type='gap')
function getGapTasks() {
  return TASK_ROLES.filter(t => t.type === 'gap');
}

// Helper: Get the target weekday name (German) based on current tab
// For "today" tab: use current day
// For "tomorrow" tab: use next workday (skip weekends)
function getTargetWeekdayName(tab) {
  const days = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
  const now = new Date();
  if (tab === 'today') {
    return days[now.getDay()];
  }
  // Tomorrow tab: calculate next workday
  let targetDate = new Date(now);
  targetDate.setDate(targetDate.getDate() + 1);
  // Skip Saturday and Sunday
  while (targetDate.getDay() === 0 || targetDate.getDay() === 6) {
    targetDate.setDate(targetDate.getDate() + 1);
  }
  return days[targetDate.getDay()];
}

// Helper: Check if a task name is a gap (using config, not string matching)
function isGapTask(taskName) {
  if (!taskName) return false;
  const gapTasks = getGapTasks();
  const taskLower = taskName.toLowerCase().trim();
  return gapTasks.some(g => g.name && g.name.toLowerCase().trim() === taskLower);
}

// Helper: Render task/role dropdown with optgroups for Shifts vs Gaps
function renderTaskOptionsWithGroups(selectedValue = '', includeGaps = false) {
  const shifts = getShiftRoles();
  const gaps = getGapTasks();

  let html = '<option value="">-- Select --</option>';

  // Shifts/Roles group
  if (shifts.length > 0) {
    html += '<optgroup label="Shifts / Roles">';
    shifts.forEach(t => {
      const selected = t.name === selectedValue ? 'selected' : '';
      const dataAttrs = `data-type="shift" data-modalities='${JSON.stringify(t.modalities || [])}' data-shift="${escapeHtml(t.shift || 'Fruehdienst')}" data-skills='${JSON.stringify(t.skill_overrides || {})}' data-modifier="${t.modifier || 1.0}"`;
      html += `<option value="${escapeHtml(t.name)}" ${dataAttrs} ${selected}>${escapeHtml(t.name)}</option>`;
    });
    html += '</optgroup>';
  }

  // Gaps/Tasks group (optional)
  if (includeGaps && gaps.length > 0) {
    html += '<optgroup label="Tasks / Gaps (makes -1)">';
    gaps.forEach(t => {
      const selected = t.name === selectedValue ? 'selected' : '';
      const dataAttrs = `data-type="gap" data-times='${JSON.stringify(t.times || {})}'`;
      html += `<option value="${escapeHtml(t.name)}" ${dataAttrs} ${selected}>${escapeHtml(t.name)}</option>`;
    });
    html += '</optgroup>';
  }

  return html;
}

// Get CSS class for skill value display
function getSkillClass(value) {
  const v = normalizeSkillValueJS(value);
  if (v === 1) return 'skill-val-1';
  if (v === 0) return 'skill-val-0';
  if (v === -1) return 'skill-val--1';
  if (isWeightedSkill(v)) return 'skill-val-w';
  return '';
}

// Get color for skill value - only 1 and w get strong colors, 0/-1 are neutral (from config)
function getSkillColor(value) {
  const v = normalizeSkillValueJS(value);
  if (v === 1) return SKILL_VALUE_COLORS.active?.color || '#28a745';
  if (isWeightedSkill(v)) return SKILL_VALUE_COLORS.weighted?.color || '#17a2b8';
  if (v === 0) return SKILL_VALUE_COLORS.passive?.color || '#ccc';
  if (v === -1) return SKILL_VALUE_COLORS.excluded?.color || '#ccc';
  return SKILL_VALUE_COLORS.passive?.color || '#ccc';
}

// Calculate aggregated proficiency class for a set of values
// Priority: Positive (1) values lead the coloring over negative (-1) values
function getAggregatedClass(values) {
  if (!values || values.length === 0) return 'agg-mixed';

  const normalized = values.map(v => normalizeSkillValueJS(v));
  const allOne = normalized.every(v => v === 1 || isWeightedSkill(v));  // Include weighted/freshman
  const anyOne = normalized.some(v => v === 1 || isWeightedSkill(v));
  const allZero = normalized.every(v => v === 0);
  const anyZero = normalized.some(v => v === 0);
  const allNeg = normalized.every(v => v === -1);

  // Positive values take priority - if any positive, show green colors
  if (allOne) return 'agg-all-1';
  if (anyOne) return 'agg-any-1';  // Any positive wins over negatives
  if (allZero) return 'agg-all-0';
  if (anyZero) return 'agg-any-0';
  if (allNeg) return 'agg-all-neg';
  return 'agg-mixed';
}

// Get display value for aggregated cell
function getAggregatedDisplay(values) {
  if (!values || values.length === 0) return '-';
  const normalized = values.map(v => normalizeSkillValueJS(v));
  const allSame = normalized.every(v => v === normalized[0]);
  if (allSame) return displaySkillValue(normalized[0]);
  // Show unique values sorted (w/1, 0, -1)
  const unique = [...new Set(normalized)].sort((a, b) => {
    const aVal = isWeightedSkill(a) ? 1 : a;
    const bVal = isWeightedSkill(b) ? 1 : b;
    return bVal - aVal;
  });
  return unique.map(displaySkillValue).join('/');
}

// Check if values contain weighted entries (skill='w')
function hasWeightedEntries(values) {
  return values && values.some(v => isWeightedSkill(v));
}

// Utility: Escape HTML to prevent XSS
function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}

// Helper functions for modality colors (from config)
function getModalityColor(modKey) {
  const settings = MODALITY_SETTINGS[modKey];
  return settings?.nav_color || '#6c757d';
}

function getModalityBgColor(modKey) {
  const settings = MODALITY_SETTINGS[modKey];
  return settings?.background_color || '#f8f9fa';
}
