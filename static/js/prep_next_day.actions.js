function toggleDisplayOrder() {
  displayOrder = displayOrder === 'modality-first' ? 'skill-first' : 'modality-first';
  const newText = displayOrder === 'modality-first' ? 'Mod → Skill' : 'Skill → Mod';
  const newTitle = displayOrder === 'modality-first'
    ? 'Current: Modalities as groups, skills as sub-columns. Click to switch.'
    : 'Current: Skills as groups, modalities as sub-columns. Click to switch.';
  // Update both buttons (today and tomorrow tabs)
  ['display-order-toggle', 'display-order-toggle-tomorrow'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.textContent = newText;
      btn.title = newTitle;
    }
  });
  renderTable('today');
  renderTable('tomorrow');
}

function updateTableFilter(tab) {
  const hideZero = document.getElementById(`filter-hide-zero-${tab}`)?.checked || false;
  if (!tableFilters[tab]) {
    tableFilters[tab] = { modality: '', skill: '', hideZero };
  } else {
    tableFilters[tab].hideZero = hideZero;
  }
  renderTable(tab);
}

function filterByModality(tab, modality) {
  // Update button states
  const buttons = document.querySelectorAll(`[data-modality]`);
  buttons.forEach(btn => {
    if (btn.closest('.filter-bar') && btn.onclick && btn.onclick.toString().includes(`'${tab}'`)) {
      btn.classList.toggle('active', btn.getAttribute('data-modality') === modality);
    }
  });

  // Update filter and render
  const hideZero = document.getElementById(`filter-hide-zero-${tab}`)?.checked || false;
  tableFilters[tab] = {
    modality: modality.toLowerCase(),
    skill: tableFilters[tab]?.skill || '',
    hideZero
  };
  renderTable(tab);
}

function filterBySkill(tab, skill) {
  // Update button states
  const buttons = document.querySelectorAll(`[data-skill]`);
  buttons.forEach(btn => {
    if (btn.closest('.filter-bar') && btn.onclick && btn.onclick.toString().includes(`'${tab}'`)) {
      btn.classList.toggle('active', btn.getAttribute('data-skill') === skill);
    }
  });

  // Update filter and render
  const hideZero = document.getElementById(`filter-hide-zero-${tab}`)?.checked || false;
  tableFilters[tab] = {
    modality: tableFilters[tab]?.modality || '',
    skill: skill,
    hideZero
  };
  renderTable(tab);

  // Also filter the timeline (like on timetable page)
  const gridEl = document.getElementById(`timeline-grid-${tab}`);
  if (gridEl && typeof TimelineChart !== 'undefined') {
    TimelineChart.filterBySkill(gridEl, skill || 'all');
  }
}

// Toggle inline edit mode
function toggleEditMode(tab) {
  editMode[tab] = !editMode[tab];
  pendingChanges[tab] = {};  // Reset pending changes
  applyEditModeUI(tab);
  renderTable(tab);
}

// Track inline skill change (supports adding new modalities with rowIndex=-1)
function onInlineSkillChange(tab, modKey, rowIndex, skill, value, groupIdx, shiftIdx, el = null) {
  const normalizedVal = normalizeSkillValueJS(value);

  // Handle new modality additions (rowIndex = -1)
  if (rowIndex === -1) {
    const key = `new-${groupIdx}-${shiftIdx}-${modKey}`;
    if (!pendingChanges[tab][key]) {
      pendingChanges[tab][key] = { modality: modKey, row_index: -1, groupIdx, shiftIdx, isNew: true, updates: {} };
    }
    pendingChanges[tab][key].updates[skill] = normalizedVal;
    if (isWeightedSkill(normalizedVal)) {
      const currentWeight = el?.nextElementSibling ? parseFloat(el.nextElementSibling.value || '1.0') : 1.0;
      pendingChanges[tab][key].updates['Modifier'] = currentWeight;
    } else {
      delete pendingChanges[tab][key].updates['Modifier'];
    }
  } else {
    const key = `${modKey}-${rowIndex}`;
    if (!pendingChanges[tab][key]) {
      pendingChanges[tab][key] = { modality: modKey, row_index: rowIndex, updates: {} };
    }
    pendingChanges[tab][key].updates[skill] = normalizedVal;
    if (isWeightedSkill(normalizedVal)) {
      const currentWeight = el?.nextElementSibling ? parseFloat(el.nextElementSibling.value || '1.0') : 1.0;
      pendingChanges[tab][key].updates['Modifier'] = currentWeight;
    } else {
      delete pendingChanges[tab][key].updates['Modifier'];
    }
  }

  if (el && el.nextElementSibling) {
    el.nextElementSibling.style.display = isWeightedSkill(normalizedVal) ? '' : 'none';
  }

  // Update save button count
  const count = Object.keys(pendingChanges[tab]).length;
  const saveBtn = document.getElementById(`save-inline-btn-${tab}`);
  if (saveBtn) {
    saveBtn.textContent = `Save ${count} change${count > 1 ? 's' : ''}`;
  }
}

// Track inline modifier change per modality
function onInlineModifierChange(tab, modKey, rowIndex, value, groupIdx, shiftIdx) {
  const parsed = parseFloat(value) || 1.0;

  if (rowIndex === -1) {
    // New modality addition
    const key = `new-${groupIdx}-${shiftIdx}-${modKey}`;
    if (!pendingChanges[tab][key]) {
      pendingChanges[tab][key] = { modality: modKey, row_index: -1, groupIdx, shiftIdx, isNew: true, updates: {} };
    }
    pendingChanges[tab][key].updates['Modifier'] = parsed;
  } else {
    const key = `${modKey}-${rowIndex}`;
    if (!pendingChanges[tab][key]) {
      pendingChanges[tab][key] = { modality: modKey, row_index: rowIndex, updates: {} };
    }
    pendingChanges[tab][key].updates['Modifier'] = parsed;
  }

  // Update save button count
  const count = Object.keys(pendingChanges[tab]).length;
  const saveBtn = document.getElementById(`save-inline-btn-${tab}`);
  if (saveBtn) {
    saveBtn.textContent = `Save ${count} change${count > 1 ? 's' : ''}`;
  }
}

// Valid skill values for quick edit validation
const VALID_SKILL_VALUES = ['-1', '0', '1', 'w', 'W'];
const VALID_MODIFIER_VALUES = [0.5, 0.75, 1, 1.0, 1.25, 1.5];

// Validate and save skill input on blur
function validateAndSaveSkill(el) {
  const raw = (el.value || '').trim().toLowerCase();
  let normalized;

  // Validate input - only allow -1, 0, 1, w
  if (raw === '-1' || raw === '-') normalized = -1;
  else if (raw === '0' || raw === '') normalized = 0;
  else if (raw === '1') normalized = 1;
  else if (raw === 'w' || raw === '2') normalized = 'w';
  else {
    // Invalid - reset to 0
    normalized = 0;
    showMessage('error', 'Valid values: -1, 0, 1, w');
  }

  // Update display
  el.value = displaySkillValue(normalized);
  const color = getSkillColor(normalized);
  el.style.backgroundColor = color + '20';
  el.style.borderColor = color;

  // Trigger change tracking
  const { tab, mod, row, skill, gidx, sidx } = el.dataset;
  onInlineSkillChange(tab, mod, parseInt(row), skill, normalized, parseInt(gidx), parseInt(sidx), el);
}

// Handle keyboard shortcuts for skill input
function handleSkillKeydown(event, el) {
  if (event.key === 'Enter') {
    el.blur();
    event.preventDefault();
  } else if (event.key === 'Tab') {
    // Allow normal tab behavior
  } else if (event.key === 'ArrowUp') {
    // Cycle up (towards 1): -1 -> w -> 0 -> 1 -> -1
    // Order: 1, 0, w, -1
    const val = normalizeSkillValueJS(el.value);
    let next;
    if (val === -1) next = 'w';
    else if (isWeightedSkill(val)) next = 0;
    else if (val === 0) next = 1;
    else next = -1;
    el.value = displaySkillValue(next);
    validateAndSaveSkill(el);
    event.preventDefault();
  } else if (event.key === 'ArrowDown') {
    // Cycle down (towards -1): 1 -> 0 -> w -> -1 -> 1
    // Order: 1, 0, w, -1
    const val = normalizeSkillValueJS(el.value);
    let next;
    if (val === 1) next = 0;
    else if (val === 0) next = 'w';
    else if (isWeightedSkill(val)) next = -1;
    else next = 1;
    el.value = displaySkillValue(next);
    validateAndSaveSkill(el);
    event.preventDefault();
  }
}

// Validate and save modifier input on blur (per-modality)
function validateAndSaveModifier(el) {
  let parsed = parseFloat(el.value);

  // Validate - clamp to valid range
  if (isNaN(parsed) || parsed < 0.5) parsed = 0.5;
  else if (parsed > 1.5) parsed = 1.5;

  // Round to nearest valid value
  const validValues = [0.5, 0.75, 1.0, 1.25, 1.5];
  parsed = validValues.reduce((prev, curr) =>
    Math.abs(curr - parsed) < Math.abs(prev - parsed) ? curr : prev
  );

  el.value = parsed;

  // Trigger change tracking
  const { tab, mod, row, gidx, sidx } = el.dataset;
  onInlineModifierChange(tab, mod, parseInt(row), parsed, parseInt(gidx), parseInt(sidx));
}

