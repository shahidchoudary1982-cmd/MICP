const state = {
  projects: [],
  sheets: [],
  selectedProjectId: null,
  charts: {},
};

const API = {
  projects: '/api/projects',
  import: '/api/projects/import',
  sheets: (id) => `/api/projects/${id}/sheets`,
  records: (id, params) => `/api/projects/${id}/records${params}`,
  stats: (id) => `/api/projects/${id}/stats`,
  logPreview: '/api/logs/preview',
};

function showStatus(message, type = 'success') {
  const el = document.querySelector('#status');
  if (!el) return;
  el.textContent = message;
  el.className = `status-message status-${type}`;
}

function showLogStatus(message, type = 'success') {
  const el = document.querySelector('#logStatus');
  if (!el) return;
  el.hidden = !message;
  el.textContent = message;
  el.className = message ? `status-message status-${type}` : 'status-message';
}

function resetLogPreview() {
  const container = document.querySelector('#logPreview');
  if (!container) return;
  container.hidden = true;
  const notes = container.querySelector('[data-field="notes"]');
  if (notes) notes.innerHTML = '';
}

function renderLogPreview(data) {
  const container = document.querySelector('#logPreview');
  if (!container) return;

  const assignText = (field, value) => {
    const element = container.querySelector(`[data-field="${field}"]`);
    if (element) {
      element.textContent = value;
    }
  };

  assignText('file_name', data.file_name || '');
  assignText('format', data.format || '');
  assignText('well_names', (data.well_names || []).join(', ') || 'Not found');
  assignText('curve_names', (data.curve_names || []).join(', ') || 'Not found');

  let depthText = 'Not available';
  const { depth_min: min, depth_max: max, depth_unit: unit } = data;
  if (min != null || max != null) {
    const parts = [];
    if (min != null) parts.push(`${min}`);
    parts.push('to');
    if (max != null) parts.push(`${max}`);
    depthText = parts.join(' ');
  }
  if (unit && depthText !== 'Not available') {
    depthText = `${depthText} ${unit}`;
  }
  assignText('depth_range', depthText);

  const notes = container.querySelector('[data-field="notes"]');
  if (notes) {
    notes.innerHTML = '';
    (data.notes || []).forEach((note) => {
      const item = document.createElement('li');
      item.textContent = note;
      notes.appendChild(item);
    });
  }

  container.hidden = false;
}

async function fetchProjects() {
  const response = await fetch(API.projects);
  if (!response.ok) {
    showStatus('Failed to load projects', 'error');
    return;
  }
  state.projects = await response.json();
  renderProjectOptions();
}

function renderProjectOptions() {
  const select = document.querySelector('#projectSelect');
  select.innerHTML = '<option value="">Select project</option>';
  state.projects.forEach((project) => {
    const option = document.createElement('option');
    option.value = project.id;
    option.textContent = `${project.name} (${new Date(project.created_at).toLocaleString()})`;
    select.appendChild(option);
  });
  if (state.selectedProjectId) {
    select.value = state.selectedProjectId;
  }
}

async function onProjectChange(event) {
  const projectId = event.target.value;
  if (!projectId) {
    state.selectedProjectId = null;
    state.sheets = [];
    renderSheetOptions();
    clearTable();
    clearCharts();
    return;
  }
  state.selectedProjectId = projectId;
  await fetchSheets(projectId);
  await refreshData();
}

async function fetchSheets(projectId) {
  const response = await fetch(API.sheets(projectId));
  if (!response.ok) {
    showStatus('Failed to load sheets', 'error');
    return;
  }
  state.sheets = await response.json();
  renderSheetOptions();
}

function renderSheetOptions() {
  const select = document.querySelector('#sheetSelect');
  select.innerHTML = '<option value="">All sheets</option>';
  state.sheets.forEach((sheet) => {
    const option = document.createElement('option');
    option.value = sheet.name;
    option.textContent = sheet.name;
    select.appendChild(option);
  });
}

async function refreshData() {
  if (!state.selectedProjectId) return;
  await Promise.all([fetchRecords(), fetchStats()]);
}

function buildQueryParams() {
  const params = new URLSearchParams();
  const sheetName = document.querySelector('#sheetSelect').value;
  const rowStart = document.querySelector('#rowStart').value;
  const rowEnd = document.querySelector('#rowEnd').value;
  const limit = document.querySelector('#recordLimit').value;

  if (sheetName) params.append('sheet', sheetName);
  if (rowStart) params.append('row_start', rowStart);
  if (rowEnd) params.append('row_end', rowEnd);
  if (limit) params.append('limit', limit);

  const query = params.toString();
  return query ? `?${query}` : '';
}

