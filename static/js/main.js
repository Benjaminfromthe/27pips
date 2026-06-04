// ============================================================
// 27pips — main.js  |  Full UI + Auth Logic
// ============================================================

// ── MODAL ──────────────────────────────────────────────────
function openModal(tab = 'login') {
  document.getElementById('modalOverlay').classList.add('active');
  document.body.style.overflow = 'hidden';
  switchTab(tab);
  clearAlert();
}
function closeModal() {
  document.getElementById('modalOverlay').classList.remove('active');
  document.body.style.overflow = '';
  clearAlert();
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── TAB SWITCHER ───────────────────────────────────────────
function switchTab(tab) {
  const loginForm  = document.getElementById('loginForm');
  const signupForm = document.getElementById('signupForm');
  const tabLogin   = document.getElementById('tabLogin');
  const tabSignup  = document.getElementById('tabSignup');
  if (!loginForm) return;

  if (tab === 'login') {
    loginForm.style.display  = 'flex';
    signupForm.style.display = 'none';
    tabLogin.classList.add('active');
    tabSignup.classList.remove('active');
  } else {
    loginForm.style.display  = 'none';
    signupForm.style.display = 'flex';
    tabSignup.classList.add('active');
    tabLogin.classList.remove('active');
  }
  clearAlert();
}

// ── ALERT HELPER ───────────────────────────────────────────
function showAlert(message, type = 'error') {
  const el = document.getElementById('modalAlert');
  if (!el) return;
  el.textContent  = message;
  el.className    = 'modal-alert ' + type;
  el.style.display = 'block';
}
function clearAlert() {
  const el = document.getElementById('modalAlert');
  if (el) { el.style.display = 'none'; el.textContent = ''; }
}

// ── LOGIN ──────────────────────────────────────────────────
async function submitLogin(event) {
  event.preventDefault();
  const btn   = document.getElementById('loginBtn2');
  const email = document.getElementById('loginEmail').value.trim();
  const pass  = document.getElementById('loginPassword').value;

  btn.textContent = i('signingIn');
  btn.classList.add('btn-loading');

  try {
    const res  = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pass })
    });
    const data = await res.json();

    if (data.success) {
      showAlert('Welcome back, ' + data.username + '! Refreshing...', 'success');
      setTimeout(() => window.location.reload(), 800);
    } else {
      showAlert(data.message || 'Login failed.');
      btn.textContent = i('signIn');
      btn.classList.remove('btn-loading');
    }
  } catch {
    showAlert(i('networkError'));
    btn.textContent = i('signIn');
    btn.classList.remove('btn-loading');
  }
}

// ── SIGNUP ─────────────────────────────────────────────────
async function submitSignup(event) {
  event.preventDefault();
  const btn      = document.getElementById('signupBtn');
  const username = document.getElementById('signupUsername').value.trim();
  const email    = document.getElementById('signupEmail').value.trim();
  const pass     = document.getElementById('signupPassword').value;

  btn.textContent = i('creatingAccount');
  btn.classList.add('btn-loading');

  try {
    const res  = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password: pass })
    });
    const data = await res.json();

    if (data.success) {
      showAlert('Account created! Welcome, ' + data.username + '!', 'success');
      setTimeout(() => window.location.reload(), 800);
    } else {
      showAlert(data.message || 'Registration failed.');
      btn.textContent = i('createAccount');
      btn.classList.remove('btn-loading');
    }
  } catch {
    showAlert(i('networkError'));
    btn.textContent = i('createAccount');
    btn.classList.remove('btn-loading');
  }
}

// ── LOGOUT ─────────────────────────────────────────────────
async function logoutUser() {
  await fetch('/auth/logout', { method: 'POST' });
  window.location.reload();
}

// ── USER DROPDOWN ──────────────────────────────────────────
function toggleUserMenu() {
  const menu = document.getElementById('userMenu');
  if (menu) menu.classList.toggle('open');
}
// Close dropdown when clicking outside
document.addEventListener('click', e => {
  const dropdown = document.getElementById('userDropdown');
  if (dropdown && !dropdown.contains(e.target)) {
    const menu = document.getElementById('userMenu');
    if (menu) menu.classList.remove('open');
  }
});