// Validate and save shift-level modifier (applies to all modalities in the shift)
function validateAndSaveShiftModifier(el) {
  let parsed = parseFloat(el.value);

  // Validate - clamp to valid range
  if (isNaN(parsed) || parsed < 0.5) parsed = 0.5;
  else if (parsed > 1.5) parsed = 1.5;

  // Round to nearest valid value
  const validValues = [0.5, 0.75, 1.0, 1.25, 1.5];
  parsed = validValues.reduce((prev, curr) =>
    Math.abs(curr - parsed) < Math.abs(prev - parsed) ? curr : prev
  );

  el.value = parsed;

  // Trigger change tracking for ALL modalities in this shift
  const { tab, gidx, sidx } = el.dataset;
  onInlineShiftModifierChange(tab, parseInt(gidx), parseInt(sidx), parsed);

  // Update save button count
  const count = Object.keys(pendingChanges[tab]).length;
  const saveBtn = document.getElementById(`save-inline-btn-${tab}`);
  if (saveBtn) {
    saveBtn.textContent = `Save ${count} change${count > 1 ? 's' : ''}`;
  }
}

// Handle keyboard for modifier input
function handleModKeydown(event, el) {
  // Determine if this is shift-level (no mod attribute) or modality-level modifier
  const isShiftLevel = !el.dataset.mod;
  const saveFunction = isShiftLevel ? validateAndSaveShiftModifier : validateAndSaveModifier;

  if (event.key === 'Enter') {
    el.blur();
    event.preventDefault();
  } else if (event.key === 'ArrowUp') {
    const val = parseFloat(el.value) || 1.0;
    const validValues = [0.5, 0.75, 1.0, 1.25, 1.5];
    const idx = validValues.indexOf(val);
    const next = idx < validValues.length - 1 ? validValues[idx + 1] : validValues[validValues.length - 1];
    el.value = next;
    saveFunction(el);
    event.preventDefault();
  } else if (event.key === 'ArrowDown') {
    const val = parseFloat(el.value) || 1.0;
    const validValues = [0.5, 0.75, 1.0, 1.25, 1.5];
    const idx = validValues.indexOf(val);
    const next = idx > 0 ? validValues[idx - 1] : validValues[0];
    el.value = next;
    saveFunction(el);
    event.preventDefault();
  }
}

// Save all inline changes (handles both updates and new modality additions)
async function saveInlineChanges(tab) {
  const changes = Object.values(pendingChanges[tab]);
  if (changes.length === 0) {
    showMessage('error', 'No changes to save');
    return;
  }

  const updateEndpoint = tab === 'today' ? '/api/live-schedule/update-row' : '/api/prep-next-day/update-row';
  const addEndpoint = tab === 'today' ? '/api/live-schedule/add-worker' : '/api/prep-next-day/add-worker';

  // Collect errors instead of throwing on first failure
  const errors = [];
  let successCount = 0;

  for (const change of changes) {
    try {
      if (change.isNew) {
        // New modality addition - need to add via add-worker endpoint
        const group = entriesData[tab][change.groupIdx];
        const shift = group?.shiftsArray?.[change.shiftIdx];
        if (!group || !shift) continue;

        // Only add if any skill is set to 0/1/w (skip pure -1 placeholders)
        const hasActiveSkill = SKILLS.some(skill => {
          const val = change.updates[skill];
          return val !== undefined && isNonNegativeSkillValue(val);
        });
        if (!hasActiveSkill) continue;

        // Build worker_data for the new modality
        const workerData = {
          PPL: group.worker,
          start_time: shift.start_time,
          end_time: shift.end_time,
          Modifier: change.updates.Modifier || 1.0,
          tasks: shift.task || ''
        };
        // Get original skill values from the placeholder modality
        const originalSkills = shift.modalities[change.modality]?.skills || {};
        // Add all skills (preserve original values for unchanged skills)
        SKILLS.forEach(skill => {
          if (change.updates[skill] !== undefined) {
            workerData[skill] = change.updates[skill];
          } else {
            workerData[skill] = originalSkills[skill] !== undefined ? originalSkills[skill] : -1;
          }
        });

        const response = await fetch(addEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ modality: change.modality, worker_data: workerData })
        });

        if (!response.ok) {
          const result = await response.json().catch(() => ({}));
          errors.push(`Add ${change.modality}: ${result.error || 'Unknown error'}`);
        } else {
          successCount++;
        }
      } else {
        // Existing entry update
        const response = await fetch(updateEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(change)
        });

        if (!response.ok) {
          const result = await response.json().catch(() => ({}));
          errors.push(`Update ${change.modality}: ${result.error || 'Unknown error'}`);
        } else {
          successCount++;
        }
      }
    } catch (fetchError) {
      errors.push(`Network error: ${fetchError.message}`);
    }
  }

  // Show appropriate message based on results
  if (errors.length === 0) {
    showMessage('success', `Saved ${successCount} change${successCount !== 1 ? 's' : ''}`);
  } else if (successCount > 0) {
    showMessage('error', `Saved ${successCount}, failed ${errors.length}: ${errors[0]}`);
  } else {
    showMessage('error', `All ${errors.length} changes failed: ${errors[0]}`);
  }

  pendingChanges[tab] = {};
  applyEditModeUI(tab);
  await loadData();
}

// Update hours toggle label based on checkbox state
function updateHoursToggleLabel(checkbox) {
  const label = checkbox.nextElementSibling;
  if (label && label.classList.contains('hours-toggle-label')) {
    if (checkbox.checked) {
      label.textContent = 'Counts';
      label.classList.remove('no-count');
      label.classList.add('counts');
    } else {
      label.textContent = 'No count';
      label.classList.remove('counts');
      label.classList.add('no-count');
    }
  }
}

// Tab switching with lazy loading
async function switchTab(tab) {
  const previousTab = currentTab;
  currentTab = tab;
  document.getElementById('tab-today').className = tab === 'today' ? 'tab-btn active-today' : 'tab-btn';
  document.getElementById('tab-tomorrow').className = tab === 'tomorrow' ? 'tab-btn active-tomorrow' : 'tab-btn';
  document.getElementById('content-today').className = tab === 'today' ? 'tab-content active' : 'tab-content';
  document.getElementById('content-tomorrow').className = tab === 'tomorrow' ? 'tab-content active' : 'tab-content';

  // Preserve filter state when switching tabs
  if (previousTab && previousTab !== tab) {
    const prevFilter = tableFilters[previousTab];
    if (prevFilter) {
      // Copy filter state to new tab
      tableFilters[tab] = { ...prevFilter };

      // Update UI button states for new tab
      const hideZeroCheckbox = document.getElementById(`filter-hide-zero-${tab}`);

      // Update modality button states
      if (prevFilter.modality !== undefined) {
        const modalityButtons = document.querySelectorAll(`[data-modality]`);
        modalityButtons.forEach(btn => {
          if (btn.onclick && btn.onclick.toString().includes(`'${tab}'`)) {
            btn.classList.toggle('active', btn.getAttribute('data-modality') === prevFilter.modality);
          }
        });
      }

      // Update skill button states
      if (prevFilter.skill !== undefined) {
        const skillButtons = document.querySelectorAll(`[data-skill]`);
        skillButtons.forEach(btn => {
          if (btn.onclick && btn.onclick.toString().includes(`'${tab}'`)) {
            btn.classList.toggle('active', btn.getAttribute('data-skill') === prevFilter.skill);
          }
        });
      }

      if (hideZeroCheckbox && prevFilter.hideZero !== undefined) {
        hideZeroCheckbox.checked = prevFilter.hideZero;
      }
    }
  }

  // Lazy load data for the selected tab if not already loaded
  if (!dataLoaded[tab]) {
    await loadTabData(tab);
  }
}

// Load data for a specific tab (lazy loading)
async function loadTabData(tab) {
  try {
    const endpoint = tab === 'today' ? '/api/live-schedule/data' : '/api/prep-next-day/data';
    const response = await fetch(endpoint);

    if (!response.ok) {
      const text = await response.text();
      console.error(`${tab} API error:`, text);
      rawData[tab] = {};
      dataLoaded[tab] = false;
      return;
    }

    const contentType = response.headers.get('content-type');
    let respData;
    if (contentType && contentType.includes('application/json')) {
      respData = await response.json();
      rawData[tab] = respData.modalities || respData;
    } else {
      console.error(`${tab} API returned non-JSON`);
      rawData[tab] = {};
      dataLoaded[tab] = false;
      return;
    }

    const result = buildEntriesByWorker(respData.modalities || respData, tab);
    entriesData[tab] = result.entries;
    workerCounts[tab] = result.counts;
    dataLoaded[tab] = true;

    if (tab === 'tomorrow' && respData.last_prepped_at) {
      const infoEl = document.getElementById('last-prepped-info');
      if (infoEl) infoEl.innerHTML = `Vorbereitet am: <strong>${respData.last_prepped_at}</strong>`;
    } else if (tab === 'tomorrow') {
      const infoEl = document.getElementById('last-prepped-info');
      if (infoEl) infoEl.textContent = 'Noch nicht vorbereitet';
    }

    renderTable(tab);
    renderTimeline(tab);  // Update timeline chart
  } catch (error) {
    console.error(`Load error for ${tab}:`, error);
    showMessage('error', `Error loading ${tab} data: ${error.message}`);
    dataLoaded[tab] = false;
  }
}

// Load data for both tabs (used after mutations)
async function loadData() {
  // Reset loaded flags to force refresh
  dataLoaded.today = false;
  dataLoaded.tomorrow = false;

  // Load current tab first (visible to user)
  await loadTabData(currentTab);

  // Load other tab in background
  const otherTab = currentTab === 'today' ? 'tomorrow' : 'today';
  loadTabData(otherTab);  // Don't await - load in background
}

