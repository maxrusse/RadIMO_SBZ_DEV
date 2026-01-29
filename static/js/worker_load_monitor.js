// Worker Load Monitor JavaScript

// Parse config from JSON block
const CONFIG = JSON.parse(document.getElementById('page-config').textContent);
const SKILLS = CONFIG.skills;
const MODALITIES = CONFIG.modalities;
const SKILL_SETTINGS = CONFIG.skill_settings;
const MODALITY_SETTINGS = CONFIG.modality_settings;
const LOAD_MONITOR_CONFIG = CONFIG.load_monitor_config;
const UI_COLORS = CONFIG.ui_colors;

// State
let currentMode = LOAD_MONITOR_CONFIG.default_view || 'simple';
let colorMode = LOAD_MONITOR_CONFIG.color_thresholds?.mode || 'absolute';
let workersData = [];
let maxWeight = 0;
let autoRefreshInterval = null;
let filters = { modality: '', skill: '', hideZero: false };
let sortState = {
  global: { column: 'weight', direction: 'desc' },
  modality: { column: 'total', direction: 'desc' },
  skill: { column: 'total', direction: 'desc' },
  advanced: { column: 'weight', direction: 'desc' }
};

// Generate dynamic CSS for modality colors
(function() {
  const style = document.createElement('style');
  let css = '';
  for (const [mod, settings] of Object.entries(MODALITY_SETTINGS)) {
    const navColor = settings.nav_color || '#6c757d';
    css += `.badge-${mod} { background: ${navColor}; }\n`;
    css += `.mod-header-${mod} { background: ${navColor}; color: white; }\n`;
  }
  for (const [skill, settings] of Object.entries(SKILL_SETTINGS)) {
    const btnColor = settings.button_color || '#6c757d';
    const textColor = settings.text_color || '#ffffff';
    css += `.skill-header-${skill.toLowerCase().replace(/[^a-z0-9]/g, '-')} { background: ${btnColor}; color: ${textColor}; }\n`;
  }
  style.textContent = css;
  document.head.appendChild(style);
})();

// Color calculation based on weight thresholds
function getLoadThresholds() {
  const thresholds = LOAD_MONITOR_CONFIG.color_thresholds || {};
  let lowThreshold, highThreshold;

  if (colorMode === 'relative' && maxWeight > 0) {
    const relConfig = thresholds.relative || { low_pct: 33, high_pct: 66 };
    lowThreshold = maxWeight * (relConfig.low_pct / 100);
    highThreshold = maxWeight * (relConfig.high_pct / 100);
  } else {
    const absConfig = thresholds.absolute || { low: 3.0, high: 7.0 };
    lowThreshold = absConfig.low;
    highThreshold = absConfig.high;
  }

  return { lowThreshold, highThreshold };
}

function getLoadColor(weight) {
  const { lowThreshold, highThreshold } = getLoadThresholds();

  if (weight <= 0) return { bg: '#e9ecef', text: 'text-muted' };
  if (weight < lowThreshold) return { bg: 'var(--load-green)', text: 'text-green' };
  if (weight < highThreshold) return { bg: 'var(--load-yellow)', text: 'text-yellow' };
  return { bg: 'var(--load-red)', text: 'text-red' };
}

function getLoadColorClass(weight) {
  const { lowThreshold, highThreshold } = getLoadThresholds();

  if (weight <= 0) return '';
  if (weight < lowThreshold) return 'load-green';
  if (weight < highThreshold) return 'load-yellow';
  return 'load-red';
}

// Mode switching
function setMode(mode) {
  currentMode = mode;
  document.body.classList.remove('mode-simple', 'mode-advanced');
  document.body.classList.add(`mode-${mode}`);

  document.querySelectorAll('.mode-btn').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });

  renderAllTables();
}

// Color mode switching
function setColorMode(mode) {
  colorMode = mode;
  document.querySelectorAll('.color-btn').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.color === mode);
  });
  renderAllTables();
}

// Filtering (Advanced mode)
function filterByModality(mod) {
  filters.modality = mod;
  document.querySelectorAll('[data-modality]').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.modality === mod);
  });
  renderAllTables();
}

function filterBySkill(skill) {
  filters.skill = skill;
  document.querySelectorAll('[data-skill]').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.skill === skill);
  });
  renderAllTables();
}

function applyFilters() {
  filters.hideZero = document.getElementById('filter-hide-zero')?.checked || false;
  renderAllTables();
}