// ── MOBILE NAV ─────────────────────────────────────────────
function toggleNav() {
  document.getElementById('nav').classList.toggle('open');
}

// ── HEADER SCROLL EFFECT ───────────────────────────────────
window.addEventListener('scroll', () => {
  const header = document.getElementById('header');
  if (header) {
    header.style.boxShadow = window.scrollY > 20
      ? '0 4px 24px rgba(0,0,0,0.4)'
      : 'none';
  }
});

// ── I18N HELPER ────────────────────────────────────────────
// Returns a translated string from the server-injected I18N object,
// falling back to the English default if the page doesn't inject it.
const _i18nDefaults = {
  signInToAccess:    'Sign In to Access',
  newHere:           'New here?',
  createFreeAccount: 'Create free account',
  signingIn:         'Signing in…',
  creatingAccount:   'Creating account…',
  signIn:            'Sign In',
  createAccount:     'Create Account',
  networkError:      'Network error. Please try again.',
  noSignalsYet:      'No signals posted yet. Check back soon.',
  signalsError:      'Could not load signals.',
  tradesSignIn:      'Sign in to view your trades.',
  tradesError:       'Could not load trades.',
  tradeSaved:        '✅ Trade logged successfully!',
  tradeSaveFail:     'Failed to log trade.',
  trackerSetupFail:  'Setup failed.',
  trackerCreated:    '✅ Tracker account created!',
  journalNoTrades:   'No trades logged yet.',
  noTradesStart:     'No trades logged yet. Start journaling above.',
  tablePair:         'Pair',
  tableDir:          'Dir',
  tableEntry:        'Entry',
  tableExit:         'Exit',
  tablePips:         'Pips',
  tableOutcome:      'Outcome',
  tableDate:         'Date',
  trackerStartedAt:  'Started at',
  trackerProfitProg: 'Profit Progress',
  trackerDailyLimit: 'Limit',
  trackerMaxLimit:   'Limit',
  trackerMaxUsed:    '% of max limit used',
  trackerSafe:       '✅ Safe',
  trackerDanger:     '⚠️ Danger Zone',
  trackerBreached:   '🚨 LIMIT BREACHED',
  trackerTargetPct:  '🎉 Target Reached!',
  trackerKeepGoing:  'of target reached — Keep going 💪',
  equityTrades:      'trades',
  eduProgressText:   '{done} / {total} Lessons Completed',
};
function i(key) {
  return (window.I18N && window.I18N[key]) ? window.I18N[key] : (_i18nDefaults[key] || key);
}

// ── ROUTE PROTECTION — Journal & Tracker ───────────────────
// Check if user is logged in; if not, show auth gate overlay
async function checkAuthGates() {
  try {
    const res  = await fetch('/auth/me');
    const data = await res.json();
    if (!data.logged_in) {
      addAuthGate('journal', 'Trading Journal',   'Log your trades and track your performance.');
      addAuthGate('funded',  'Prop Firm Tracker', 'Track your challenge metrics in real time.');
    }
  } catch { /* silent — don't block UI */ }
}

function addAuthGate(sectionId, title, subtitle) {
  const section = document.getElementById(sectionId);
  if (!section) return;
  const container = section.querySelector('.journal-wrap, .tracker-grid');
  if (!container) return;

  container.style.position = 'relative';
  container.classList.add('auth-gate');

  const overlay = document.createElement('div');
  overlay.className = 'auth-gate-overlay';
  overlay.innerHTML = `
    <div style="font-size:2.5rem">🔒</div>
    <h3>${title}</h3>
    <p>${subtitle}</p>
    <button class="btn-primary" onclick="openModal('login')">${i('signInToAccess')}</button>
    <p style="font-size:0.8rem;color:var(--muted)">${i('newHere')} <a href="#" class="link-green" onclick="openModal('signup')">${i('createFreeAccount')}</a></p>
  `;
  container.appendChild(overlay);
}

// ── CHART PREVIEW ──────────────────────────────────────────
function previewChart(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {
    const preview = document.getElementById('chartPreview');
    preview.src = e.target.result;
    preview.style.display = 'block';
  };
  reader.readAsDataURL(file);
}