// Build grouped entries list: worker -> shifts (time-based) -> modality×skills matrix
// Merges split shifts back into connected work periods with gaps shown inline
function buildEntriesByWorker(data, tab = 'today') {
  const counts = {};
  const grouped = {};
  const targetDay = getTargetWeekdayName(tab);

  function mergeUniqueGaps(list) {
    const seen = new Set();
    const result = [];
    list.filter(Boolean).forEach(gap => {
      const key = `${gap.start || ''}-${gap.end || ''}-${gap.activity || ''}`;
      if (!seen.has(key)) {
        seen.add(key);
        result.push(gap);
      }
    });
    return result;
  }

  function deriveGapsFromSegments(segments) {
    const sorted = [...segments].sort((a, b) => (a.start || '').localeCompare(b.start || ''));
    const derived = [];
    for (let i = 1; i < sorted.length; i++) {
      const prev = sorted[i - 1];
      const curr = sorted[i];
      if (prev?.end && curr?.start && prev.end < curr.start) {
        derived.push({ start: prev.end, end: curr.start, activity: 'Gap' });
      }
    }
    return derived;
  }

  // First pass: collect all entries
  MODALITIES.forEach(mod => {
    const modData = Array.isArray(data[mod]) ? data[mod] : [];
    modData.forEach(row => {
      const workerName = row.PPL;
      counts[workerName] = (counts[workerName] || 0) + 1;

      // Parse task - handle both string and array formats
      let taskStr = row.tasks || '';
      if (Array.isArray(taskStr)) {
        taskStr = taskStr.filter(t => t && t.trim()).join(', ');
      }

      // Parse gaps from JSON if present
      let gaps = [];
      if (row.gaps) {
        try {
          gaps = typeof row.gaps === 'string' ? JSON.parse(row.gaps) : row.gaps;
        } catch (e) { gaps = []; }
      }

      // Check if this is a gap row using config (not string matching)
      const isGapRow = isGapTask(taskStr);

      // Pull default times from configured shifts/roles when missing
      const roleConfig = TASK_ROLES.find(t => t.name === taskStr);
      let startTime = row.start_time;
      let endTime = row.end_time;
      if ((!startTime || !endTime) && roleConfig) {
        if (isGapRow) {
          // Use 'times' field (unified with shifts)
          const times = roleConfig.times || {};
          const dayTimes = times[targetDay] || times.default;
          if (dayTimes) {
            // Handle both array format and string format
            const firstTime = Array.isArray(dayTimes) ? dayTimes[0] : dayTimes;
            if (firstTime) {
              [startTime, endTime] = firstTime.split('-');
            }
          }
        } else {
          // Use getShiftTimes helper for day-specific times
          const shiftTimes = getShiftTimes(roleConfig, targetDay);
          startTime = startTime || shiftTimes.start;
          endTime = endTime || shiftTimes.end;
        }
      }
      if (!startTime || !endTime) {
        [startTime, endTime] = isGapRow ? ['12:00', '13:00'] : ['07:00', '15:00'];
      }

      // Roster structure is modality-scoped: { modality: { skill: value } }
      const rosterPreset = (WORKER_SKILLS[workerName] || {});
      const rosterSkills = rosterPreset[mod] || {};

      // Get counts_for_hours from API response, or derive from task config
      let countsForHours = row.counts_for_hours;
      if (countsForHours === undefined) {
        // Derive from task config if not in API response
        countsForHours = roleConfig ? roleConfig.counts_for_hours : true;
      }

      const entry = {
        worker: workerName,
        modality: mod,
        row_index: row.row_index,
        start_time: startTime,
        end_time: endTime,
        modifier: row.Modifier !== undefined ? row.Modifier : 1.0,
        counts_for_hours: countsForHours !== false,  // Default true
        is_manual: Boolean(row.is_manual),
        gap_id: row.gap_id || null,
        gaps: gaps,
        skills: SKILLS.reduce((acc, skill) => {
          if (isGapRow) { acc[skill] = -1; return acc; }
          const rawVal = row[skill];
          const hasRaw = rawVal !== undefined && rawVal !== '';
          const fallback = rosterSkills[skill];
          const hasFallback = fallback !== undefined && fallback !== '';

          const normalizedRaw = hasRaw ? normalizeSkillValueJS(rawVal) : undefined;
          const normalizedFallback = hasFallback ? normalizeSkillValueJS(fallback) : undefined;

          acc[skill] = hasRaw
            ? normalizedRaw
            : (hasFallback ? normalizedFallback : 0);
          return acc;
        }, {}),
        task: taskStr
      };

      if (!grouped[workerName]) {
        grouped[workerName] = { worker: workerName, shifts: {}, allEntries: [], allGaps: [] };
      }
      grouped[workerName].allEntries.push(entry);
      const gapCandidates = [...gaps];
      if (isGapRow) {
        gapCandidates.push({ start: startTime, end: endTime, activity: taskStr });
      }
      grouped[workerName].allGaps = mergeUniqueGaps([...(grouped[workerName].allGaps || []), ...gapCandidates]);

      // Group by time slot (shift key = start_time-end_time)
      const shiftKey = `${entry.start_time}-${entry.end_time}`;
      if (!grouped[workerName].shifts[shiftKey]) {
        grouped[workerName].shifts[shiftKey] = {
          start_time: entry.start_time,
          end_time: entry.end_time,
          modifier: entry.modifier,
          counts_for_hours: entry.counts_for_hours,
          task: entry.task,
          gaps: gaps,
          modalities: {},
          timeSegments: [{ start: entry.start_time, end: entry.end_time }],
          originalShifts: [entry],
          is_manual: entry.is_manual,
          gap_id: entry.gap_id
        };
      }

      // Add this modality's skills to the shift
      const modKey = mod.toLowerCase();
      grouped[workerName].shifts[shiftKey].modalities[modKey] = {
        skills: entry.skills,
        row_index: entry.row_index,
        modifier: entry.modifier
      };

      // Merge tasks if different
      const existingTask = grouped[workerName].shifts[shiftKey].task;
      if (entry.task && existingTask && !existingTask.includes(entry.task)) {
        grouped[workerName].shifts[shiftKey].task = existingTask + ', ' + entry.task;
      } else if (entry.task && !existingTask) {
        grouped[workerName].shifts[shiftKey].task = entry.task;
      }
      // Merge gaps
      if (gaps.length > 0 && !grouped[workerName].shifts[shiftKey].gaps) {
        grouped[workerName].shifts[shiftKey].gaps = gaps;
      }
    });
  });

  // Ensure every shift carries all modalities so inline+modal edits can add missing ones
  Object.values(grouped).forEach(group => {
    const preset = WORKER_SKILLS[group.worker] || {};
    Object.values(group.shifts).forEach(shift => {
      MODALITIES.map(m => m.toLowerCase()).forEach(modKey => {
        if (!shift.modalities[modKey]) {
          const skills = {};
          // Default placeholders to -1 so new modality rows are opt-in
          // Roster structure is modality-scoped: { modality: { skill: value } }
          const rosterDefaults = preset[modKey] || {};
          SKILLS.forEach(skill => {
            const fallback = rosterDefaults[skill];
            skills[skill] = fallback !== undefined ? fallback : -1;
          });
          shift.modalities[modKey] = {
            skills,
            row_index: -1,
            modifier: shift.modifier || 1.0,
            placeholder: true
          };
        }
      });
    });
  });

  // Convert shifts to array and merge consecutive shifts with same task
  Object.values(grouped).forEach(group => {
    const shiftsArr = Object.entries(group.shifts)
      .map(([key, shift]) => ({ ...shift, shiftKey: key }))
      .sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));

    // Collect all gaps for this worker
    const workerGaps = group.allGaps || [];

    const hasWorkerGapBetween = (start, end) => {
      if (!start || !end) return false;
      return workerGaps.some(g => {
        const gapStart = g.start || '';
        const gapEnd = g.end || '';
        return gapStart < end && gapEnd >= start;
      });
    };

    // Merge consecutive shifts with same task (split shifts due to gaps)
    const mergedShifts = [];
    let currentMerged = null;

    shiftsArr.forEach(shift => {
      // Check if there's a gap between currentMerged.end_time and shift.start_time
      const hasGapBetween = currentMerged && (
        (shift.start_time || '') > (currentMerged.end_time || '') ||
        hasWorkerGapBetween(currentMerged.end_time, shift.start_time)
      );

      if (!currentMerged) {
        currentMerged = {
          ...shift,
          timeSegments: [{ start: shift.start_time, end: shift.end_time }],
          originalShifts: [shift],
          gaps: mergeUniqueGaps(shift.gaps || []),
          is_manual: shift.is_manual,
          gap_id: shift.gap_id
        };
      } else if (currentMerged.task === shift.task && hasGapBetween) {
        // Same task with gap between - merge into one work period
        currentMerged.timeSegments.push({ start: shift.start_time, end: shift.end_time });
        currentMerged.originalShifts.push(shift);
        currentMerged.end_time = shift.end_time;
        currentMerged.gaps = mergeUniqueGaps([...(currentMerged.gaps || []), ...(shift.gaps || [])]);
        currentMerged.is_manual = shift.is_manual || currentMerged.is_manual;
        currentMerged.gap_id = shift.gap_id || currentMerged.gap_id;
        // Merge modalities (prefer non-placeholder)
        Object.entries(shift.modalities).forEach(([modKey, modData]) => {
          if (!currentMerged.modalities[modKey] || currentMerged.modalities[modKey].placeholder) {
            currentMerged.modalities[modKey] = modData;
          }
        });
      } else {
        // Different task or no gap - save current and start new
        mergedShifts.push(currentMerged);
        currentMerged = {
          ...shift,
          timeSegments: [{ start: shift.start_time, end: shift.end_time }],
          originalShifts: [shift],
          gaps: mergeUniqueGaps(shift.gaps || []),
          is_manual: shift.is_manual,
          gap_id: shift.gap_id
        };
      }
    });
    if (currentMerged) mergedShifts.push(currentMerged);

    // Attach only the gaps that live inside each merged shift and derive implicit ones between segments
    group.shiftsArray = mergedShifts.map(shift => {
      const segments = (shift.timeSegments || []).sort((a, b) => (a.start || '').localeCompare(b.start || ''));
      const firstStart = segments[0]?.start || shift.start_time;
      const lastEnd = segments[segments.length - 1]?.end || shift.end_time;

      const gapsInRange = (workerGaps || [])
        .filter(g => {
          const gapStart = g.start || '';
          const gapEnd = g.end || '';
          return gapStart < (lastEnd || '') && gapEnd > (firstStart || '');
        })
        .map(g => {
          const gapStart = g.start || '';
          const gapEnd = g.end || '';
          const clippedStart = gapStart < (firstStart || '') ? firstStart : gapStart;
          const clippedEnd = gapEnd > (lastEnd || '') ? lastEnd : gapEnd;
          return { ...g, start: clippedStart, end: clippedEnd };
        });
      const derivedGaps = deriveGapsFromSegments(segments);
      const combinedGaps = mergeUniqueGaps([...(shift.gaps || []), ...gapsInRange, ...derivedGaps]);

      return {
        ...shift,
        start_time: firstStart,
        end_time: lastEnd,
        gaps: combinedGaps,
        timeSegments: segments
      };
    });
  });

  // Sort workers (default by name)
  const entries = Object.values(grouped).sort((a, b) => a.worker.localeCompare(b.worker));

  return { entries, counts };
}

