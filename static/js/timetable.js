/**
 * Timetable Page JavaScript
 * Uses shared TimelineChart module for rendering
 */

// Page configuration - will be set by inline script with Jinja data
let TimetableConfig = {
  modalities: {},
  skillDefinitions: [],
  skillColumns: [],
  skillSlugMap: {},
  skillColorMap: {},
  modColorMap: {},
  currentModality: 'all',
  skillFilter: 'all',
  data: []
};

// Initialize configuration from page
function initTimetableConfig(config) {
  TimetableConfig = { ...TimetableConfig, ...config };
}

// Inject dynamic styles based on modality and skills
function injectDynamicStyles() {
  const { modalities, skillDefinitions, currentModality } = TimetableConfig;

  // Set modality body styles
  if (modalities[currentModality]) {
    const settings = modalities[currentModality];
    document.body.style.setProperty('--modality-bg', settings.background_color);
    document.body.style.setProperty('--modality-nav', settings.nav_color);
    document.body.style.setProperty('--modality-hover', settings.hover_color);
  }

  // Add styles for modality filter buttons
  document.querySelectorAll('#modalityFilterBar a').forEach(a => {
    const mod = a.getAttribute('data-modality');
    if (modalities[mod] && mod === currentModality) {
      a.style.background = modalities[mod].nav_color;
      a.style.borderColor = modalities[mod].nav_color;
      a.style.color = 'white';
    }
  });

  // Add styles for skill filter buttons
  document.querySelectorAll('#skillFilterBar button').forEach(btn => {
    const skillSlug = btn.getAttribute('data-skill');
    const skillDef = skillDefinitions.find(s => s.slug === skillSlug);
    if (skillDef) {
      btn.style.borderLeft = `4px solid ${skillDef.button_color}`;
    }
  });

  // Add styles for legend boxes
  document.querySelectorAll('.legend-box').forEach(box => {
    const skillSlug = box.getAttribute('data-skill');
    const skillDef = skillDefinitions.find(s => s.slug === skillSlug);
    if (skillDef) {
      box.style.background = skillDef.button_color;
    }
  });
}

// Build the timeline using shared module
function buildTimeline() {
  const grid = document.getElementById('timeline-grid');
  const header = document.getElementById('time-header');

  if (!grid) {
    console.error('Timeline grid element not found');
    return;
  }

  const { data, skillColumns, skillSlugMap, skillColorMap, currentModality } = TimetableConfig;
  const isAllView = currentModality === 'all';

  // Validate data
  if (!Array.isArray(data)) {
    console.error('Timeline data is not an array:', data);
    grid.innerHTML = '<div class="empty-state">Error: Invalid timeline data format</div>';
    return;
  }

  // Filter out empty entries
  const filteredData = data.filter(e => {
    if (!e) return false;
    if (e.TIME === '00:00-00:00') return false;
    if (!e.start_time || !e.end_time) return false;
    return TimelineChart.hasAnyActiveSkill(e, skillColumns);
  });

  if (filteredData.length === 0) {
    grid.innerHTML = '<div class="empty-state">No active schedule entries found</div>';
    return;
  }

  // Render using shared module
  TimelineChart.render({
    gridEl: grid,
    headerEl: header,
    data: filteredData,
    skillColumns,
    skillSlugMap,
    skillColorMap,
    mergeModalities: isAllView,
    showCurrentTime: true,
    timeLineId: 'current-time-line'
  });

  // Set up time update interval
  setInterval(() => {
    TimelineChart.updateCurrentTimeLine(grid, 'current-time-line');
  }, 60000);
}

// Change modality while preserving skill filter
function changeModality(event, modality) {
  event.preventDefault();
  const url = new URL(window.location);
  const currentSkill = url.searchParams.get('skill') || 'all';

  // Build new URL with modality and current skill filter
  const newUrl = new URL(window.location.origin + '/timetable');
  newUrl.searchParams.set('modality', modality);
  if (currentSkill !== 'all') {
    newUrl.searchParams.set('skill', currentSkill);
  }

  // Navigate to new URL
  window.location.href = newUrl.toString();
}

// Filter by skill using shared module
function filterBySkill(skillSlug) {
  const grid = document.getElementById('timeline-grid');
  const buttons = document.querySelectorAll('.skill-filter-bar .filter-btn[data-skill]');

  // Update button states
  buttons.forEach(btn => {
    btn.classList.toggle('active', btn.dataset.skill === skillSlug);
  });

  // Update filter state
  grid.dataset.filter = skillSlug;

  // Use shared module for filtering
  TimelineChart.filterBySkill(grid, skillSlug);

  // Update URL without reloading page
  const url = new URL(window.location);
  if (skillSlug === 'all') {
    url.searchParams.delete('skill');
  } else {
    url.searchParams.set('skill', skillSlug);
  }
  window.history.pushState({}, '', url);
}

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
  injectDynamicStyles();
  buildTimeline();

  // Apply initial filter from config
  if (TimetableConfig.skillFilter && TimetableConfig.skillFilter !== 'all') {
    filterBySkill(TimetableConfig.skillFilter);
  }
});