// ── TRADING JOURNAL ────────────────────────────────────────
const journalEntries = [];

function logTrade(event) {
  event.preventDefault();
  const asset     = document.getElementById('j-asset').value.trim();
  const direction = document.getElementById('j-direction').value;
  const date      = document.getElementById('j-date').value;
  const notes     = document.getElementById('j-notes').value.trim();

  if (!asset) { alert('Please enter an asset/pair.'); return; }

  const entry = { asset, direction, date: date || new Date().toLocaleDateString(), notes };
  journalEntries.unshift(entry);
  renderJournal();

  document.getElementById('j-asset').value = '';
  document.getElementById('j-notes').value = '';
  document.getElementById('j-date').value  = '';
  const preview = document.getElementById('chartPreview');
  if (preview) preview.style.display = 'none';
}

function renderJournal() {
  const log = document.getElementById('journalLog');
  if (!log) return;
  const noEntries = document.getElementById('noEntries');
  if (noEntries) noEntries.style.display = journalEntries.length ? 'none' : 'block';

  const existing = log.querySelectorAll('.log-entry');
  existing.forEach(e => e.remove());

  journalEntries.forEach(e => {
    const div = document.createElement('div');
    div.className = 'log-entry';
    div.innerHTML = `
      <div class="log-entry-header">
        <span class="log-asset">${e.asset}</span>
        <span class="${e.direction === 'BUY' ? 'log-dir-buy' : 'log-dir-sell'}">${e.direction}</span>
        <span style="font-size:0.75rem;color:var(--muted)">${e.date}</span>
      </div>
      ${e.notes ? `<p class="log-notes">${e.notes}</p>` : ''}
    `;
    log.appendChild(div);
  });
}

// ── ACTIVE NAV ON SCROLL ───────────────────────────────────
const sections = document.querySelectorAll('section[id]');
const navLinks  = document.querySelectorAll('.nav-link');
const navObserver = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      navLinks.forEach(link => {
        link.classList.toggle('active', link.getAttribute('href') === '#' + entry.target.id);
      });
    }
  });
}, { threshold: 0.35 });
sections.forEach(s => navObserver.observe(s));

const navStyle = document.createElement('style');
navStyle.textContent = '.nav-link.active{color:var(--green)!important;background:rgba(16,185,129,0.08);}';
document.head.appendChild(navStyle);

// ── INIT ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  checkAuthGates();
  console.log('27pips loaded');
});

// ============================================================
// PHASE 2 — Dynamic Journal & Tracker
// ============================================================

// ── SUBMIT TRADE ───────────────────────────────────────────
async function submitTrade(event) {
  event.preventDefault();
  const btn = document.getElementById('journalSubmitBtn');
  const msg = document.getElementById('journalMsg');
  btn.textContent = 'Saving...';
  btn.classList.add('btn-loading');

  const form = document.getElementById('journalForm');
  const fd   = new FormData(form);

  try {
    const res  = await fetch('/journal/add', { method: 'POST', body: fd });
    const data = await res.json();

    if (data.success) {
      msg.textContent  = i('tradeSaved');
      msg.className    = 'modal-alert success';
      msg.style.display = 'block';
      form.reset();
      const preview = document.getElementById('chartPreview');
      if (preview) preview.style.display = 'none';
      setTimeout(() => { msg.style.display = 'none'; }, 3000);
      loadJournalEntries();   // refresh table
      loadTrackerData();      // refresh tracker (balance updated)
    } else {
      msg.textContent  = data.message || i('tradeSaveFail');
      msg.className    = 'modal-alert error';
      msg.style.display = 'block';
    }
  } catch {
    msg.textContent  = i('networkError');
    msg.className    = 'modal-alert error';
    msg.style.display = 'block';
  }
  btn.textContent = 'Log This Trade';
  btn.classList.remove('btn-loading');
}