// Track inline time change
function onInlineTimeChange(tab, groupIdx, shiftIdx, field, value) {
  const group = entriesData[tab][groupIdx];
  if (!group) return;
  const shift = group.shiftsArray?.[shiftIdx];
  if (!shift) return;

  // Update all modalities in this shift with new time
  Object.keys(shift.modalities).forEach(modKey => {
    const modData = shift.modalities[modKey];
    const key = `${modKey}-${modData.row_index}`;
    if (!pendingChanges[tab][key]) {
      pendingChanges[tab][key] = { modality: modKey, row_index: modData.row_index, updates: {} };
    }
    pendingChanges[tab][key].updates[field === 'start' ? 'start_time' : 'end_time'] = value;
  });
}

// Track inline modifier change for the whole shift (one modifier)
function onInlineShiftModifierChange(tab, groupIdx, shiftIdx, value) {
  const group = entriesData[tab][groupIdx];
  if (!group) return;
  const shift = group.shiftsArray?.[shiftIdx];
  if (!shift) return;

  const parsed = parseFloat(value);
  shift.modifier = parsed;

  Object.entries(shift.modalities).forEach(([modKey, modData]) => {
    if (modData.row_index === undefined || modData.row_index < 0) return;
    const key = `${modKey}-${modData.row_index}`;
    if (!pendingChanges[tab][key]) {
      pendingChanges[tab][key] = { modality: modKey, row_index: modData.row_index, updates: {} };
    }
    pendingChanges[tab][key].updates['Modifier'] = parsed;
  });
}

// Delete all entries for a worker
async function deleteWorkerEntries(tab, groupIdx) {
  const group = entriesData[tab][groupIdx];
  if (!group) return;

  const allEntries = group.allEntries || [];
  if (!confirm(`Delete all ${allEntries.length} entries for ${group.worker}?`)) return;

  const endpoint = tab === 'today' ? '/api/live-schedule/delete-worker' : '/api/prep-next-day/delete-worker';

  try {
    // Delete all entries in reverse order (to avoid index shifting issues)
    // Sort by row_index descending to delete from end first
    const sortedEntries = [...allEntries].sort((a, b) => b.row_index - a.row_index);
    for (const entry of sortedEntries) {
      await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modality: entry.modality, row_index: entry.row_index, verify_ppl: entry.worker })
      });
    }
    showMessage('success', `Deleted all entries for ${group.worker}`);
    await loadData();
  } catch (error) {
    showMessage('error', error.message);
  }
}

// Delete single entry
async function deleteEntry(tab, groupIdx, entryIdx) {
  const group = entriesData[tab][groupIdx];
  if (!group) return;
  const entry = group.entries[entryIdx];
  if (!entry) return;

  if (!confirm(`Delete entry for ${entry.worker} (${entry.modality.toUpperCase()} ${entry.start_time}-${entry.end_time})?`)) return;

  const endpoint = tab === 'today' ? '/api/live-schedule/delete-worker' : '/api/prep-next-day/delete-worker';

  try {
    await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modality: entry.modality, row_index: entry.row_index, verify_ppl: entry.worker })
    });
    showMessage('success', `Deleted entry for ${entry.worker}`);
    await loadData();
  } catch (error) {
    showMessage('error', error.message);
  }
}

// Open Edit modal for a worker - edit skills per modality
function openEditModal(tab, groupIdx) {
  const group = entriesData[tab][groupIdx];
  if (!group) return;

  currentEditEntry = { tab, groupIdx };
  renderEditModalContent();
  document.getElementById('edit-modal').classList.add('show');
}

// Handle task change in existing shift (edit modal)
function onEditShiftTaskChange(shiftIdx, taskName) {
  const taskConfig = TASK_ROLES.find(t => t.name === taskName);
  if (!taskConfig) return;

  const isGap = taskConfig.type === 'gap';
  const { tab, groupIdx } = currentEditEntry || {};

  if (isGap) {
    // Gap selected - set all skills to -1 and use times for target day
    const times = taskConfig.times || {};
    const targetDay = getTargetWeekdayName(tab || currentTab);
    const dayTimes = times[targetDay] || times.default;
    if (dayTimes) {
      // Handle both array format and string format
      const firstTime = Array.isArray(dayTimes) ? dayTimes[0] : dayTimes;
      if (firstTime) {
        const [startTime, endTime] = firstTime.split('-');
        const startEl = document.getElementById(`edit-shift-${shiftIdx}-start`);
        const endEl = document.getElementById(`edit-shift-${shiftIdx}-end`);
        if (startEl) startEl.value = startTime;
        if (endEl) endEl.value = endTime;
      }
    }
    const modifierEl = document.getElementById(`edit-shift-${shiftIdx}-modifier`);
    if (modifierEl) modifierEl.value = '1.0';

    // Set ALL skills to -1 for gaps across modalities
    MODALITIES.forEach(mod => {
      const modKey = mod.toLowerCase();
      SKILLS.forEach(skill => {
        const skillSelect = document.getElementById(`edit-shift-${shiftIdx}-${modKey}-skill-${skill}`);
        if (skillSelect) skillSelect.value = '-1';
      });
    });
  } else {
    // Regular shift selected - preload skills from task's skill_overrides (like CSV loading)
    const targetDay = getTargetWeekdayName(tab || currentTab);
    const times = getShiftTimes(taskConfig, targetDay);
    const startEl = document.getElementById(`edit-shift-${shiftIdx}-start`);
    const endEl = document.getElementById(`edit-shift-${shiftIdx}-end`);
    if (startEl) startEl.value = times.start;
    if (endEl) endEl.value = times.end;

    const modifierEl = document.getElementById(`edit-shift-${shiftIdx}-modifier`);
    if (modifierEl && taskConfig.modifier) modifierEl.value = taskConfig.modifier.toString();

    // Also update counts_for_hours based on task config
    const countsEl = document.getElementById(`edit-shift-${shiftIdx}-counts-hours`);
    if (countsEl) {
      countsEl.checked = taskConfig.counts_for_hours !== false;
      updateHoursToggleLabel(countsEl);
    }

    // Preload skills from task's skill_overrides (supports "Skill_modality" format like CSV loading)
    const overrides = taskConfig.skill_overrides || {};
    MODALITIES.forEach(mod => {
      const modKey = mod.toLowerCase();
      SKILLS.forEach(skill => {
        const skillSelect = document.getElementById(`edit-shift-${shiftIdx}-${modKey}-skill-${skill}`);
        if (skillSelect) {
          // Check for skill_modality format (e.g., "Notfall_ct") first, then skill-only
          const skillModKey = `${skill}_${modKey}`;
          let val = 0;  // Default to passive
          if (overrides[skillModKey] !== undefined) {
            val = overrides[skillModKey];
          } else if (overrides[skill] !== undefined) {
            val = overrides[skill];
          } else if (overrides['all'] !== undefined) {
            val = overrides['all'];
          }
          skillSelect.value = val.toString();
        }
      });
    });

    // Apply worker roster exclusions (-1) - roster -1 always wins
    // Roster structure is modality-scoped: { modality: { skill: value } }
    const group = entriesData[tab]?.[groupIdx];
    if (group) {
      const workerRoster = WORKER_SKILLS[group.worker];
      if (workerRoster) {
        MODALITIES.forEach(mod => {
          const modKey = mod.toLowerCase();
          const modalityRoster = workerRoster[modKey] || {};
          SKILLS.forEach(skill => {
            const skillSelect = document.getElementById(`edit-shift-${shiftIdx}-${modKey}-skill-${skill}`);
            if (skillSelect && modalityRoster[skill] === -1) {
              skillSelect.value = '-1';  // Roster -1 always wins
            }
          });
        });
      }
    }
  }
}

