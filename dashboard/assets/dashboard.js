const LIFECYCLE_STATES = [
  'CREATED',
  'SCRIPT_READY',
  'VIDEO_GENERATED',
  'QUALITY_CHECKED',
  'READY_TO_PUBLISH',
  'PUBLISHED',
  'ANALYTICS_TRACKING',
  'COMPLETED',
  'FAILED',
];

const normalize = value => {
  if (value === null || value === undefined || value === '') return 'UNKNOWN';
  return String(value);
};

const canonical = value => normalize(value).trim().toUpperCase();

const escapeHtml = value => normalize(value)
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#039;');

const badgeClass = value => {
  const status = canonical(value);
  if (['PUBLISHED', 'SUCCEEDED', 'SUCCESS', 'COMPLETED', 'HEALTHY', 'OK'].includes(status)) return 'success';
  if (status.includes('FAIL') || status.includes('ERROR') || status.includes('UNHEALTHY')) return 'danger';
  if (status === 'UNKNOWN' || status.includes('PENDING') || status.includes('SCHEDULED')) return 'warning';
  return 'info';
};

const isPublished = video => {
  const publish = canonical(video.publish_status);
  const lifecycle = canonical(video.lifecycle?.current_state);
  return ['PUBLISHED', 'SUCCEEDED', 'SUCCESS', 'COMPLETED'].includes(publish)
    || ['PUBLISHED', 'ANALYTICS_TRACKING', 'COMPLETED'].includes(lifecycle);
};

const isFailed = video => [
  video.production_status,
  video.publish_status,
  video.lifecycle?.current_state,
].some(value => canonical(value).includes('FAIL'));

function renderLifecycle(videos) {
  const counts = Object.fromEntries(LIFECYCLE_STATES.map(state => [state, 0]));
  videos.forEach(video => {
    const state = canonical(video.lifecycle?.current_state);
    if (Object.hasOwn(counts, state)) counts[state] += 1;
  });

  document.getElementById('lifecycle').innerHTML = LIFECYCLE_STATES.map(state => `
    <div class="lifecycle-item">
      <span class="lifecycle-state">${state}</span>
      <strong class="lifecycle-count">${counts[state]}</strong>
    </div>
  `).join('');
}

function renderContent(videos) {
  const tbody = document.getElementById('content-table');
  const empty = document.getElementById('content-empty');
  tbody.innerHTML = videos.map(video => `
    <tr>
      <td class="code">${escapeHtml(video.content_id)}</td>
      <td>${escapeHtml(video.topic)}</td>
      <td><span class="badge ${badgeClass(video.production_status)}">${escapeHtml(video.production_status)}</span></td>
      <td><span class="badge ${badgeClass(video.publish_status)}">${escapeHtml(video.publish_status)}</span></td>
      <td><span class="badge ${badgeClass(video.lifecycle?.current_state)}">${escapeHtml(video.lifecycle?.current_state)}</span></td>
    </tr>
  `).join('');
  empty.hidden = videos.length > 0;
}

function renderAnalytics(videos) {
  const target = document.getElementById('analytics-panel');
  if (!videos.length) {
    target.innerHTML = '<div class="empty-state">No analytics records available.</div>';
    return;
  }

  target.innerHTML = `<div class="analytics-grid">${videos.map(video => {
    const analytics = video.analytics || {};
    return `
      <article class="analytics-card">
        <div class="content-name">${escapeHtml(video.content_id)}</div>
        <div class="analytics-meta">
          <span>Platform<br><strong>${escapeHtml(analytics.platform)}</strong></span>
          <span>Views<br><strong>${escapeHtml(analytics.views ?? 0)}</strong></span>
          <span>Clicks<br><strong>${escapeHtml(analytics.clicks ?? 0)}</strong></span>
          <span>Likes<br><strong>${escapeHtml(analytics.likes ?? 0)}</strong></span>
          <span>Shares<br><strong>${escapeHtml(analytics.shares ?? 0)}</strong></span>
          <span>Conversion<br><strong>${escapeHtml(analytics.conversion ?? 0)}</strong></span>
        </div>
      </article>`;
  }).join('')}</div>`;
}

function renderHealth(health) {
  const status = normalize(health?.system_status);
  const checks = Array.isArray(health?.checks) ? health.checks : [];
  const target = document.getElementById('health-panel');

  target.innerHTML = `
    <div class="health-summary">
      <span>Overall status</span>
      <span class="badge ${badgeClass(status)}">${escapeHtml(status)}</span>
    </div>
    <div class="health-list">
      ${checks.length ? checks.map(check => `
        <div class="health-row">
          <span>${escapeHtml(check.component)}</span>
          <span class="badge ${badgeClass(check.status)}">${escapeHtml(check.status)}</span>
        </div>
      `).join('') : '<div class="empty-state">No health checks available.</div>'}
    </div>`;
}

function renderDashboard(data) {
  const videos = Array.isArray(data.videos) ? data.videos : [];
  const published = videos.filter(isPublished).length;
  const failed = videos.filter(isFailed).length;
  const production = Math.max(videos.length - published - failed, 0);
  const health = data.system_health || {};

  document.getElementById('total').textContent = Number.isFinite(data.total_videos) ? data.total_videos : videos.length;
  document.getElementById('published').textContent = published;
  document.getElementById('production').textContent = production;
  document.getElementById('failed').textContent = failed;
  document.getElementById('system-health').textContent = normalize(health.system_status);
  document.getElementById('system-health').className = `metric-value metric-value-text ${badgeClass(health.system_status)}`;
  document.getElementById('generated-at').textContent = `Generated: ${data.generated_at ? normalize(data.generated_at) : '—'}`;

  renderLifecycle(videos);
  renderContent(videos);
  renderAnalytics(videos);
  renderHealth(health);
}

fetch('./data/dashboard_data.json')
  .then(response => {
    if (!response.ok) throw new Error(`dashboard_data.json HTTP ${response.status}`);
    return response.json();
  })
  .then(renderDashboard)
  .catch(error => {
    const banner = document.getElementById('dashboard-error');
    banner.hidden = false;
    banner.textContent = `Dashboard data failed to load: ${error.message}`;
    renderDashboard({ total_videos: 0, videos: [], system_health: {} });
  });