// ── LOAD JOURNAL ENTRIES ───────────────────────────────────
async function loadJournalEntries() {
  const wrap = document.getElementById('tradesTableWrap');
  if (!wrap) return;

  try {
    const res  = await fetch('/journal/entries');
    if (res.status === 401) {
      wrap.innerHTML = `<p class="text-muted">${i('tradesSignIn')}</p>`;
      return;
    }
    const trades = await res.json();

    if (!trades.length) {
      wrap.innerHTML = `<p class="text-muted" id="noEntries">${i('noTradesStart')}</p>`;
      return;
    }

    let html = `
      <div class="trades-table-wrap">
        <table class="trades-table">
          <thead>
            <tr>
              <th>${i('tablePair')}</th><th>${i('tableDir')}</th><th>${i('tableEntry')}</th><th>${i('tableExit')}</th>
              <th>${i('tablePips')}</th><th>${i('tableOutcome')}</th><th>${i('tableDate')}</th>
            </tr>
          </thead>
          <tbody>
    `;
    trades.forEach(t => {
      const outcomeClass = t.outcome === 'Win' ? 'outcome-win' : t.outcome === 'Loss' ? 'outcome-loss' : '';
      const dirClass     = t.direction === 'Buy' ? 'dir-buy' : 'dir-sell';
      const pipsColor    = (t.pips_gained_lost || 0) >= 0 ? 'text-green' : 'text-red';
      const date         = t.created_at ? t.created_at.split(' ')[0] : '—';
      html += `
        <tr>
          <td style="font-weight:600;color:var(--text)">${t.pair}</td>
          <td class="${dirClass}">${t.direction}</td>
          <td class="mono">${t.entry_price ?? '—'}</td>
          <td class="mono">${t.exit_price ?? '—'}</td>
          <td class="mono ${pipsColor}">${t.pips_gained_lost != null ? (t.pips_gained_lost > 0 ? '+' : '') + t.pips_gained_lost : '—'}</td>
          <td class="${outcomeClass}">${t.outcome || '—'}</td>
          <td style="color:var(--muted);font-size:0.8rem">${date}</td>
        </tr>
      `;
    });
    html += '</tbody></table></div>';
    wrap.innerHTML = html;
  } catch {
    wrap.innerHTML = `<p class="text-muted">${i('tradesError')}</p>`;
  }
}

// ── LOAD TRACKER DATA ──────────────────────────────────────
async function loadTrackerData() {
  const grid  = document.getElementById('trackerGrid');
  const setup = document.getElementById('trackerSetup');
  const alert = document.getElementById('drawdownAlert');
  if (!grid) return;

  try {
    const res  = await fetch('/tracker/challenge');
    const data = await res.json();

    if (res.status === 404 && data.setup_required) {
      grid.style.display  = 'none';
      if (setup) setup.style.display = 'block';
      return;
    }
    if (!res.ok) return;

    // Show grid, hide setup
    grid.style.display  = 'grid';
    if (setup) setup.style.display = 'none';

    // Risk alert
    if (alert) alert.style.display = data.drawdown_breached ? 'block' : 'none';

    // Balance card
    setText('t-balance',     '$' + data.current_balance.toLocaleString('en-US', {minimumFractionDigits:2}));
    setText('t-balance-sub', `${i('trackerStartedAt')} $` + data.account_size.toLocaleString('en-US', {minimumFractionDigits:2}));
    setBar ('t-profit-bar',  data.profit_percent);
    setText('t-profit-hint', `${i('trackerProfitProg')}: ${data.profit_progress}% / ${data.target_profit}% target`);

    // Daily drawdown card
    const dailyColor = data.daily_used_percent >= 80 ? 'text-red' : 'text-yellow';
    setValueColor('t-daily', `${data.daily_loss_today}%`, dailyColor);
    setText('t-daily-sub',  `${i('trackerDailyLimit')}: ${data.daily_drawdown_limit}%`);
    const dailyBar = document.getElementById('t-daily-bar');
    if (dailyBar) {
      dailyBar.style.width = Math.min(data.daily_used_percent, 100) + '%';
      dailyBar.className   = data.daily_used_percent >= 80
        ? 'tracker-progress-bar tracker-bar-danger'
        : 'tracker-progress-bar tracker-bar-yellow';
    }
    const safeLabel = data.drawdown_breached ? i('trackerBreached') : data.daily_used_percent >= 80 ? i('trackerDanger') : i('trackerSafe');
    setText('t-daily-hint', `${data.daily_used_percent}% of daily limit used — ${safeLabel}`);

    // Max drawdown card
    const maxColor = data.max_used_percent >= 80 ? 'text-red' : 'text-green';
    setValueColor('t-max', `${data.total_loss}%`, maxColor);
    setText('t-max-sub',  `${i('trackerMaxLimit')}: ${data.max_loss_limit}%`);
    setBar ('t-max-bar',  data.max_used_percent);
    setText('t-max-hint', `${data.max_used_percent}% ${i('trackerMaxUsed')}`);

    // Profit target card
    setText('t-profit',     `${data.profit_progress}%`);
    setText('t-profit-sub', `${i('trackerDailyLimit')}: ${data.target_profit}%`);
    setBar ('t-target-bar', data.profit_percent);
    const progressLabel = data.profit_percent >= 100 ? i('trackerTargetPct') : `${data.profit_percent}% ${i('trackerKeepGoing')}`;
    setText('t-target-hint', progressLabel);

  } catch {
    // Silent fail — don't break the page
  }
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
function setBar(id, pct) {
  const el = document.getElementById(id);
  if (el) el.style.width = Math.min(pct, 100) + '%';
}
function setValueColor(id, text, colorClass) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className   = 'tracker-value ' + colorClass;
}