// Delete shift from edit modal
async function deleteShiftFromModal(shiftIdx) {
  const { tab, groupIdx } = currentEditEntry || {};
  const group = entriesData[tab]?.[groupIdx];
  if (!group) return;

  const shifts = group.shiftsArray || [];
  const shift = shifts[shiftIdx];
  if (!shift) return;

  if (!confirm(`Delete this shift (${shift.start_time}-${shift.end_time})?`)) return;

  const endpoint = tab === 'today' ? '/api/live-schedule/delete-worker' : '/api/prep-next-day/delete-worker';

  try {
    // Delete all modality entries for this shift
    for (const [modKey, modData] of Object.entries(shift.modalities)) {
      if (modData.row_index !== undefined && modData.row_index >= 0) {
        await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ modality: modKey, row_index: modData.row_index, verify_ppl: group.worker })
        });
      }
    }
    showMessage('success', 'Shift deleted');
    closeModal();
    await loadData();
  } catch (error) {
    showMessage('error', error.message);
  }
}

// Delete shift inline from quick edit mode
async function deleteShiftInline(tab, groupIdx, shiftIdx) {
  const group = entriesData[tab]?.[groupIdx];
  if (!group) return;

  const shifts = group.shiftsArray || [];
  const shift = shifts[shiftIdx];
  if (!shift) return;

  if (!confirm(`Delete this shift (${shift.start_time}-${shift.end_time})?`)) return;

  const endpoint = tab === 'today' ? '/api/live-schedule/delete-worker' : '/api/prep-next-day/delete-worker';

  try {
    // Delete all modality entries for this shift
    for (const [modKey, modData] of Object.entries(shift.modalities)) {
      if (modData.row_index !== undefined && modData.row_index >= 0) {
        await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ modality: modKey, row_index: modData.row_index, verify_ppl: group.worker })
        });
      }
    }
    showMessage('success', 'Shift deleted');
    await loadData();
  } catch (error) {
    showMessage('error', error.message);
  }
}

// Handle task change in modal add shift section
function onModalTaskChange() {
  const taskSelect = document.getElementById('modal-add-task');
  const option = taskSelect?.options[taskSelect.selectedIndex];
  if (!option || !option.value) {
    return;
  }

  const taskName = option.value;
  const taskConfig = TASK_ROLES.find(t => t.name === taskName);
  const isGap = option.dataset.type === 'gap';
  const { tab, groupIdx } = currentEditEntry || {};

  // Set times - use target day based on current tab (today vs tomorrow)
  const targetDay = getTargetWeekdayName(tab || currentTab);
  const times = taskConfig?.times || {};
  const dayTimes = times[targetDay] || times.default;

  if (isGap && dayTimes) {
    // Handle both array format and string format
    const firstTime = Array.isArray(dayTimes) ? dayTimes[0] : dayTimes;
    if (firstTime) {
      const [startTime, endTime] = firstTime.split('-');
      document.getElementById('modal-add-start').value = startTime;
      document.getElementById('modal-add-end').value = endTime;
    }
  } else if (!isGap && taskConfig) {
    // Use day-specific times from task config
    const times = getShiftTimes(taskConfig, targetDay);
    document.getElementById('modal-add-start').value = times.start;
    document.getElementById('modal-add-end').value = times.end;
  } else {
    // Fallback defaults
    const defaultTime = isGap ? '12:00-13:00' : '07:00-15:00';
    const [startTime, endTime] = defaultTime.split('-');
    document.getElementById('modal-add-start').value = startTime;
    document.getElementById('modal-add-end').value = endTime;
  }

  // Set modifier from task config
  const modifier = option.dataset.modifier || '1.0';
  document.getElementById('modal-add-modifier').value = modifier;

  // Update hours count checkbox based on task type
  const countsEl = document.getElementById('modal-add-counts-hours');
  if (countsEl) {
    countsEl.checked = isGap ? false : (taskConfig?.counts_for_hours !== false);
    updateHoursToggleLabel(countsEl);
  }

  // Preload skills from task's skill_overrides (supports "Skill_modality" format like CSV loading)
  const overrides = taskConfig?.skill_overrides || {};

  MODALITIES.forEach(mod => {
    const modKey = mod.toLowerCase();
    SKILLS.forEach(skill => {
      const el = document.getElementById(`modal-add-${modKey}-skill-${skill}`);
      if (!el) return;

      if (isGap) {
        el.value = '-1';  // All skills excluded for gaps
      } else {
        // Check for skill_modality format (e.g., "Notfall_ct") first, then skill-only
        const skillModKey = `${skill}_${modKey}`;
        let val = 0;  // Default to passive
        if (overrides[skillModKey] !== undefined) {
          val = overrides[skillModKey];
        } else if (overrides[skill] !== undefined) {
          val = overrides[skill];
        } else if (overrides['all'] !== undefined) {
          val = overrides['all'];
        }
        el.value = val.toString();
      }
    });
  });

  // Apply worker roster exclusions (-1) - roster -1 always wins
  // Roster structure is modality-scoped: { modality: { skill: value } }
  const group = entriesData[tab]?.[groupIdx];
  if (group) {
    const workerRoster = WORKER_SKILLS[group.worker];
    if (workerRoster) {
      MODALITIES.forEach(mod => {
        const modKey = mod.toLowerCase();
        const modalityRoster = workerRoster[modKey] || {};
        SKILLS.forEach(skill => {
          const el = document.getElementById(`modal-add-${modKey}-skill-${skill}`);
          if (el && modalityRoster[skill] === -1) {
            el.value = '-1';  // Roster -1 always wins
          }
        });
      });
    }
  }
}

// Initialize modal add-shift form with sensible defaults from config and roster
function initializeModalAddForm() {
  const taskSelect = document.getElementById('modal-add-task');
  if (!taskSelect) return;

  if (!taskSelect.value && taskSelect.options.length > 1) {
    taskSelect.selectedIndex = 1;
  }

  if (taskSelect.value) {
    onModalTaskChange();
  } else {
    // No task selected: still populate with roster defaults if present
    // Roster structure is modality-scoped: { modality: { skill: value } }
    const { tab, groupIdx } = currentEditEntry || {};
    const group = entriesData[tab]?.[groupIdx];
    const workerRoster = group ? WORKER_SKILLS[group.worker] : null;
    MODALITIES.forEach(mod => {
      const modKey = mod.toLowerCase();
      const modalitySkills = workerRoster ? (workerRoster[modKey] || {}) : {};
      SKILLS.forEach(skill => {
        const el = document.getElementById(`modal-add-${modKey}-skill-${skill}`);
        if (el) {
          const val = modalitySkills[skill] !== undefined ? modalitySkills[skill] : 0;
          el.value = val.toString();
        }
      });
    });
  }
}

// Add shift from modal (staged locally until Save)
async function addShiftFromModal() {
  const { tab, groupIdx } = currentEditEntry || {};
  const group = entriesData[tab]?.[groupIdx];
  if (!group) return;

  const taskSelect = document.getElementById('modal-add-task');
  const taskName = taskSelect?.value;
  if (!taskName) {
    showMessage('error', 'Please pick a role/task');
    return;
  }

  // All modalities are always active
  const selectedModalities = MODALITIES.map(m => m.toLowerCase());

  const startTime = document.getElementById('modal-add-start').value;
  const endTime = document.getElementById('modal-add-end').value;
  const modifier = parseFloat(document.getElementById('modal-add-modifier').value) || 1.0;
  const countsHoursEl = document.getElementById('modal-add-counts-hours');
  const countsForHours = countsHoursEl ? countsHoursEl.checked : true;
  const isGap = isGapTask(taskName);

  const workerEndpoint = tab === 'today' ? '/api/live-schedule/add-worker' : '/api/prep-next-day/add-worker';
  const gapEndpoint = tab === 'today' ? '/api/live-schedule/add-gap' : '/api/prep-next-day/add-gap';

  try {
    let overlapFound = false;

    // If it is a Gap task, check for overlaps with existing shifts
    if (isGap) {
      const shifts = group.shiftsArray || [];
      const start = startTime;
      const end = endTime;

      // Find overlapping shift (simple string comparison for HH:MM works for ISO times in same day)
      const targetShift = shifts.find(s => !(end <= s.start_time || start >= s.end_time));

      if (targetShift) {
        overlapFound = true;

        // Apply gap to all active modalities in this shift
        for (const [modKey, modData] of Object.entries(targetShift.modalities)) {
          // Check if this modality exists in the shift (row_index >= 0)
          if (modData.row_index !== undefined && modData.row_index >= 0) {
            const response = await fetch(gapEndpoint, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                modality: modKey,
                row_index: modData.row_index,
                gap_type: taskName,
                gap_start: startTime,
                gap_end: endTime
              })
            });

            if (!response.ok) {
              const errData = await response.json().catch(() => ({}));
              throw new Error(errData.error || `Failed to add gap for ${modKey.toUpperCase()}`);
            }
          }
        }
        showMessage('success', `Added gap to shift ${targetShift.start_time}-${targetShift.end_time}`);
      }
    }

    if (!overlapFound) {
      // Standard add-worker logic (new row) if no overlap or not a gap
      for (const modKey of selectedModalities) {
        const skills = {};
        SKILLS.forEach(skill => {
          const el = document.getElementById(`modal-add-${modKey}-skill-${skill}`);
          skills[skill] = normalizeSkillValueJS(el ? el.value : 0);
        });

        const response = await fetch(workerEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            modality: modKey,
            worker_data: {
              PPL: group.worker,
              start_time: startTime,
              end_time: endTime,
              Modifier: modifier,
              counts_for_hours: countsForHours,
              tasks: taskName,
              ...skills
            }
          })
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.error || `Failed to add shift for ${modKey.toUpperCase()}`);
        }
      }
      showMessage('success', `Added new ${isGap ? 'gap' : 'shift'} for ${group.worker}`);
    }

    await loadData();
    // Re-render modal to show updated shifts instead of closing
    renderEditModalContent();
  } catch (error) {
    showMessage('error', error.message);
  }
}