// Sorting
function sortTable(tableType, column) {
  const state = sortState[tableType];
  if (state.column === column) {
    state.direction = state.direction === 'asc' ? 'desc' : 'asc';
  } else {
    state.column = column;
    state.direction = column === 'name' ? 'asc' : 'desc';
  }

  renderAllTables();
}

function getSortValue(worker, column, tableType) {
  if (column === 'name') return worker.name.toLowerCase();
  if (column === 'weight') return worker.global_weight || 0;
  if (column === 'total') {
    if (tableType === 'modality') {
      return MODALITIES.reduce(function(total, mod) {
        return total + (worker.modalities[mod]?.assignment_total || 0);
      }, 0);
    }
    if (tableType === 'skill') {
      return SKILLS.reduce(function(total, skill) {
        return total + (worker.skills[skill] || 0);
      }, 0);
    }
    return worker.global_weight || 0;
  }
  if (MODALITIES.includes(column)) return worker.modalities[column]?.assignment_total || 0;
  if (SKILLS.includes(column)) return worker.skills[column] || 0;
  return 0;
}

function sortWorkers(workers, tableType) {
  const { column, direction } = sortState[tableType];
  const sorted = [...workers];
  const ascending = direction === 'asc';

  sorted.sort(function(a, b) {
    const valA = getSortValue(a, column, tableType);
    const valB = getSortValue(b, column, tableType);

    if (typeof valA === 'string') {
      return ascending ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return ascending ? valA - valB : valB - valA;
  });

  return sorted;
}

// Filter workers based on current filters
function filterWorkers(workers) {
  return workers.filter(function(worker) {
    // Hide zero filter
    if (filters.hideZero && worker.global_weight <= 0) {
      return false;
    }

    // Modality filter
    if (filters.modality && !worker.modalities[filters.modality]) {
      return false;
    }

    // Skill filter (worker must have assignment in that skill)
    if (filters.skill && (worker.skills[filters.skill] || 0) <= 0) {
      return false;
    }

    return true;
  });
}

// Render Global table (Simple mode)
function renderGlobalTable() {
  const tbody = document.getElementById('tbody-global');
  if (!tbody) return;

  const filteredWorkers = filterWorkers(workersData);
  const sorted = sortWorkers(filteredWorkers, 'global');

  if (sorted.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="no-data">No workers match filters</td></tr>';
    return;
  }

  const maxBarWeight = Math.max(maxWeight, 1);
  let html = '';

  let totalWeight = 0;

  sorted.forEach(function(worker) {
    const weight = worker.global_weight || 0;
    totalWeight += weight;
    const color = getLoadColor(weight);
    const colorClass = getLoadColorClass(weight);
    const barWidth = Math.min((weight / maxBarWeight) * 100, 100);

    html += `<tr>
      <td class="worker-col">${escapeHtml(worker.name)}</td>
      <td class="weight-value ${color.text}">${weight.toFixed(1)}</td>
      <td>
        <div class="weight-bar">
          <div class="weight-bar-fill ${colorClass}" style="width: ${barWidth}%; max-width: 200px;"></div>
        </div>
      </td>
    </tr>`;
  });

  // Add totals row
  const totalBarWidth = Math.min((totalWeight / maxBarWeight) * 100, 100);
  html += `<tr class="totals-row">
    <td class="worker-col" style="font-weight: 700;">Total</td>
    <td class="weight-value" style="font-weight: 700;">${totalWeight.toFixed(1)}</td>
    <td>
      <div class="weight-bar">
        <div class="weight-bar-fill" style="width: ${totalBarWidth}%; max-width: 200px; background: #6c757d;"></div>
      </div>
    </td>
  </tr>`;

  tbody.innerHTML = html;
}

// Render Per-Modality table (Simple mode)
function renderModalityTable() {
  const tbody = document.getElementById('tbody-modality');
  if (!tbody) return;

  const filteredWorkers = filterWorkers(workersData);
  const sorted = sortWorkers(filteredWorkers, 'modality');

  if (sorted.length === 0) {
    const colCount = MODALITIES.length + 2;
    tbody.innerHTML = `<tr><td colspan="${colCount}" class="no-data">No workers match filters</td></tr>`;
    return;
  }

  let html = '';

  // Track column totals
  const modalityTotals = {};
  MODALITIES.forEach(function(mod) { modalityTotals[mod] = 0; });
  let grandTotal = 0;

  sorted.forEach(function(worker) {
    let total = 0;
    let modCells = '';

    MODALITIES.forEach(function(mod) {
      const modData = worker.modalities[mod];
      const count = modData?.assignment_total || 0;
      total += count;
      modalityTotals[mod] += count;
      const color = getLoadColor(count);

      modCells += `<td class="${color.text}" style="text-align: center;">${count > 0 ? count : '-'}</td>`;
    });

    grandTotal += total;
    const totalColor = getLoadColor(total);

    html += `<tr>
      <td class="worker-col">${escapeHtml(worker.name)}</td>
      ${modCells}
      <td class="${totalColor.text}" style="text-align: center; font-weight: 600;">${total}</td>
    </tr>`;
  });

  // Add totals row
  let totalModCells = '';
  MODALITIES.forEach(function(mod) {
    const count = modalityTotals[mod];
    totalModCells += `<td style="text-align: center; font-weight: 700;">${count > 0 ? count : '-'}</td>`;
  });
  html += `<tr class="totals-row">
    <td class="worker-col" style="font-weight: 700;">Total</td>
    ${totalModCells}
    <td style="text-align: center; font-weight: 700;">${grandTotal}</td>
  </tr>`;

  tbody.innerHTML = html;
}

// Render Per-Skill table (Simple mode)
function renderSkillTable() {
  const tbody = document.getElementById('tbody-skill');
  if (!tbody) return;

  const filteredWorkers = filterWorkers(workersData);
  const sorted = sortWorkers(filteredWorkers, 'skill');

  if (sorted.length === 0) {
    const colCount = SKILLS.length + 2;
    tbody.innerHTML = `<tr><td colspan="${colCount}" class="no-data">No workers match filters</td></tr>`;
    return;
  }

  let html = '';

  // Track column totals
  const skillTotals = {};
  SKILLS.forEach(function(skill) { skillTotals[skill] = 0; });
  let grandTotal = 0;

  sorted.forEach(function(worker) {
    let total = 0;
    let skillCells = '';

    SKILLS.forEach(function(skill) {
      const count = worker.skills[skill] || 0;
      total += count;
      skillTotals[skill] += count;
      const color = getLoadColor(count);

      skillCells += `<td class="${color.text}" style="text-align: center;">${count > 0 ? count : '-'}</td>`;
    });

    grandTotal += total;
    const totalColor = getLoadColor(total);

    html += `<tr>
      <td class="worker-col">${escapeHtml(worker.name)}</td>
      ${skillCells}
      <td class="${totalColor.text}" style="text-align: center; font-weight: 600;">${total}</td>
    </tr>`;
  });

  // Add totals row
  let totalSkillCells = '';
  SKILLS.forEach(function(skill) {
    const count = skillTotals[skill];
    totalSkillCells += `<td style="text-align: center; font-weight: 700;">${count > 0 ? count : '-'}</td>`;
  });
  html += `<tr class="totals-row">
    <td class="worker-col" style="font-weight: 700;">Total</td>
    ${totalSkillCells}
    <td style="text-align: center; font-weight: 700;">${grandTotal}</td>
  </tr>`;

  tbody.innerHTML = html;
}

// Render Advanced table (Full matrix)
function renderAdvancedTable() {
  const thead = document.getElementById('thead-advanced');
  const tbody = document.getElementById('tbody-advanced');
  if (!thead || !tbody) return;

  const filteredWorkers = filterWorkers(workersData);
  const sorted = sortWorkers(filteredWorkers, 'advanced');

  // Determine which modalities/skills to show based on filters
  const showModalities = filters.modality ? [filters.modality] : MODALITIES;
  const showSkills = filters.skill ? [filters.skill] : SKILLS;

  // Build header
  let headerTop = '<tr class="header-top"><th rowspan="2" class="sortable worker-col" data-sort="name" onclick="sortTable(\'advanced\', \'name\')">Worker</th>';
  let headerSub = '<tr class="header-sub">';

  showModalities.forEach(function(mod) {
    const modSettings = MODALITY_SETTINGS[mod] || {};
    const label = modSettings.label || mod.toUpperCase();
    const colSpan = showSkills.length;
    headerTop += `<th colspan="${colSpan}" class="mod-header-${mod}">${label}</th>`;

    showSkills.forEach(function(skill) {
      const skillSettings = SKILL_SETTINGS[skill] || {};
      const skillLabel = skillSettings.label || skill;
      const skillClass = `skill-header-${skill.toLowerCase().replace(/[^a-z0-9]/g, '-')}`;
      headerSub += `<th class="${skillClass}" title="${skillLabel}">${skillLabel.substring(0, 4)}</th>`;
    });
  });

  headerTop += '<th rowspan="2" class="sortable" data-sort="weight" onclick="sortTable(\'advanced\', \'weight\')">Total</th></tr>';
  headerSub += '</tr>';

  thead.innerHTML = headerTop + headerSub;

  // Build body
  if (sorted.length === 0) {
    const colCount = showModalities.length * showSkills.length + 2;
    tbody.innerHTML = `<tr><td colspan="${colCount}" class="no-data">No workers match filters</td></tr>`;
    return;
  }

  let html = '';

  // Track column totals for each modality-skill combination
  const cellTotals = {};
  showModalities.forEach(function(mod) {
    cellTotals[mod] = {};
    showSkills.forEach(function(skill) {
      cellTotals[mod][skill] = 0;
    });
  });
  let grandTotal = 0;

  sorted.forEach(function(worker) {
    html += '<tr>';
    html += `<td class="worker-col">${escapeHtml(worker.name)}</td>`;

    showModalities.forEach(function(mod) {
      const modData = worker.modalities[mod];

      showSkills.forEach(function(skill) {
        const count = modData?.skill_counts?.[skill] || 0;
        cellTotals[mod][skill] += count;
        const color = getLoadColor(count);

        if (count > 0) {
          html += `<td class="${color.text}" style="font-weight: 600;">${count}</td>`;
        } else {
          html += '<td style="color: #ccc;">-</td>';
        }
      });
    });

    grandTotal += worker.global_weight || 0;
    const totalColor = getLoadColor(worker.global_weight);
    html += `<td class="${totalColor.text}" style="font-weight: 700;">${worker.global_weight.toFixed(1)}</td>`;
    html += '</tr>';
  });

  // Add totals row
  html += '<tr class="totals-row">';
  html += '<td class="worker-col" style="font-weight: 700;">Total</td>';
  showModalities.forEach(function(mod) {
    showSkills.forEach(function(skill) {
      const count = cellTotals[mod][skill];
      html += `<td style="font-weight: 700;">${count > 0 ? count : '-'}</td>`;
    });
  });
  html += `<td style="font-weight: 700;">${grandTotal.toFixed(1)}</td>`;
  html += '</tr>';

  tbody.innerHTML = html;
}

function renderAllTables() {
  if (currentMode === 'simple') {
    renderGlobalTable();
    renderModalityTable();
    renderSkillTable();
    updateSortIndicators('global');
    updateSortIndicators('modality');
    updateSortIndicators('skill');
  } else {
    renderAdvancedTable();
    updateSortIndicators('advanced');
  }

  // Show/hide no data message
  const noDataMsg = document.getElementById('no-data-msg');
  if (noDataMsg) {
    noDataMsg.style.display = workersData.length === 0 ? 'block' : 'none';
  }
}

function updateSortIndicators(tableType) {
  const state = sortState[tableType];
  const tableId = `table-${tableType}`;
  document.querySelectorAll(`#${tableId} th`).forEach(function(th) {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.sort === state.column) {
      th.classList.add(state.direction === 'asc' ? 'sort-asc' : 'sort-desc');
    }
  });
}

// Auto-refresh
function toggleAutoRefresh() {
  const checkbox = document.getElementById('auto-refresh');
  if (checkbox?.checked) {
    loadData();
    autoRefreshInterval = setInterval(loadData, 30000); // 30 seconds
  } else {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
    }
  }
}

// Load data from API
function loadData() {
  return fetch('/api/worker-load/data')
    .then(function(response) {
      if (!response.ok) {
        throw new Error(`Failed to load worker data (${response.status})`);
      }
      return response.json();
    })
    .then(function(data) {
      if (data.success) {
        workersData = data.workers || [];
        maxWeight = data.max_weight || 0;

        // Update last update time
        const lastUpdate = document.getElementById('last-update');
        if (lastUpdate) {
          lastUpdate.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
        }

        renderAllTables();
      } else {
        console.error('Failed to load worker data:', data.error);
      }
    })
    .catch(function(error) {
      console.error('Error loading worker data:', error);
    });
}

// Escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
  setColorMode(colorMode);
  setMode(currentMode);
  loadData();
});