// ── TRACKER SETUP ──────────────────────────────────────────
async function setupTracker() {
  const balance = parseFloat(document.getElementById('setupBalance').value);
  const msg     = document.getElementById('setupMsg');

  if (!balance || balance <= 0) {
    msg.textContent  = 'Please enter a valid starting balance.';
    msg.className    = 'modal-alert error';
    msg.style.display = 'block';
    return;
  }

  const res  = await fetch('/tracker/setup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ starting_balance: balance })
  });
  const data = await res.json();

  if (data.success) {
    msg.textContent  = i('trackerCreated');
    msg.className    = 'modal-alert success';
    msg.style.display = 'block';
    setTimeout(() => loadTrackerData(), 800);
  } else {
    msg.textContent  = data.message || i('trackerSetupFail');
    msg.className    = 'modal-alert error';
    msg.style.display = 'block';
  }
}

// ── INIT DYNAMIC SECTIONS ──────────────────────────────────
// Only run if user is logged in (Jinja injects this flag)
document.addEventListener('DOMContentLoaded', () => {
  // Check if journal form exists (means user is logged in)
  if (document.getElementById('journalForm')) {
    loadJournalEntries();
    loadTrackerData();
  }
});

// ============================================================
// PHASE 3 — Dynamic Signals Feed
// ============================================================

async function loadSignals() {
  const tbody = document.getElementById('signalsBody');
  if (!tbody) return;

  try {
    const res  = await fetch('/signals/');
    const json = await res.json();

    // Support both old array format and new {signals, user_tier} format
    const signals   = json.signals || json;
    const user_tier = json.user_tier || window.USER_TIER || 'guest';

    if (!signals.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:24px">${i('noSignalsYet')}</td></tr>`;
      return;
    }

    tbody.innerHTML = signals.map(s => {
      const actionBadge = s.action === 'BUY'
        ? '<span class="badge-buy">BUY</span>'
        : '<span class="badge-sell">SELL</span>';

      const statusMap = {
        'Active':      '<span class="status-badge status-active">ACTIVE</span>',
        'Pending':     '<span class="status-badge status-pending">PENDING</span>',
        'TP Hit':      '<span class="status-badge status-tp">TP HIT ✅</span>',
        'Stopped Out': '<span class="status-badge status-stopped">STOPPED</span>',
      };
      const statusBadge = statusMap[s.status] || `<span class="status-badge">${s.status}</span>`;

      const dotClass = s.pair.includes('XAU') || s.pair.includes('GOLD') ? 'asset-dot asset-gold'
                     : s.pair.includes('NAS') || s.pair.includes('US30') ? 'asset-dot asset-blue'
                     : 'asset-dot';

      // Premium gating
      const locked = '<span class="premium-lock">🔒 Premium</span>';
      const entry  = s.gated ? locked : (s.entry_price ?? '—');
      const sl     = s.gated ? locked : `<span class="text-red">${s.stop_loss ?? '—'}</span>`;
      const tp1    = s.gated ? locked : `<span class="text-green">${s.take_profit_1 ?? '—'}</span>`;
      const tp2    = s.gated ? locked : `<span class="text-green">${s.take_profit_2 ?? '—'}</span>`;

      const premiumBadge = s.is_premium ? '<span class="signal-premium-badge">👑</span>' : '';

      return `
        <tr ${s.gated ? 'class="signal-gated"' : ''}>
          <td class="asset-cell"><span class="${dotClass}"></span>${s.pair}${premiumBadge}</td>
          <td>${actionBadge}</td>
          <td class="mono">${entry}</td>
          <td class="mono">${sl}</td>
          <td class="mono">${tp1}</td>
          <td class="mono">${tp2}</td>
          <td>${statusBadge}</td>
        </tr>
      `;
    }).join('');

  } catch {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:24px">${i('signalsError')}</td></tr>`;
  }
}