function onEditGapTypeChange() {
  const select = document.getElementById('edit-gap-type');
  const startInput = document.getElementById('edit-gap-start');
  const endInput = document.getElementById('edit-gap-end');

  if (!select.value) {
    startInput.disabled = true;
    endInput.disabled = true;
    return;
  }

  startInput.disabled = false;
  endInput.disabled = false;

  const option = select.options[select.selectedIndex];
  if (option.value !== 'custom' && option.dataset.times) {
    const times = JSON.parse(option.dataset.times);
    // Use target day based on current tab (today vs tomorrow)
    const { tab } = currentEditEntry || {};
    const targetDay = getTargetWeekdayName(tab || currentTab);
    const dayTimes = times[targetDay] || times.default;
    if (dayTimes) {
      const firstTime = Array.isArray(dayTimes) ? dayTimes[0] : dayTimes;
      if (firstTime) {
        const [start, end] = firstTime.split('-');
        startInput.value = start;
        endInput.value = end;
      }
    }
  }
}

function applySkillValues(skillMap = {}) {
  SKILLS.forEach(skill => {
    if (skillMap[skill] !== undefined) {
      const el = document.getElementById(`edit-skill-${skill}`);
      if (el) {
        el.value = skillMap[skill];
      }
    }
  });
}

function applyTaskSkillPreset() {
  const taskSelect = document.getElementById('edit-task');
  if (!taskSelect) return;
  const option = taskSelect.options[taskSelect.selectedIndex];
  if (!option || !option.dataset.skills) return;

  try {
    const skills = JSON.parse(option.dataset.skills) || {};
    applySkillValues(skills);

    // Also apply modifier from task config
    const taskName = option.value;
    const taskConfig = TASK_ROLES.find(t => t.name === taskName);
    if (taskConfig && taskConfig.modifier !== undefined) {
      const modifierSelect = document.getElementById('edit-modifier');
      if (modifierSelect) {
        modifierSelect.value = taskConfig.modifier.toString();
      }
    }
  } catch (err) {
    console.error('Failed to apply task skill preset', err);
  }
}

// Apply worker skill preset for a specific modality
function applyWorkerSkillPresetForModality(workerName, modKey) {
  const workerRoster = WORKER_SKILLS[workerName];
  if (!workerRoster) {
    showMessage('error', `No skill preset found for ${workerName}`);
    return;
  }

  // Roster structure is modality-scoped: { modality: { skill: value } }
  const modalitySkills = workerRoster[modKey] || {};

  SKILLS.forEach(skill => {
    const el = document.getElementById(`edit-${modKey}-skill-${skill}`);
    if (el && modalitySkills[skill] !== undefined) {
      // Limit roster presets to 0/-1; positive values are reserved for manual/CSV edits
      const val = modalitySkills[skill];
      el.value = (val > 0 ? 0 : val).toString();
    }
  });
}

// Apply worker skill preset for a specific modality in a specific shift
function applyWorkerSkillPresetForShiftModality(groupIdx, shiftIdx, modKey) {
  const { tab } = currentEditEntry || {};
  const group = entriesData[tab]?.[groupIdx];
  const workerName = group?.worker;
  const workerRoster = workerName ? WORKER_SKILLS[workerName] : null;
  if (!workerRoster) {
    showMessage('error', `No skill preset found for ${workerName || 'worker'}`);
    return;
  }

  // Roster structure is modality-scoped: { modality: { skill: value } }
  const modalitySkills = workerRoster[modKey] || {};

  SKILLS.forEach(skill => {
    const el = document.getElementById(`edit-shift-${shiftIdx}-${modKey}-skill-${skill}`);
    if (el && modalitySkills[skill] !== undefined) {
      // Limit roster presets to 0/-1; positive values are reserved for manual/CSV edits
      const val = modalitySkills[skill];
      el.value = (val > 0 ? 0 : val).toString();
    }
  });
}

// Apply preset from config to all modalities in a shift
function applyPresetToShift(shiftIdx, taskName) {
  if (!taskName) return;

  const task = TASK_ROLES.find(t => t.name === taskName);
  if (!task) {
    showMessage('error', `Preset not found: ${taskName}`);
    return;
  }

  const overrides = task.skill_overrides || {};
  const { tab, groupIdx } = currentEditEntry || {};
  const group = entriesData[tab]?.[groupIdx];
  if (!group) return;

  const shift = group.shiftsArray?.[shiftIdx];
  if (!shift) return;

  // Apply skills to all modalities in this shift
  // Config uses skill×modality format: { "Notfall_ct": 1, "Privat_mr": 0 }
  // Also supports shortcuts: { "all": -1 }, { "MSK-Haut": 1 }
  Object.keys(shift.modalities).forEach(modKey => {
    SKILLS.forEach(skill => {
      const el = document.getElementById(`edit-shift-${shiftIdx}-${modKey}-skill-${skill}`);
      if (el) {
        // Check skill×modality format first, then skill shortcut, then "all" shortcut
        const skillModKey = `${skill}_${modKey}`;
        let val = 0;  // Default to passive
        if (overrides[skillModKey] !== undefined) {
          val = overrides[skillModKey];
        } else if (overrides[skill] !== undefined) {
          val = overrides[skill];  // Skill shortcut applies to all modalities
        } else if (overrides['all'] !== undefined) {
          val = overrides['all'];
        }
        el.value = val.toString();
      }
    });
  });

  // Apply modifier if task has one (for weighted skills)
  if (task.modifier !== undefined) {
    const modifierEl = document.getElementById(`edit-shift-${shiftIdx}-modifier`);
    if (modifierEl) {
      modifierEl.value = task.modifier.toString();
    }
  }

  // Update shift times from task config (day-specific)
  const targetDay = getTargetWeekdayName(tab || currentTab);
  const times = getShiftTimes(task, targetDay);

  const startEl = document.getElementById(`edit-shift-${shiftIdx}-start`);
  const endEl = document.getElementById(`edit-shift-${shiftIdx}-end`);
  if (startEl) startEl.value = times.start;
  if (endEl) endEl.value = times.end;
}

// Apply worker roster skills to all modalities in a shift
function applyWorkerRosterToShift(shiftIdx) {
  const { tab, groupIdx } = currentEditEntry || {};
  const group = entriesData[tab]?.[groupIdx];
  if (!group) return;

  const workerRoster = WORKER_SKILLS[group.worker];
  if (!workerRoster) {
    showMessage('error', `No skill preset found for ${group.worker}`);
    return;
  }

  const shift = group.shiftsArray?.[shiftIdx];
  if (!shift) return;

  // Apply skills to all modalities in this shift
  // Roster structure is modality-scoped: { modality: { skill: value } }
  Object.keys(shift.modalities).forEach(modKey => {
    const modalitySkills = workerRoster[modKey] || {};

    SKILLS.forEach(skill => {
      const el = document.getElementById(`edit-shift-${shiftIdx}-${modKey}-skill-${skill}`);
      if (el && modalitySkills[skill] !== undefined) {
        // Limit roster presets to 0/-1; positive values are reserved for manual/CSV edits
        const val = modalitySkills[skill];
        el.value = (val > 0 ? 0 : val).toString();
      }
    });
  });
}

async function saveModalChanges() {
  if (!currentEditEntry) return;

  const { tab, groupIdx } = currentEditEntry;
  const group = entriesData[tab][groupIdx];
  if (!group) return;

  const updateEndpoint = tab === 'today' ? '/api/live-schedule/update-row' : '/api/prep-next-day/update-row';
  const shifts = group.shiftsArray || [];

  try {
    for (let shiftIdx = 0; shiftIdx < shifts.length; shiftIdx++) {
      const shift = shifts[shiftIdx];

      const shiftTaskEl = document.getElementById(`edit-shift-${shiftIdx}-task`);
      const shiftStartEl = document.getElementById(`edit-shift-${shiftIdx}-start`);
      const shiftEndEl = document.getElementById(`edit-shift-${shiftIdx}-end`);
      const shiftModifierEl = document.getElementById(`edit-shift-${shiftIdx}-modifier`);

      const shiftTask = shiftTaskEl ? shiftTaskEl.value : shift.task;
      const shiftStart = shiftStartEl ? shiftStartEl.value : shift.start_time;
      const shiftEnd = shiftEndEl ? shiftEndEl.value : shift.end_time;
      const shiftModifier = shiftModifierEl ? parseFloat(shiftModifierEl.value) || 1.0 : shift.modifier || 1.0;

      // Get counts_for_hours checkbox value
      const countsHoursEl = document.getElementById(`edit-shift-${shiftIdx}-counts-hours`);
      const countsForHours = countsHoursEl ? countsHoursEl.checked : (shift.counts_for_hours !== false);

      for (const [modKey, modData] of Object.entries(shift.modalities)) {
        const rowIndexEl = document.getElementById(`edit-shift-${shiftIdx}-${modKey}-rowindex`);
        const rowIndex = rowIndexEl ? parseInt(rowIndexEl.value) : modData.row_index;

        // Only update existing entries (rowIndex >= 0)
        // Modal no longer has modality enable/disable checkboxes
        if (rowIndex < 0) continue;

        const skillUpdates = {};
        SKILLS.forEach(skill => {
          const el = document.getElementById(`edit-shift-${shiftIdx}-${modKey}-skill-${skill}`);
          if (el) {
            skillUpdates[skill] = normalizeSkillValueJS(el.value);
          }
        });

        const updates = {
          start_time: shiftStart,
          end_time: shiftEnd,
          Modifier: shiftModifier,
          counts_for_hours: countsForHours,
          tasks: shiftTask,
          ...skillUpdates
        };
        const response = await fetch(updateEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ modality: modKey, row_index: rowIndex, updates })
        });
        if (!response.ok) {
          const result = await response.json();
          throw new Error(result.error || `Failed to update ${modKey.toUpperCase()} entry`);
        }
      }
    }

    closeModal();
    showMessage('success', 'Worker entries updated');
    await loadData();
  } catch (error) {
    showMessage('error', error.message);
  }
}

