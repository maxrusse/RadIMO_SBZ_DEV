/**
 * Shared Timeline Chart Module
 * Used by both timetable.html and prep_next_day.html
 */

const TimelineChart = (function() {
  // Default timeline config
  const TIMELINE_START = 6;  // 6:00
  const TIMELINE_END = 20;   // 20:00
  const TIMELINE_HOURS = TIMELINE_END - TIMELINE_START;

  // Parse time string "HH:MM" into hours and minutes
  function parseTimeStr(timeStr) {
    if (!timeStr || typeof timeStr !== 'string') return null;
    const parts = timeStr.split(':');
    if (parts.length < 2) return null;
    const [h, m] = parts.map(Number);
    return { hours: h || 0, minutes: m || 0 };
  }

  // Convert time string to minutes for comparison
  function timeToMinutes(timeStr) {
    const parsed = parseTimeStr(timeStr);
    if (!parsed) return 0;
    return parsed.hours * 60 + parsed.minutes;
  }

  // Convert time string to percentage position
  function timeToPercent(timeStr) {
    const parsed = parseTimeStr(timeStr);
    if (!parsed) return 0;
    const hours = parsed.hours + parsed.minutes / 60;
    const clamped = Math.max(TIMELINE_START, Math.min(TIMELINE_END, hours));
    return ((clamped - TIMELINE_START) / TIMELINE_HOURS) * 100;
  }

  // Check if skill is active (value >= 1 or weighted)
  function isSkillActive(val) {
    if (val === 'w' || val === 'W') return true;
    const n = Number(val);
    return !isNaN(n) && n >= 1;
  }

  // Check if any skill in entry is active
  function hasAnyActiveSkill(entry, skillColumns) {
    const hasSkills = skillColumns.some(s => {
      const val = entry[s];
      return isSkillActive(val);
    });
    if (hasSkills) return true;
    return parseGapList(entry.gaps).length > 0;
  }

  // Escape HTML for XSS protection
  function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  // Parse gap list from various formats (array, JSON string, or object)
  function parseGapList(rawGaps) {
    if (!rawGaps) return [];
    if (Array.isArray(rawGaps)) return rawGaps;
    if (typeof rawGaps !== 'string') return [];

    try {
      const parsed = JSON.parse(rawGaps);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  }

  function normalizeTasks(rawTasks) {
    if (!rawTasks) return [];
    if (Array.isArray(rawTasks)) {
      return rawTasks.map(String).filter(t => t.trim() !== '');
    }
    if (typeof rawTasks === 'string') {
      return rawTasks.split(',').map(t => t.trim()).filter(Boolean);
    }
    return [String(rawTasks)].filter(t => t.trim() !== '');
  }

  // Build gradient for skill stripes
  function buildSkillGradient(skills, skillColorMap) {
    if (!skills || skills.length === 0) return '#ddd';
    if (skills.length === 1) {
      const color = skillColorMap[skills[0]] || '#ccc';
      return `repeating-linear-gradient(90deg, ${color} 0, ${color} 10px, #fff 10px, #fff 25px)`;
    }
    const sw = 10, gw = 15;
    const colors = skills.map(s => skillColorMap[s] || '#ccc');
    const stops = colors.map((c, i) => `${c} ${i * sw}px, ${c} ${(i + 1) * sw}px`);
    const bw = colors.length * sw;
    stops.push(`#fff ${bw}px, #fff ${bw + gw}px`);
    return `repeating-linear-gradient(90deg, ${stops.join(', ')})`;
  }

  // Deduplicate gaps by start-end key
  function deduplicateGaps(gaps) {
    const seen = new Map();
    gaps.filter(Boolean).forEach(gap => {
      const key = `${gap.start || ''}-${gap.end || ''}`;
      if (!seen.has(key)) {
        seen.set(key, gap);
      }
    });
    return Array.from(seen.values());
  }

  // Merge entries across modalities and time
  function mergeEntriesByTime(entries, skillColumns) {
    if (!entries || entries.length === 0) return [];

    const sorted = [...entries].sort((a, b) => timeToMinutes(a.start_time) - timeToMinutes(b.start_time));

    const merged = {
      start_time: sorted[0].start_time,
      end_time: sorted[0].end_time,
      TIME: sorted[0].TIME,
      modalities: new Set(),
      skillValues: {},
      gaps: [],
      tasks: new Set()
    };

    let lastEndMinutes = timeToMinutes(sorted[0].end_time);
    let mergedEndMinutes = lastEndMinutes;
    let lastEndLabel = sorted[0].end_time;

    sorted.forEach((entry, idx) => {
      if (entry._modality) merged.modalities.add(entry._modality.toUpperCase());

      // Merge skills - mark active if any modality has it active
      skillColumns.forEach(s => {
        if (isSkillActive(entry[s])) {
          merged.skillValues[s] = 1;
        }
      });

      // Preserve explicit gap metadata
      parseGapList(entry.gaps).forEach(gap => merged.gaps.push(gap));
      normalizeTasks(entry.tasks || entry.task).forEach(task => merged.tasks.add(task));

      const startMin = timeToMinutes(entry.start_time);
      const endMin = timeToMinutes(entry.end_time);

      // Record inferred gaps between sequential segments
      if (idx > 0 && startMin > lastEndMinutes) {
        merged.gaps.push({ start: lastEndLabel, end: entry.start_time, activity: 'Gap' });
      }

      if (endMin > mergedEndMinutes) {
        mergedEndMinutes = endMin;
        merged.end_time = entry.end_time;
      }

      if (endMin > lastEndMinutes) {
        lastEndMinutes = endMin;
        lastEndLabel = entry.end_time;
      }
    });

    merged.TIME = `${merged.start_time}-${merged.end_time}`;
    // Deduplicate gaps to avoid rendering same gap multiple times
    merged.gaps = deduplicateGaps(merged.gaps);
    merged.tasks = Array.from(merged.tasks);

    return [merged];
  }

  function mergeEntriesForSingleLane(entries, skillColumns) {
    if (!entries || entries.length === 0) return [];

    const sorted = [...entries].sort((a, b) => {
      const startDiff = timeToMinutes(a.start_time) - timeToMinutes(b.start_time);
      if (startDiff !== 0) return startDiff;
      return timeToMinutes(a.end_time) - timeToMinutes(b.end_time);
    });

    const merged = [];

    sorted.forEach(entry => {
      const start = timeToMinutes(entry.start_time);
      const end = timeToMinutes(entry.end_time);

      const skillValues = {};
      if (entry.skillValues) {
        Object.keys(entry.skillValues).forEach(s => {
          if (isSkillActive(entry.skillValues[s])) {
            skillValues[s] = 1;
          }
        });
      } else {
        skillColumns.forEach(s => {
          if (isSkillActive(entry[s])) {
            skillValues[s] = 1;
          }
        });
      }

      const modalities = new Set();
      if (entry.modalities && entry.modalities.size) {
        entry.modalities.forEach(m => modalities.add(m));
      }
      if (entry._modality || entry.modality) {
        modalities.add((entry._modality || entry.modality).toUpperCase());
      }

      const gaps = parseGapList(entry.gaps);
      const tasks = normalizeTasks(entry.tasks || entry.task);

      const last = merged[merged.length - 1];
      if (!last) {
        merged.push({
          start_time: entry.start_time,
          end_time: entry.end_time,
          TIME: entry.TIME,
          skillValues: { ...skillValues },
          modalities,
          gaps: [...gaps],
          tasks: [...tasks]
        });
        return;
      }

      const lastEnd = timeToMinutes(last.end_time);
      if (start <= lastEnd) {
        if (end > lastEnd) {
          last.end_time = entry.end_time;
        }
        last.TIME = `${last.start_time}-${last.end_time}`;
        Object.keys(skillValues).forEach(s => {
          last.skillValues[s] = 1;
        });
        modalities.forEach(m => last.modalities.add(m));
        gaps.forEach(gap => last.gaps.push(gap));
        tasks.forEach(task => last.tasks.push(task));
        // Deduplicate gaps after merging
        last.gaps = deduplicateGaps(last.gaps);
        last.tasks = Array.from(new Set(last.tasks));
        return;
      }

      merged.push({
        start_time: entry.start_time,
        end_time: entry.end_time,
        TIME: entry.TIME,
        skillValues: { ...skillValues },
        modalities,
        gaps: [...gaps],
        tasks: [...tasks]
      });
    });

    return merged;
  }

  // Build time header row
  function buildTimeHeader(headerEl) {
    headerEl.innerHTML = '';
    for (let h = TIMELINE_START; h < TIMELINE_END; h++) {
      const slot = document.createElement('div');
      slot.className = 'time-slot';
      slot.textContent = `${h}:00`;
      headerEl.appendChild(slot);
    }
  }

  // Update current time indicator line
  function updateCurrentTimeLine(gridEl, lineId) {
    const existing = document.getElementById(lineId);
    if (existing) existing.remove();

    const now = new Date();
    const currentHour = now.getHours() + now.getMinutes() / 60;

    // Only show if within timeline bounds
    if (currentHour < TIMELINE_START || currentHour > TIMELINE_END) return;

    const percent = ((currentHour - TIMELINE_START) / TIMELINE_HOURS) * 100;

    const workerColWidth = getComputedStyle(document.documentElement).getPropertyValue('--worker-col-width') || '180px';
    const line = document.createElement('div');
    line.id = lineId;
    line.className = 'current-time-line';
    line.style.left = `calc(${workerColWidth.trim()} + (100% - ${workerColWidth.trim()}) * ${percent / 100})`;

    gridEl.appendChild(line);
  }

  /**
   * Render timeline chart
   * @param {Object} options Configuration options
   * @param {HTMLElement} options.gridEl - The timeline grid container element
   * @param {HTMLElement} options.headerEl - The time header element
   * @param {Array} options.data - Array of schedule entries
   * @param {Array} options.skillColumns - Array of skill column names
   * @param {Object} options.skillSlugMap - Map of skill names to slugs
   * @param {Object} options.skillColorMap - Map of skill slugs to colors
   * @param {boolean} options.mergeModalities - Whether to merge entries across modalities (ALL view)
   * @param {boolean} options.showCurrentTime - Whether to show current time indicator
   * @param {string} options.timeLineId - ID for the current time line element
   */
  function render(options) {
    const {
      gridEl,
      headerEl,
      data,
      skillColumns,
      skillSlugMap = {},
      skillColorMap = {},
      mergeModalities = true,
      showCurrentTime = true,
      timeLineId = 'current-time-line'
    } = options;

    if (!gridEl) {
      console.error('TimelineChart: gridEl is required');
      return;
    }

    // Clear existing content (keep header label if present)
    const headerLabel = gridEl.querySelector('.time-header-label');
    gridEl.innerHTML = '';

    // Re-add header label
    if (headerLabel) {
      gridEl.appendChild(headerLabel);
    } else {
      const label = document.createElement('div');
      label.className = 'time-header-label';
      label.textContent = 'Worker';
      gridEl.appendChild(label);
    }

    // Re-add time header
    if (headerEl) {
      gridEl.appendChild(headerEl);
      buildTimeHeader(headerEl);
    } else {
      const header = document.createElement('div');
      header.className = 'time-header';
      gridEl.appendChild(header);
      buildTimeHeader(header);
    }

    // Validate data
    if (!Array.isArray(data) || data.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'No schedule data available';
      gridEl.appendChild(empty);
      return;
    }

    // Filter out invalid entries
    const validData = data.filter(e => {
      if (!e) return false;
      if (e.TIME === '00:00-00:00') return false;
      if (!e.start_time || !e.end_time) return false;
      return hasAnyActiveSkill(e, skillColumns);
    });

    if (validData.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'No active schedule entries';
      gridEl.appendChild(empty);
      return;
    }

    // Group entries by worker name
    const workerMap = new Map();
    validData.forEach(entry => {
      const worker = entry.PPL || entry.worker;
      if (!workerMap.has(worker)) {
        workerMap.set(worker, []);
      }
      workerMap.get(worker).push(entry);
    });

    // Sort workers by earliest start time
    const sortedWorkers = Array.from(workerMap.entries()).sort((a, b) => {
      const aStart = Math.min(...a[1].map(e => timeToMinutes(e.start_time)));
      const bStart = Math.min(...b[1].map(e => timeToMinutes(e.start_time)));
      return aStart - bStart;
    });

    // Create worker rows
    sortedWorkers.forEach(([worker, entries]) => {
      // Merge entries if in ALL view mode
      const processedEntries = mergeModalities ? mergeEntriesByTime(entries, skillColumns) : entries;
      const displayEntries = mergeEntriesForSingleLane(processedEntries, skillColumns);

      // Collect all skills this worker has
      const workerSkills = new Set();
      displayEntries.forEach(entry => {
        const skills = entry.skillValues
          ? Object.keys(entry.skillValues)
          : skillColumns.filter(s => isSkillActive(entry[s]));
        skills.forEach(s => {
          workerSkills.add(skillSlugMap[s] || s.toLowerCase());
        });
      });

      const row = document.createElement('div');
      row.className = 'worker-row';
      row.dataset.worker = worker;
      row.dataset.skills = Array.from(workerSkills).join(',');

      // Worker name cell
      const nameCell = document.createElement('div');
      nameCell.className = 'worker-name-cell';
      nameCell.textContent = worker;

      // Timeline cell
      const timelineCell = document.createElement('div');
      timelineCell.className = 'worker-timeline';

      // Create shift bars
      displayEntries.forEach(entry => {
        const left = timeToPercent(entry.start_time);
        const right = timeToPercent(entry.end_time);
        const width = right - left;

        if (width <= 0) return;

        let activeSkills;
        let tooltipMods = '';
        let gapTooltip = '';

        if (entry.skillValues) {
          activeSkills = Object.keys(entry.skillValues)
            .map(s => skillSlugMap[s] || s.toLowerCase());
        } else {
          activeSkills = skillColumns
            .filter(s => isSkillActive(entry[s]))
            .map(s => skillSlugMap[s] || s.toLowerCase());
        }

        if (entry.modalities && entry.modalities.size > 0) {
          tooltipMods = `Modalities: ${Array.from(entry.modalities).join(', ')}\n`;
        } else if (entry._modality || entry.modality) {
          tooltipMods = `Modality: ${(entry._modality || entry.modality).toUpperCase()}\n`;
        }

        const tasks = normalizeTasks(entry.tasks || entry.task);
        const taskTooltip = tasks.length ? `Shifts: ${tasks.join(', ')}\n` : '';

        const gaps = parseGapList(entry.gaps);
        if (gaps.length) {
          const gapList = gaps
            .map(g => {
              const start = g.start || '?';
              const end = g.end || '?';
              const activity = g.activity ? ` (${g.activity})` : '';
              return `${start}-${end}${activity}`;
            })
            .join(', ');
          gapTooltip = `Gaps: ${gapList}\n`;
        }

        if (activeSkills.length > 0) {
          const bar = document.createElement('div');
          bar.className = 'shift-bar';
          bar.style.left = `${left}%`;
          bar.style.width = `${width}%`;
          bar.style.background = buildSkillGradient(activeSkills, skillColorMap);
          bar.style.zIndex = '1';
          bar.dataset.skills = activeSkills.join(',');

          // Store modality data for filtering
          let modList = [];
          if (entry.modalities && entry.modalities.size > 0) {
            modList = Array.from(entry.modalities).map(m => m.toLowerCase());
          } else if (entry._modality || entry.modality) {
            modList = [(entry._modality || entry.modality).toLowerCase()];
          }
          bar.dataset.modalities = modList.join(',');

          // Tooltip
          const timeDisplay = entry.TIME || `${entry.start_time}-${entry.end_time}`;
          bar.title = `${worker}\n${tooltipMods}${taskTooltip}${gapTooltip}Zeit: ${timeDisplay}\nSkills: ${activeSkills.join(', ')}`;

          timelineCell.appendChild(bar);
        }

        // Render gap bars for this entry
        gaps.forEach(gap => {
          const gapStart = gap.start;
          const gapEnd = gap.end;
          if (!gapStart || !gapEnd) return;

          const gapLeft = timeToPercent(gapStart);
          const gapRight = timeToPercent(gapEnd);
          const gapWidth = gapRight - gapLeft;

          if (gapWidth <= 0) return;

          const gapBar = document.createElement('div');
          gapBar.className = 'gap-bar';
          gapBar.style.left = `${gapLeft}%`;
          gapBar.style.width = `${gapWidth}%`;
          gapBar.style.zIndex = '2';

          // Gap tooltip
          const activity = gap.activity || 'Gap';
          gapBar.title = `${worker}\n${activity}: ${gapStart}-${gapEnd}`;

          timelineCell.appendChild(gapBar);
        });
      });

      row.appendChild(nameCell);
      row.appendChild(timelineCell);
      gridEl.appendChild(row);
    });

    // Add current time indicator
    if (showCurrentTime) {
      updateCurrentTimeLine(gridEl, timeLineId);
    }
  }

  // Filter rows by skill
  function filterBySkill(gridEl, skillSlug) {
    const rows = gridEl.querySelectorAll('.worker-row');
    rows.forEach(row => {
      const bars = Array.from(row.querySelectorAll('.shift-bar'));

      // Show all bars when filter is cleared
      if (skillSlug === 'all' || !skillSlug) {
        bars.forEach(bar => bar.style.display = '');
        row.style.display = '';
        return;
      }

      const matchingBars = bars.filter(bar => {
        const barSkills = (bar.dataset.skills || '').split(',').filter(s => s);
        return barSkills.includes(skillSlug);
      });

      // Show matching bars, hide the rest
      bars.forEach(bar => {
        const barSkills = (bar.dataset.skills || '').split(',').filter(s => s);
        bar.style.display = barSkills.includes(skillSlug) ? '' : 'none';
      });

      // Hide row if no matching bars
      row.style.display = matchingBars.length > 0 ? '' : 'none';
    });
  }

  // Filter rows by modality
  function filterByModality(gridEl, modality) {
    const rows = gridEl.querySelectorAll('.worker-row');
    const mod = (modality || '').toLowerCase();

    rows.forEach(row => {
      const bars = Array.from(row.querySelectorAll('.shift-bar'));

      // Show all bars when filter is cleared
      if (mod === 'all' || mod === '' || !mod) {
        bars.forEach(bar => bar.style.display = '');
        row.style.display = '';
        return;
      }

      const matchingBars = bars.filter(bar => {
        const barMods = (bar.dataset.modalities || '').split(',').filter(m => m);
        return barMods.includes(mod);
      });

      // Show matching bars, hide the rest
      bars.forEach(bar => {
        const barMods = (bar.dataset.modalities || '').split(',').filter(m => m);
        bar.style.display = barMods.includes(mod) ? '' : 'none';
      });

      // Hide row if no matching bars
      row.style.display = matchingBars.length > 0 ? '' : 'none';
    });
  }

  // Public API
  return {
    render,
    filterBySkill,
    filterByModality,
    updateCurrentTimeLine,
    timeToMinutes,
    timeToPercent,
    isSkillActive,
    hasAnyActiveSkill,
    parseGapList,
    escapeHtml,
    TIMELINE_START,
    TIMELINE_END,
    TIMELINE_HOURS
  };
})();

// Export for module systems if available
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TimelineChart;
}
