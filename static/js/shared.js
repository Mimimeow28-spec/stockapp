// ── Theme System ──
const COLOR_VARS = [
  {label:'Background',  key:'--bg'},
  {label:'Cards',       key:'--surface'},
  {label:'Borders',     key:'--border'},
  {label:'Accent/Glow', key:'--cyan'},
  {label:'Text',        key:'--text'},
  {label:'Muted Text',  key:'--muted'},
  {label:'Positive',    key:'--green'},
  {label:'Negative',    key:'--red'},
];

function getCSSVar(k) { return getComputedStyle(document.documentElement).getPropertyValue(k).trim(); }
function setCSSVar(k, v) { document.documentElement.style.setProperty(k, v); }

function applyPreset(name) {
  document.documentElement.dataset.theme = name;
  COLOR_VARS.forEach(({key}) => document.documentElement.style.removeProperty(key));
  localStorage.setItem('mkt-theme', name);
  localStorage.removeItem('mkt-theme-overrides');
  if (typeof updateChartTheme === 'function') updateChartTheme();
  buildColorRows();
}

function resetTheme() {
  document.documentElement.dataset.theme = 'dark';
  COLOR_VARS.forEach(({key}) => document.documentElement.style.removeProperty(key));
  localStorage.removeItem('mkt-theme');
  localStorage.removeItem('mkt-theme-overrides');
  if (typeof updateChartTheme === 'function') updateChartTheme();
  buildColorRows();
}

function buildColorRows() {
  const container = document.getElementById('color-rows');
  if (!container) return;
  container.innerHTML = COLOR_VARS.map(({label, key}) => {
    const val = getCSSVar(key) || '#000000';
    return `<div class="color-row">
      <span class="color-label">${label}</span>
      <div class="color-swatch-wrap">
        <div class="color-swatch" style="background:${val}" onclick="document.getElementById('cp-${key.slice(2)}').click()"></div>
        <input type="color" id="cp-${key.slice(2)}" value="${val}" oninput="pickColor('${key}',this.value)">
      </div></div>`;
  }).join('');
}

function pickColor(key, val) {
  setCSSVar(key, val);
  const s = document.querySelector(`[onclick*="${key.slice(2)}"]`);
  if (s) s.style.background = val;
  if (typeof updateChartTheme === 'function') updateChartTheme();
  const overrides = {};
  COLOR_VARS.forEach(({key: k}) => {
    const v = document.documentElement.style.getPropertyValue(k);
    if (v) overrides[k] = v;
  });
  localStorage.setItem('mkt-theme-overrides', JSON.stringify(overrides));
}

function openTheme() {
  buildColorRows();
  document.getElementById('theme-panel').classList.add('open');
  document.getElementById('theme-overlay').classList.add('open');
}

function closeTheme() {
  document.getElementById('theme-panel').classList.remove('open');
  document.getElementById('theme-overlay').classList.remove('open');
}

// ── Matrix Rain ──
(function() {
  const c = document.getElementById('matrix-canvas');
  if (!c) return;
  const x = c.getContext('2d');
  const CH = '0123456789$%+-.,/*ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  let cols, drops, animId, lastFrame = 0;
  const FRAME_MS = 60;

  function resize() {
    c.width = window.innerWidth;
    c.height = window.innerHeight;
    cols = Math.floor(c.width / 13);
    drops = new Array(cols).fill(0);
  }
  resize();
  window.addEventListener('resize', resize);

  function draw(ts) {
    animId = requestAnimationFrame(draw);
    if (ts - lastFrame < FRAME_MS) return;
    lastFrame = ts;
    x.fillStyle = 'rgba(0,0,0,0.035)';
    x.fillRect(0, 0, c.width, c.height);
    x.fillStyle = 'rgba(0,255,136,0.13)';
    x.font = '13px monospace';
    drops.forEach((y, i) => {
      x.fillText(CH[Math.floor(Math.random() * CH.length)], i * 13, y * 13);
      if (y * 13 > c.height && Math.random() > .982) drops[i] = 0;
      drops[i] += 0.5;
    });
  }

  // Pause when tab is hidden to save CPU
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      cancelAnimationFrame(animId);
    } else {
      lastFrame = 0;
      animId = requestAnimationFrame(draw);
    }
  });

  animId = requestAnimationFrame(draw);
})();

// ── Ticker Search Autocomplete (shared factory) ──
function initTickerSearch(inputId, dropdownId, onSelect) {
  const input = document.getElementById(inputId);
  const dropdown = document.getElementById(dropdownId);
  if (!input || !dropdown) return;
  let debounce;

  input.addEventListener('input', () => {
    clearTimeout(debounce);
    const q = input.value.trim();
    if (q.length < 1) { dropdown.classList.remove('open'); return; }
    debounce = setTimeout(async () => {
      try {
        const res = await fetch('/api/search?q=' + encodeURIComponent(q));
        const data = await res.json();
        if (!data.results || data.results.length === 0) {
          dropdown.classList.remove('open'); return;
        }
        dropdown.innerHTML = data.results.map(r =>
          `<div class="td-item" data-sym="${r.symbol}">
             <span class="td-sym">${r.symbol}</span>
             <span class="td-desc">${r.name}</span>
           </div>`
        ).join('');
        dropdown.classList.add('open');
        dropdown.querySelectorAll('.td-item').forEach(item => {
          item.addEventListener('click', () => {
            dropdown.classList.remove('open');
            onSelect(item.dataset.sym, input);
          });
        });
      } catch(e) {}
    }, 180);
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') { dropdown.classList.remove('open'); input.blur(); }
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('#' + inputId) && !e.target.closest('#' + dropdownId)) {
      dropdown.classList.remove('open');
    }
  });
}