function closeModal() {
  document.getElementById('edit-modal').classList.remove('show');
  currentEditEntry = null;
}

// =============================================
// ADD WORKER MODAL FUNCTIONS
// =============================================

function openAddWorkerModal(tab) {
  addWorkerModalState.tab = tab;
  addWorkerModalState.tasks = [];
  // Start with one empty task
  addTaskToAddWorkerModal();
  renderAddWorkerModalContent();
  document.getElementById('add-worker-modal').classList.add('show');
  document.getElementById('add-worker-modal-title').textContent = tab === 'today' ? 'Add Worker (Today)' : 'Add Worker (Tomorrow)';
}

function closeAddWorkerModal() {
  document.getElementById('add-worker-modal').classList.remove('show');
  addWorkerModalState.tab = null;
  addWorkerModalState.tasks = [];
}

function addTaskToAddWorkerModal() {
  // Find default task to prefill (prefer shifts over gaps)
  const defaultTask = TASK_ROLES.find(t => t.type === 'shift') || TASK_ROLES[0] || {};

  // Get day-specific times from task config
  const targetDay = getTargetWeekdayName(addWorkerModalState.tab || currentTab);
  const times = getShiftTimes(defaultTask, targetDay);

  // Initialize skills per modality from task's skill_overrides
  const skillsByModality = {};
  MODALITIES.forEach(mod => {
    const modKey = mod.toLowerCase();
    skillsByModality[modKey] = {};
    SKILLS.forEach(skill => {
      // Check for skill_modality format (e.g., "Notfall_ct") first, then skill-only
      const skillModKey = `${skill}_${modKey}`;
      const overrides = defaultTask.skill_overrides || {};
      if (overrides[skillModKey] !== undefined) {
        skillsByModality[modKey][skill] = overrides[skillModKey];
      } else if (overrides[skill] !== undefined) {
        skillsByModality[modKey][skill] = overrides[skill];
      } else {
        skillsByModality[modKey][skill] = 0;  // Default to passive
      }
    });
  });

  addWorkerModalState.tasks.push({
    task: defaultTask.name || '',
    start_time: times.start,
    end_time: times.end,
    modifier: defaultTask.modifier || 1.0,
    counts_for_hours: defaultTask.counts_for_hours !== false,
    skillsByModality: skillsByModality
  });
}

function removeTaskFromAddWorkerModal(idx) {
  if (addWorkerModalState.tasks.length <= 1) {
    showMessage('error', 'At least one task is required');
    return;
  }
  addWorkerModalState.tasks.splice(idx, 1);
  renderAddWorkerModalContent();
}

function updateAddWorkerTask(idx, field, value) {
  if (!addWorkerModalState.tasks[idx]) return;
  addWorkerModalState.tasks[idx][field] = value;

  // If task changed, update times, modifier, and skills per modality (preload from config)
  if (field === 'task') {
    const taskConfig = TASK_ROLES.find(t => t.name === value);
    if (taskConfig) {
      const task = addWorkerModalState.tasks[idx];
      const isGap = taskConfig.type === 'gap';
      const overrides = taskConfig.skill_overrides || {};

      // Update counts_for_hours from task config
      task.counts_for_hours = taskConfig.counts_for_hours !== false;

      if (isGap) {
        // Gap selected - set all skills to -1 and use times for target day
        task.modifier = 1.0;
        task.counts_for_hours = false;  // Gaps typically don't count for hours

        // Get times for the target day (based on modal's tab)
        const times = taskConfig.times || {};
        const targetDay = getTargetWeekdayName(addWorkerModalState.tab || currentTab);
        const dayTimes = times[targetDay] || times.default;
        if (dayTimes) {
          const firstTime = Array.isArray(dayTimes) ? dayTimes[0] : dayTimes;
          if (firstTime) {
            const [startTime, endTime] = firstTime.split('-');
            task.start_time = startTime;
            task.end_time = endTime;
          }
        } else {
          task.start_time = '12:00';
          task.end_time = '13:00';
        }

        // Set ALL skills to -1 for gaps across all modalities
        MODALITIES.forEach(mod => {
          const modKey = mod.toLowerCase();
          if (!task.skillsByModality[modKey]) task.skillsByModality[modKey] = {};
          SKILLS.forEach(skill => {
            task.skillsByModality[modKey][skill] = -1;
          });
        });
      } else {
        // Regular shift selected - preload skills from task's skill_overrides (like CSV loading)
        const targetDay = getTargetWeekdayName(addWorkerModalState.tab || currentTab);
        const times = getShiftTimes(taskConfig, targetDay);
        task.start_time = times.start;
        task.end_time = times.end;
        task.modifier = taskConfig.modifier || 1.0;

        // Apply skill_overrides per modality (supports "Skill_modality" format like CSV loading)
        MODALITIES.forEach(mod => {
          const modKey = mod.toLowerCase();
          if (!task.skillsByModality[modKey]) task.skillsByModality[modKey] = {};
          SKILLS.forEach(skill => {
            // Check for skill_modality format (e.g., "Notfall_ct") first
            const skillModKey = `${skill}_${modKey}`;
            if (overrides[skillModKey] !== undefined) {
              task.skillsByModality[modKey][skill] = overrides[skillModKey];
            } else if (overrides[skill] !== undefined) {
              // Skill-only override applies to all modalities
              task.skillsByModality[modKey][skill] = overrides[skill];
            } else if (overrides['all'] !== undefined) {
              // "all" shortcut
              task.skillsByModality[modKey][skill] = overrides['all'];
            } else {
              task.skillsByModality[modKey][skill] = 0;  // Default to passive
            }
          });
        });

        // Apply worker roster exclusions (-1) - roster -1 always wins
        const workerInput = document.getElementById('add-worker-name-input');
        const inputValue = workerInput ? workerInput.value.trim() : '';
        const { id: workerId } = parseWorkerInput(inputValue);
        if (workerId && WORKER_SKILLS[workerId]) {
          applyRosterToSkillsByModality(task.skillsByModality, workerId);
        }
      }

      renderAddWorkerModalContent();
    }
  }
}

function updateAddWorkerSkill(idx, modality, skill, value) {
  if (!addWorkerModalState.tasks[idx]) return;
  const task = addWorkerModalState.tasks[idx];
  if (!task.skillsByModality[modality]) task.skillsByModality[modality] = {};
  const raw = (value || '').toString().trim();
  task.skillsByModality[modality][skill] = raw === 'w' ? 'w' : (parseInt(raw, 10) || 0);
}

// Helper: apply roster exclusions to skillsByModality (roster -1 always wins)
// Roster structure is modality-scoped: { modality: { skill: value } }
function applyRosterToSkillsByModality(skillsByModality, workerName) {
  if (!workerName || !WORKER_SKILLS[workerName]) return;
  const workerRoster = WORKER_SKILLS[workerName];
  MODALITIES.forEach(mod => {
    const modKey = mod.toLowerCase();
    if (!skillsByModality[modKey]) skillsByModality[modKey] = {};
    // Get roster skills for this specific modality
    const modalityRoster = workerRoster[modKey] || {};
    SKILLS.forEach(skill => {
      // Roster -1 always wins (cannot be overridden)
      if (modalityRoster[skill] === -1) {
        skillsByModality[modKey][skill] = -1;
      }
    });
  });
}

function onAddWorkerNameChange() {
  const workerInput = document.getElementById('add-worker-name-input');
  const inputValue = workerInput ? workerInput.value.trim() : '';

  // Parse "Full Name (ID)" format to extract the worker ID
  const { id: workerId } = parseWorkerInput(inputValue);

  if (workerId && WORKER_SKILLS[workerId]) {
    // Apply roster -1 values to all modalities in all tasks
    addWorkerModalState.tasks.forEach(task => {
      if (task.skillsByModality) {
        applyRosterToSkillsByModality(task.skillsByModality, workerId);
      }
    });
    renderAddWorkerModalContent();
  }
}