async function fetchRecords() {
  const params = buildQueryParams();
  const url = API.records(state.selectedProjectId, params);
  const response = await fetch(url);
  if (!response.ok) {
    showStatus('Failed to load records', 'error');
    return;
  }
  const records = await response.json();
  renderTable(records);
}

async function fetchStats() {
  const response = await fetch(API.stats(state.selectedProjectId));
  if (!response.ok) {
    showStatus('Failed to load statistics', 'error');
    return;
  }
  const stats = await response.json();
  renderCharts(stats);
}

function renderTable(records) {
  const tbody = document.querySelector('#recordsTable tbody');
  tbody.innerHTML = '';
  if (!records.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.textContent = 'No records found for the current filters.';
    row.appendChild(cell);
    tbody.appendChild(row);
    return;
  }

  records.forEach((record) => {
    const row = document.createElement('tr');
    const columns = [
      record.row_index,
      record.sheet_name || '',
      record.company || '',
      record.field || '',
      record.wellName || '',
      record.formation || '',
      summariseRow(record.data),
    ];
    columns.forEach((value) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
}

function summariseRow(data) {
  const entries = Object.entries(data || {});
  if (!entries.length) return '';
  return entries
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${value}`)
    .join(' | ');
}

function clearTable() {
  const tbody = document.querySelector('#recordsTable tbody');
  if (tbody) tbody.innerHTML = '';
}

function clearCharts() {
  Object.values(state.charts).forEach((chart) => chart.destroy());
  state.charts = {};
}

function renderCharts(stats) {
  if (!stats) return;
  renderChart('companyChart', 'Wells by Company', stats.wells_by_company, 'bar');
  renderChart('fieldChart', 'Wells by Field', stats.wells_by_field, 'bar');
  renderChart('formationChart', 'Wells by Formation', stats.wells_by_formation, 'bar');
  renderChart('sheetChart', 'Records per Sheet', stats.wells_by_sheet, 'doughnut');
  renderChart('rowBucketChart', 'Records per Row Bucket', stats.wells_per_row_bucket, 'line');
  renderChart('sheetRowChart', 'Row Counts per Sheet', stats.sheet_row_counts, 'bar', true);
}

function renderChart(elementId, label, dataset, type = 'bar', horizontal = false) {
  const ctx = document.getElementById(elementId);
  if (!ctx) return;
  const dataEntries = Object.entries(dataset || {});
  const labels = dataEntries.map(([key]) => key);
  const values = dataEntries.map(([, value]) => value);

  if (state.charts[elementId]) {
    state.charts[elementId].destroy();
  }

  state.charts[elementId] = new Chart(ctx, {
    type,
    data: {
      labels,
      datasets: [
        {
          label,
          data: values,
          backgroundColor: '#62b6cb',
          borderColor: '#1b4965',
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: horizontal ? 'y' : 'x',
      scales: {
        y: {
          beginAtZero: true,
        },
      },
      plugins: {
        legend: { display: type !== 'bar' || horizontal },
      },
    },
  });
}

function setupEventListeners() {
  document.querySelector('#projectSelect').addEventListener('change', onProjectChange);
  document.querySelector('#sheetSelect').addEventListener('change', refreshData);
  document.querySelector('#rowStart').addEventListener('change', fetchRecords);
  document.querySelector('#rowEnd').addEventListener('change', fetchRecords);
  document.querySelector('#recordLimit').addEventListener('change', fetchRecords);

  document.querySelector('#reloadButton').addEventListener('click', () => {
    refreshData();
  });

  const form = document.querySelector('#uploadForm');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const response = await fetch(API.import, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      showStatus(detail.detail || 'Failed to upload file', 'error');
      return;
    }

    const project = await response.json();
    showStatus(`Uploaded project "${project.name}" successfully.`, 'success');
    form.reset();
    await fetchProjects();
    state.selectedProjectId = project.id;
    document.querySelector('#projectSelect').value = project.id;
    await fetchSheets(project.id);
    await refreshData();
  });
}

function setupLogForm() {
  const logForm = document.querySelector('#logForm');
  if (!logForm) return;

  logForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    showLogStatus('Analysing log…', 'info');
    resetLogPreview();

    const formData = new FormData(logForm);
    const response = await fetch(API.logPreview, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      showLogStatus(detail.detail || 'Failed to analyse log file.', 'error');
      return;
    }

    const data = await response.json();
    showLogStatus('Log analysed successfully.', 'success');
    renderLogPreview(data);
    logForm.reset();
  });

  logForm.addEventListener('change', () => {
    showLogStatus('', 'info');
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  setupLogForm();
  resetLogPreview();
  showLogStatus('', 'info');
  await fetchProjects();
});
