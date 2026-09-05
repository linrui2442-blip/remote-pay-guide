fetch('./data/dashboard_data.json')
  .then(response => response.json())
  .then(data => {
    document.getElementById('total').textContent = data.total_videos;

    const videos = data.videos || [];
    document.getElementById('content-table').innerHTML = videos.map(v => `
      <tr>
        <td>${v.content_id}</td>
        <td>${v.topic}</td>
        <td>${v.production_status}</td>
        <td>${v.publish_status}</td>
        <td>${v.lifecycle ? v.lifecycle.current_state : 'UNKNOWN'}</td>
      </tr>
    `).join('');

    document.getElementById('analytics-panel').innerHTML = videos.map(v => `
      <div>
        ${v.content_id}: ${JSON.stringify(v.analytics || {})}
      </div>
    `).join('');

    const health = data.system_health || {};
    document.getElementById('health-panel').textContent =
      `${health.system_status || 'UNKNOWN'} ${JSON.stringify(health.checks || [])}`;
  });
