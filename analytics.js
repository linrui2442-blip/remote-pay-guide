(() => {
  const cfg = window.RPG_CONFIG || {};
  const id = (cfg.ga4MeasurementId || '').trim();

  if (id) {
    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
    document.head.appendChild(script);

    window.dataLayer = window.dataLayer || [];
    window.gtag = function(){ window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', id, {
      send_page_view: false,
      anonymize_ip: true
    });
  }

  window.addEventListener('rpg:event', (event) => {
    const payload = event.detail || {};
    if (!id || !window.gtag || !payload.event) return;

    const { event: eventName, ts, ...params } = payload;
    window.gtag('event', eventName, params);
  });
})();
