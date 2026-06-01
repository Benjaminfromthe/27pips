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

  btn.textContent = 'Signing in...';
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
      btn.textContent = 'Sign In';
      btn.classList.remove('btn-loading');
    }
  } catch {
    showAlert('Network error. Please try again.');
    btn.textContent = 'Sign In';
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

  btn.textContent = 'Creating account...';
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
      btn.textContent = 'Create Account';
      btn.classList.remove('btn-loading');
    }
  } catch {
    showAlert('Network error. Please try again.');
    btn.textContent = 'Create Account';
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

// ── ROUTE PROTECTION — Journal & Tracker ───────────────────
// Check if user is logged in; if not, show auth gate overlay
async function checkAuthGates() {
  try {
    const res  = await fetch('/auth/me');
    const data = await res.json();
    if (!data.logged_in) {
      addAuthGate('journal',  'Trading Journal',      'Log your trades and track your performance.');
      addAuthGate('funded',   'Prop Firm Tracker',    'Track your challenge metrics in real time.');
    }
  } catch { /* silent — don't block UI */ }
}

function addAuthGate(sectionId, title, subtitle) {
  const section = document.getElementById(sectionId);
  if (!section) return;

  // Find the content wrapper inside the section
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
    <button class="btn-primary" onclick="openModal('login')">Sign In to Access</button>
    <p style="font-size:0.8rem;color:var(--muted)">New here? <a href="#" class="link-green" onclick="openModal('signup')">Create free account</a></p>
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
      msg.textContent  = '✅ Trade logged successfully!';
      msg.className    = 'modal-alert success';
      msg.style.display = 'block';
      form.reset();
      const preview = document.getElementById('chartPreview');
      if (preview) preview.style.display = 'none';
      setTimeout(() => { msg.style.display = 'none'; }, 3000);
      loadJournalEntries();   // refresh table
      loadTrackerData();      // refresh tracker (balance updated)
    } else {
      msg.textContent  = data.message || 'Failed to log trade.';
      msg.className    = 'modal-alert error';
      msg.style.display = 'block';
    }
  } catch {
    msg.textContent  = 'Network error. Please try again.';
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
      wrap.innerHTML = '<p class="text-muted">Sign in to view your trades.</p>';
      return;
    }
    const trades = await res.json();

    if (!trades.length) {
      wrap.innerHTML = '<p class="text-muted" id="noEntries">No trades logged yet. Start journaling above.</p>';
      return;
    }

    let html = `
      <div class="trades-table-wrap">
        <table class="trades-table">
          <thead>
            <tr>
              <th>Pair</th><th>Dir</th><th>Entry</th><th>Exit</th>
              <th>Pips</th><th>Outcome</th><th>Date</th>
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
    wrap.innerHTML = '<p class="text-muted">Could not load trades.</p>';
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
    setText('t-balance-sub', 'Started at $' + data.account_size.toLocaleString('en-US', {minimumFractionDigits:2}));
    setBar ('t-profit-bar',  data.profit_percent);
    setText('t-profit-hint', `Profit Progress: ${data.profit_progress}% / ${data.target_profit}% target`);

    // Daily drawdown card
    const dailyColor = data.daily_used_percent >= 80 ? 'text-red' : 'text-yellow';
    setValueColor('t-daily', `${data.daily_loss_today}%`, dailyColor);
    setText('t-daily-sub',  `Limit: ${data.daily_drawdown_limit}%`);
    const dailyBar = document.getElementById('t-daily-bar');
    if (dailyBar) {
      dailyBar.style.width = Math.min(data.daily_used_percent, 100) + '%';
      dailyBar.className   = data.daily_used_percent >= 80
        ? 'tracker-progress-bar tracker-bar-danger'
        : 'tracker-progress-bar tracker-bar-yellow';
    }
    const safeLabel = data.drawdown_breached ? '🚨 LIMIT BREACHED' : data.daily_used_percent >= 80 ? '⚠️ Danger Zone' : '✅ Safe';
    setText('t-daily-hint', `${data.daily_used_percent}% of daily limit used — ${safeLabel}`);

    // Max drawdown card
    const maxColor = data.max_used_percent >= 80 ? 'text-red' : 'text-green';
    setValueColor('t-max', `${data.total_loss}%`, maxColor);
    setText('t-max-sub',  `Limit: ${data.max_loss_limit}%`);
    setBar ('t-max-bar',  data.max_used_percent);
    setText('t-max-hint', `${data.max_used_percent}% of max limit used`);

    // Profit target card
    setText('t-profit',     `${data.profit_progress}%`);
    setText('t-profit-sub', `Target: ${data.target_profit}%`);
    setBar ('t-target-bar', data.profit_percent);
    const progressLabel = data.profit_percent >= 100 ? '🎉 Target Reached!' : `${data.profit_percent}% of target reached — Keep going 💪`;
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
    msg.textContent  = '✅ Tracker account created!';
    msg.className    = 'modal-alert success';
    msg.style.display = 'block';
    setTimeout(() => loadTrackerData(), 800);
  } else {
    msg.textContent  = data.message || 'Setup failed.';
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