async function saveAddWorkerModal() {
  const workerInput = document.getElementById('add-worker-name-input');
  const inputValue = workerInput ? workerInput.value.trim() : '';

  if (!inputValue) {
    showMessage('error', 'Please enter a worker name');
    return;
  }

  // Parse "Full Name (ID)" format to extract the worker ID
  const { id: workerId } = parseWorkerInput(inputValue);

  if (addWorkerModalState.tasks.length === 0) {
    showMessage('error', 'Please add at least one task');
    return;
  }

  const { tab, tasks } = addWorkerModalState;
  const workerEndpoint = tab === 'today' ? '/api/live-schedule/add-worker' : '/api/prep-next-day/add-worker';
  const gapEndpoint = tab === 'today' ? '/api/live-schedule/add-gap' : '/api/prep-next-day/add-gap';

  try {
    // Group tasks into shifts vs gaps to handle ordering
    const normalTasks = [];
    const gapTasks = [];

    tasks.forEach(t => {
      if (isGapTask(t.task)) {
        gapTasks.push(t);
      } else {
        normalTasks.push(t);
      }
    });

    // Track new shifts: { start, end, modality, row_index }
    const addedShifts = [];

    // 1. Process Normal Tasks (Shifts/Roles) first
    // For each task, iterate through all modalities in skillsByModality
    for (const task of normalTasks) {
      const skillsByMod = task.skillsByModality || {};

      // Add entry for each modality that has at least one skill != -1
      for (const modKey of Object.keys(skillsByMod)) {
        const modSkills = skillsByMod[modKey];
        // Check if any skill is active (not all -1)
        const hasActiveSkill = Object.values(modSkills).some(v => v !== -1);
        if (!hasActiveSkill) continue;  // Skip modality if all skills are -1

        const response = await fetch(workerEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            modality: modKey,
            worker_data: {
              PPL: workerId,
              start_time: task.start_time,
              end_time: task.end_time,
              Modifier: task.modifier,
              counts_for_hours: task.counts_for_hours !== false,
              tasks: task.task,
              ...modSkills
            }
          })
        });

        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || 'Failed to add worker task');
        }

        // Capture new row info for gap checking
        if (result.row_index !== undefined) {
          addedShifts.push({
            start: task.start_time,
            end: task.end_time,
            modality: modKey,
            row_index: result.row_index
          });
        }
      }
    }

    // 2. Process Gap Tasks (check for overlaps)
    // For gaps, we need to check against all modalities
    const groups = entriesData[tab] || [];
    const existingGroup = groups.find(g => g.worker === workerId);

    for (const gap of gapTasks) {
      const gapStart = gap.start_time;
      const gapEnd = gap.end_time;
      const skillsByMod = gap.skillsByModality || {};

      // Process each modality in the gap
      for (const modKey of Object.keys(skillsByMod)) {
        let overlapFound = false;

        // A) Check against newly added shifts for this modality
        for (const shift of addedShifts) {
          if (shift.modality === modKey && !(gapEnd <= shift.start || gapStart >= shift.end)) {
            overlapFound = true;
            await callAddGap(gapEndpoint, shift.modality, shift.row_index, gap.task, gapStart, gapEnd);
          }
        }

        // B) Check against existing shifts (from entriesData)
        if (existingGroup && existingGroup.shiftsArray) {
          for (const shift of existingGroup.shiftsArray) {
            const modData = shift.modalities[modKey];
            if (modData && modData.row_index !== undefined && modData.row_index >= 0) {
              if (!(gapEnd <= shift.start_time || gapStart >= shift.end_time)) {
                overlapFound = true;
                await callAddGap(gapEndpoint, modKey, modData.row_index, gap.task, gapStart, gapEnd);
              }
            }
          }
        }

        // C) If no overlap and any skill is not -1, add as standalone row
        const modSkills = skillsByMod[modKey];
        const hasActiveSkill = Object.values(modSkills).some(v => v !== -1);
        if (!overlapFound && hasActiveSkill) {
          const response = await fetch(workerEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              modality: modKey,
              worker_data: {
                PPL: workerId,
                start_time: gapStart,
                end_time: gapEnd,
                Modifier: gap.modifier,
                counts_for_hours: false, // Gaps usually don't count
                tasks: gap.task,
                ...modSkills
              }
            })
          });

          if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || 'Failed to add gap task');
          }
        }
      }
    }

    closeAddWorkerModal();
    showMessage('success', `${getWorkerDisplayName(workerId)} added/updated`);
    await loadData();
  } catch (error) {
    showMessage('error', error.message);
  }
}

// Helper wrapper for adding gap
async function callAddGap(endpoint, modality, rowIndex, type, start, end) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      modality: modality,
      row_index: rowIndex,
      gap_type: type,
      gap_start: start,
      gap_end: end
    })
  });
  if (!response.ok) {
    const res = await response.json().catch(() => ({}));
    // Log error but continue? Or throw?
    console.error('Gap add failed:', res.error);
    throw new Error(res.error || 'Failed to add overlapping gap');
  }
}

// =============================================
// END ADD WORKER MODAL FUNCTIONS
// =============================================


// =============================================
// QUICK BREAK NOW FEATURE
// =============================================

/**
 * Add a break (gap) starting NOW for a worker.
 * Uses add-gap API to split existing shifts at the break time.
 * Falls back to standalone gap entry if no shift exists at that time.
 */
async function onQuickGap30(tab, gIdx, shiftIdx) {
  const group = entriesData[tab][gIdx];
  if (!group) {
    showMessage('error', 'Invalid worker group');
    return;
  }

  // Get current time (exact minute)
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  const gapStart = formatMinutesToTime(currentMinutes);
  const gapEnd = addMinutes(gapStart, QUICK_BREAK.duration_minutes);
  const gapType = QUICK_BREAK.gap_type || 'Break';

  // Find shifts that overlap with the gap time
  const shifts = group.shiftsArray || [];
  const overlappingShifts = shifts.filter(s => {
    const shiftStart = s.start_time || '00:00';
    const shiftEnd = s.end_time || '23:59';
    return gapStart < shiftEnd && gapEnd > shiftStart;
  });

  // If not in edit mode, show confirmation popup
  if (!editMode[tab]) {
    let msg = `Add ${QUICK_BREAK.duration_minutes}-min break for ${group.worker}?\n\nTime: ${gapStart} - ${gapEnd}`;
    if (overlappingShifts.length > 0) {
      msg += `\n\nWill split shift(s) at break time.`;
    } else {
      msg += `\n\nNo shift at this time - will create gap entry.`;
    }
    if (!confirm(msg)) return;
  }

  try {
    if (overlappingShifts.length > 0) {
      // Use add-gap API to split existing shifts
      const gapEndpoint = tab === 'today' ? '/api/live-schedule/add-gap' : '/api/prep-next-day/add-gap';

      for (const shift of overlappingShifts) {
        // Get all modalities with valid row_index for this shift
        const modKeys = MODALITIES.map(m => m.toLowerCase()).filter(modKey => {
          const modData = shift.modalities[modKey];
          return modData && modData.row_index !== undefined && modData.row_index >= 0;
        });

        for (const modKey of modKeys) {
          const modData = shift.modalities[modKey];
          await callAddGap(gapEndpoint, modKey, modData.row_index, gapType, gapStart, gapEnd);
        }
      }

      showMessage('success', `Added break (${gapStart}-${gapEnd}) for ${group.worker} - shift split`);
    } else {
      // No overlapping shift - create standalone gap entry
      const addEndpoint = tab === 'today' ? '/api/live-schedule/add-worker' : '/api/prep-next-day/add-worker';
      const skills = {};
      SKILLS.forEach(skill => { skills[skill] = -1; });

      const response = await fetch(addEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          modality: MODALITIES[0].toLowerCase(),
          ppl_name: group.worker,
          start_time: gapStart,
          end_time: gapEnd,
          modifier: 1.0,
          counts_for_hours: false,
          tasks: gapType,
          ...skills
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to create gap');
      }

      showMessage('success', `Added break (${gapStart}-${gapEnd}) for ${group.worker}`);
    }

    await loadData();
  } catch (error) {
    showMessage('error', error.message || 'Failed to add break');
  }
}

/** Format total minutes to HH:MM string */
function formatMinutesToTime(totalMinutes) {
  const hours = Math.floor(totalMinutes / 60) % 24;
  const mins = totalMinutes % 60;
  return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
}

/** Add minutes to a time string (HH:MM format) */
function addMinutes(timeStr, minutes) {
  const [hours, mins] = timeStr.split(':').map(Number);
  return formatMinutesToTime(hours * 60 + mins + minutes);
}

/** Called from edit modal - uses currentEditEntry context */
async function onQuickGapFromModal() {
  if (!currentEditEntry) {
    showMessage('error', 'No entry selected');
    return;
  }
  const { tab, groupIdx } = currentEditEntry;
  // Close modal first, then add gap
  closeModal();
  await onQuickGap30(tab, groupIdx, 0);
}

// =============================================
// END QUICK BREAK NOW FEATURE
// =============================================


// Load from CSV
async function loadFromCSV(mode) {
  const statusId = mode === 'today' ? 'load-status-today' : 'load-status-tomorrow';
  const loadStatus = document.getElementById(statusId);
  loadStatus.textContent = 'Loading...';

  const endpoint = mode === 'today' ? '/load-today-from-master' : '/preload-from-master';

  try {
    const response = await fetch(endpoint, { method: 'POST' });
    const result = await response.json();

    if (response.ok) {
      loadStatus.textContent = result.message || 'Loaded!';
      loadStatus.style.color = '#28a745';
      await loadData();
    } else {
      loadStatus.textContent = result.error || 'Error';
      loadStatus.style.color = '#dc3545';
    }
  } catch (error) {
    loadStatus.textContent = 'Error: ' + error.message;
    loadStatus.style.color = '#dc3545';
  }

  setTimeout(() => { loadStatus.textContent = ''; }, 5000);
}

// Show message (XSS-safe)
function showMessage(type, message) {
  const container = document.getElementById('message-container');
  const div = document.createElement('div');
  div.className = `message ${type}`;
  div.textContent = message;  // textContent is XSS-safe
  container.innerHTML = '';
  container.appendChild(div);
  setTimeout(() => { container.innerHTML = ''; }, 5000);
}

// Initialize edit mode UI and load current tab (lazy loading)
applyEditModeUI('today');
applyEditModeUI('tomorrow');
loadTabData('today');
