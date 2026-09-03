(() => {
  const params = new URLSearchParams(window.location.search);
  const state = {
    payment_type: null,
    payer_type: null,
    exchange_status: null,
    src: params.get('src') || 'direct'
  };

  const steps = [...document.querySelectorAll('.step')];
  const results = [...document.querySelectorAll('.result')];
  const bar = document.getElementById('bar');
  const existingAsset = document.getElementById('existingAsset');
  const debugPanel = document.getElementById('debugPanel');
  const debugLog = document.getElementById('debugLog');

  function emit(name, data = {}) {
    const payload = {
      event: name,
      src: state.src,
      ts: new Date().toISOString(),
      ...data
    };

    try {
      const key = 'rpg_event_log';
      const previous = JSON.parse(localStorage.getItem(key) || '[]');
      previous.push(payload);
      localStorage.setItem(key, JSON.stringify(previous.slice(-200)));
    } catch (_) {}

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(payload);
    window.dispatchEvent(new CustomEvent('rpg:event', { detail: payload }));

    if (debugLog) {
      const row = document.createElement('div');
      row.textContent = `${payload.event} · src=${payload.src}${payload.value ? ` · ${payload.value}` : ''}`;
      debugLog.prepend(row);
    }
  }

  function showStep(n) {
    steps.forEach(el => el.classList.toggle('active', Number(el.dataset.step) === n));
    results.forEach(el => el.classList.remove('active'));
    bar.style.width = `${Math.min(100, n * 33.333)}%`;
  }

  function showResult(id) {
    steps.forEach(el => el.classList.remove('active'));
    results.forEach(el => el.classList.remove('active'));
    bar.style.width = '100%';
    document.getElementById(id).classList.add('active');
  }

  document.querySelectorAll('.option').forEach(button => {
    button.addEventListener('click', () => {
      const field = button.dataset.field;
      const value = button.dataset.value;
      state[field] = value;
      emit(`${field}_select`, { value });

      if (field === 'payment_type') showStep(2);
      if (field === 'payer_type') showStep(3);
      if (field === 'exchange_status') {
        if (value === 'No exchange') {
          emit('new_to_exchange_identified', {
            payment_type: state.payment_type,
            payer_type: state.payer_type
          });
          showResult('resultNew');
        } else {
          existingAsset.textContent = state.payment_type === 'Not sure' ? 'the stablecoin' : state.payment_type;
          showResult('resultExisting');
        }
      }
    });
  });

  document.querySelectorAll('[data-back]').forEach(button => {
    button.addEventListener('click', () => showStep(Number(button.dataset.back)));
  });

  document.querySelectorAll('.reset').forEach(button => {
    button.addEventListener('click', () => {
      state.payment_type = null;
      state.payer_type = null;
      state.exchange_status = null;
      showStep(1);
      document.getElementById('guide').scrollIntoView({ behavior: 'smooth', block: 'start' });
      emit('quiz_reset');
    });
  });

  document.querySelectorAll('[data-track]').forEach(el => {
    el.addEventListener('click', () => emit(el.dataset.track));
  });

  document.getElementById('binanceCta').addEventListener('click', () => {
    emit('binance_referral_click', {
      payment_type: state.payment_type,
      payer_type: state.payer_type,
      exchange_status: state.exchange_status
    });
  });

  if (params.get('debug') === '1' && debugPanel) {
    debugPanel.hidden = false;
    document.getElementById('debugSource').textContent = state.src;
  }

  emit('page_view', {
    page_path: window.location.pathname,
    referrer: document.referrer || 'none'
  });
})();