// Load signals on page load
document.addEventListener('DOMContentLoaded', () => {
  loadSignals();
  // Refresh signals every 60 seconds
  setInterval(loadSignals, 60000);
});

// ============================================================
// PHASE 4 — Education Progress Widget on Homepage
// ============================================================

async function loadEducationProgress() {
  // Only run if the edu-grid exists on the page
  const eduGrid = document.querySelector('.edu-grid');
  if (!eduGrid) return;

  try {
    const res  = await fetch('/education/progress');
    const data = await res.json();
    if (!data.logged_in || !data.progress.length) return;

    // Update the first edu-card progress bar with real data
    const cards = eduGrid.querySelectorAll('.edu-card');
    data.progress.forEach((course, i) => {
      if (!cards[i]) return;
      const bar  = cards[i].querySelector('.progress-bar');
      const text = cards[i].querySelector('.progress-text');
      if (bar)  bar.style.width = course.pct + '%';
      if (text) text.textContent = i('eduProgressText')
        .replace('{done}', course.completed)
        .replace('{total}', course.total);
    });
  } catch { /* silent */ }
}

document.addEventListener('DOMContentLoaded', () => {
  loadEducationProgress();
});

// ============================================================
// PHASE 5 — Equity Curve Chart (Chart.js)
// ============================================================

let equityChartInstance = null;

async function loadEquityChart() {
  const canvas = document.getElementById('equityChart');
  const empty  = document.getElementById('equityEmpty');
  const stats  = document.getElementById('equityStats');
  if (!canvas) return;

  try {
    const res  = await fetch('/api/analytics/equity');
    if (res.status === 401) return;   // not logged in — silent
    const data = await res.json();

    if (!data.success) return;

    // No trades yet — show empty state
    if (!data.has_data) {
      canvas.style.display = 'none';
      if (empty) empty.style.display = 'block';
      return;
    }

    // Show chart + stats
    canvas.style.display = 'block';
    if (empty) empty.style.display = 'none';
    if (stats) stats.style.display = 'grid';

    // Populate stat cards
    const fmt = v => '$' + v.toLocaleString('en-US', {minimumFractionDigits: 2});
    setText('eq-start',  fmt(data.starting_balance));
    setText('eq-current', fmt(data.current_balance));
    const pnlEl = document.getElementById('eq-pnl');
    if (pnlEl) {
      pnlEl.textContent = (data.net_pnl >= 0 ? '+' : '') + fmt(data.net_pnl) + ` (${data.net_pct}%)`;
      pnlEl.style.color = data.is_profit ? 'var(--green)' : 'var(--red)';
    }
    setText('eq-trades', data.total_trades + ' ' + i('equityTrades'));

    // Chart colors
    const lineColor   = data.is_profit ? '#10b981' : '#ef4444';
    const gradientTop = data.is_profit ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)';

    // Destroy previous instance if exists
    if (equityChartInstance) {
      equityChartInstance.destroy();
      equityChartInstance = null;
    }

    const ctx = canvas.getContext('2d');

    // Gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, gradientTop);
    gradient.addColorStop(1, 'rgba(0,0,0,0)');

    equityChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [{
          label: 'Account Balance ($)',
          data: data.data,
          borderColor: lineColor,
          borderWidth: 2.5,
          backgroundColor: gradient,
          fill: true,
          tension: 0.3,
          pointRadius: data.data.length > 30 ? 0 : 4,
          pointHoverRadius: 6,
          pointBackgroundColor: lineColor,
          pointBorderColor: '#1e293b',
          pointBorderWidth: 2,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1e293b',
            borderColor: '#334155',
            borderWidth: 1,
            titleColor: '#94a3b8',
            bodyColor: '#f1f5f9',
            bodyFont: { weight: '700', size: 14 },
            padding: 12,
            callbacks: {
              label: ctx => ' $' + ctx.parsed.y.toLocaleString('en-US', {minimumFractionDigits: 2})
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(51,65,85,0.5)', drawBorder: false },
            ticks: { color: '#94a3b8', font: { size: 11 }, maxTicksLimit: 8 }
          },
          y: {
            grid: { color: 'rgba(51,65,85,0.5)', drawBorder: false },
            ticks: {
              color: '#94a3b8',
              font: { size: 11 },
              callback: v => '$' + v.toLocaleString('en-US', {minimumFractionDigits: 0})
            }
          }
        }
      }
    });

  } catch (err) {
    console.error('Equity chart error:', err);
  }
}

// Load chart on page load
document.addEventListener('DOMContentLoaded', () => {
  loadEquityChart();
});

// ============================================================
// LANGUAGE — i18n (theme handled by theme.js)
// ============================================================

// ── Language dropdown ──────────────────────────────────────
function toggleLangMenu() {
  const menu = document.getElementById('langMenu');
  const btn  = document.getElementById('langBtn');
  if (!menu) return;
  const open = menu.classList.toggle('open');
  if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}

// Close lang menu on outside click
document.addEventListener('click', e => {
  const dd = document.getElementById('langDropdown');
  if (dd && !dd.contains(e.target)) {
    const menu = document.getElementById('langMenu');
    const btn  = document.getElementById('langBtn');
    if (menu) menu.classList.remove('open');
    if (btn) btn.setAttribute('aria-expanded', 'false');
  }
});


// ============================================================
// THEME & LANGUAGE — Dark/Light toggle + i18n
// ============================================================

// ── THEME TOGGLE ───────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('27pips-theme', theme);
  const btn = document.getElementById('themeBtn');
  if (btn) btn.textContent = theme === 'light' ? '🌙' : '☀️';
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

// Apply saved theme immediately on page load (before paint)
(function() {
  const saved = localStorage.getItem('27pips-theme') || 'dark';
  applyTheme(saved);
})();

// ── LANGUAGE DROPDOWN ──────────────────────────────────────
function toggleLangMenu() {
  const menu = document.getElementById('langMenu');
  if (menu) menu.classList.toggle('open');
}

// Close lang menu when clicking outside
document.addEventListener('click', e => {
  const dropdown = document.getElementById('langDropdown');
  if (dropdown && !dropdown.contains(e.target)) {
    const menu = document.getElementById('langMenu');
    if (menu) menu.classList.remove('open');
  }
});


// ============================================================
// SITE-WIDE SEARCH  (debounced, keyboard-navigable dropdown)
// ============================================================

(function () {
  'use strict';

  const DEBOUNCE_MS = 300;
  const MIN_CHARS   = 2;

  let _debounceTimer = null;
  let _lastQuery     = '';
  let _focusedIndex  = -1;

  // Translated strings injected server-side via window.I18N
  function _t(key, fallback) {
    return (window.I18N && window.I18N[key]) ? window.I18N[key] : fallback;
  }

  // ── DOM refs (lazy — elements may not exist on every page) ────────
  function _el(id) { return document.getElementById(id); }

  // ── Open / close dropdown ─────────────────────────────────────────
  function _openDropdown(html) {
    const dd    = _el('searchDropdown');
    const input = _el('siteSearchInput');
    if (!dd || !input) return;
    dd.innerHTML = html;
    dd.classList.add('open');
    input.setAttribute('aria-expanded', 'true');
    _focusedIndex = -1;
  }

  function _closeDropdown() {
    const dd    = _el('searchDropdown');
    const input = _el('siteSearchInput');
    if (dd)    { dd.classList.remove('open'); dd.innerHTML = ''; }
    if (input) { input.setAttribute('aria-expanded', 'false'); }
    _focusedIndex = -1;
  }

  // ── Build result HTML ─────────────────────────────────────────────
  function _renderResults(data) {
    const results = data.results || [];

    if (!results.length) {
      return `<div class="search-empty">
        <span>🔍</span>
        ${_t('search_no_results', 'No results found')}
        <strong style="color:var(--text-primary)">"${_escHtml(data.query)}"</strong>
      </div>`;
    }

    // Group by type
    const groups = {};
    const typeLabels = {
      lesson:  _t('search_type_lesson',    'Lesson'),
      course:  _t('search_type_course',    'Course'),
      signal:  _t('search_type_signal',    'Signal'),
      tool:    _t('search_type_tool',      'Feature'),
    };

    results.forEach(r => {
      if (!groups[r.type]) groups[r.type] = [];
      groups[r.type].push(r);
    });

    let html = '';
    let itemIndex = 0;
    Object.entries(groups).forEach(([type, items]) => {
      if (html) html += '<hr class="search-divider">';
      html += `<div class="search-section-label">${typeLabels[type] || type}</div>`;
      items.forEach(item => {
        html += `<a href="${_escHtml(item.url)}"
                    class="search-result-item"
                    role="option"
                    tabindex="-1"
                    data-index="${itemIndex}"
                    onclick="_closeSearch()">
          <span class="search-result-icon">${item.icon}</span>
          <span class="search-result-text">
            <p class="search-result-title">${_escHtml(item.title)}</p>
            ${item.subtitle ? `<p class="search-result-sub">${_escHtml(item.subtitle)}</p>` : ''}
          </span>
          ${item.meta ? `<span class="search-result-meta">${_escHtml(item.meta)}</span>` : ''}
        </a>`;
        itemIndex++;
      });
    });

    return html;
  }

  function _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Fetch results from backend ────────────────────────────────────
  async function _fetchResults(q) {
    try {
      const res  = await fetch(`/search/?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      _openDropdown(_renderResults(data));
    } catch {
      _closeDropdown();
    }
  }

  // ── Input handler (debounced) ─────────────────────────────────────
  function _onInput(e) {
    const q     = e.target.value.trim();
    const clear = _el('searchClear');
    if (clear) clear.classList.toggle('visible', q.length > 0);

    if (q.length < MIN_CHARS) {
      _closeDropdown();
      _lastQuery = '';
      return;
    }
    if (q === _lastQuery) return;
    _lastQuery = q;

    clearTimeout(_debounceTimer);
    _openDropdown(`<div class="search-loading">${_t('loading', 'Loading…')}</div>`);
    _debounceTimer = setTimeout(() => _fetchResults(q), DEBOUNCE_MS);
  }

  // ── Keyboard navigation ───────────────────────────────────────────
  function _onKeydown(e) {
    const dd    = _el('searchDropdown');
    const items = dd ? dd.querySelectorAll('.search-result-item') : [];

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      _focusedIndex = Math.min(_focusedIndex + 1, items.length - 1);
      if (items[_focusedIndex]) items[_focusedIndex].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      _focusedIndex = Math.max(_focusedIndex - 1, 0);
      if (items[_focusedIndex]) items[_focusedIndex].focus();
      else _el('siteSearchInput').focus();
    } else if (e.key === 'Escape') {
      _closeSearch();
    }
  }

  // ── Clear & close helpers (global — called from HTML onclick) ─────
  window.clearSearch = function () {
    const input = _el('siteSearchInput');
    const clear = _el('searchClear');
    if (input) { input.value = ''; input.focus(); }
    if (clear) clear.classList.remove('visible');
    _closeDropdown();
    _lastQuery = '';
  };

  window._closeSearch = function () {
    _closeDropdown();
  };

  // ── Init ──────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    const input = _el('siteSearchInput');
    if (!input) return;   // page has no search bar

    input.addEventListener('input',   _onInput);
    input.addEventListener('keydown', _onKeydown);

    // Close when clicking outside the search widget
    document.addEventListener('click', function (e) {
      const wrap = _el('searchWrap');
      if (wrap && !wrap.contains(e.target)) {
        _closeDropdown();
      }
    });
  });
}());
