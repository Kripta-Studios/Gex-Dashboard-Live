/* ═══════════════════════════════════════════════════════════════
   Proyecto Teyka — app.js
   IS Engine: IS = 0.60 × StressScore + 0.40 × BehaviorScore
   Session classification: Productive (green) vs Entertainment (red)
   Alert system: Trigger when IS > 70% and user is in Entertainment state
   ═══════════════════════════════════════════════════════════════ */

// ─── Chart defaults ─────────────────────────────────────────────
Chart.defaults.color = '#8b8d99';
Chart.defaults.borderColor = 'rgba(255,255,255,0.04)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;

// ─── State ──────────────────────────────────────────────────────
let DATA = null;
let state = { userIdx: 0, dayIdx: 0, playing: false, interval: null, speed: 7000 };
let charts = {};

// ─── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    initCounters();
    try {
        const res = await fetch('gem_data.json');
        DATA = await res.json();
    } catch (e) {
        console.error('Failed to load gem_data.json:', e);
        return;
    }
    initUserSelector();
    initCharts();
    selectUser(0);
    initTimeline();
    initNudge();
    initPipeline();
    initNav();
});

// ─── Counter Animation ──────────────────────────────────────────
function initCounters() {
    const obs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                e.target.querySelectorAll('[data-target]').forEach(el => {
                    const target = parseFloat(el.dataset.target);
                    const dur = 2000, start = performance.now();
                    (function tick(now) {
                        const p = Math.min((now - start) / dur, 1);
                        const v = target * (1 - Math.pow(1 - p, 4));
                        el.textContent = target > 100 ? Math.round(v).toLocaleString('es-ES') : v.toFixed(0);
                        if (p < 1) requestAnimationFrame(tick);
                    })(performance.now());
                });
                obs.unobserve(e.target);
            }
        });
    }, { threshold: 0.3 });
    document.querySelectorAll('#hero').forEach(s => obs.observe(s));
}

// ═══════════════════════════════════════════════════════════════
// ─── USER SELECTOR ─────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════

function initUserSelector() {
    const c = document.getElementById('user-selector');
    c.innerHTML = DATA.globem_users.map((u, i) => {
        const isColor = u.avg_IS >= 75 ? '#ef4444' : u.avg_IS >= 50 ? '#eab308' : u.avg_IS >= 25 ? '#3b82f6' : '#22c55e';
        return `<div class="user-card${i === 0 ? ' active' : ''}" data-idx="${i}">
            <div class="uc-pid">Usuario ${i + 1}</div>
            <div class="uc-is" style="color:${isColor}">IS ${Math.round(u.avg_IS)}%</div>
            <div class="uc-stats">📱 ${Math.round(u.avg_screen)} min/día<br>🚶 ${u.avg_steps.toLocaleString()} pasos<br>💓 ${u.baseline_rmssd} ms base</div>
        </div>`;
    }).join('');

    c.querySelectorAll('.user-card').forEach(card => {
        card.addEventListener('click', () => {
            c.querySelectorAll('.user-card').forEach(x => x.classList.remove('active'));
            card.classList.add('active');
            selectUser(parseInt(card.dataset.idx));
        });
    });
}

function selectUser(idx) {
    if (state.playing) togglePlay();
    state.userIdx = idx;
    state.dayIdx = 0;
    const u = DATA.globem_users[idx];
    const slider = document.getElementById('timeline-slider');
    slider.max = u.daily.length - 1;
    slider.value = 0;
    updateDay(0);
    updateDualTimeline();
}

// ═══════════════════════════════════════════════════════════════
// ─── UPDATE DAY ────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════

function updateDay(dayIdx) {
    const u = DATA.globem_users[state.userIdx];
    if (dayIdx >= u.daily.length) { if (state.playing) togglePlay(); return; }
    state.dayIdx = dayIdx;
    const d = u.daily[dayIdx];

    document.getElementById('timeline-slider').value = dayIdx;
    document.getElementById('timeline-date').textContent = d.date;

    // ─── IS Gauge ────────────────────────────────────────
    const is = d.IS || 0;
    const stress = d.stress_score || 0;
    const behavior = d.behavior_score || 0;
    const rmssd = d.daily_rmssd || 0;

    const circumference = 490;
    const offset = circumference - (is / 100) * circumference;
    const arc = document.getElementById('is-arc');
    const color = is >= 75 ? '#ef4444' : is >= 50 ? '#eab308' : is >= 25 ? '#3b82f6' : '#22c55e';
    arc.style.strokeDashoffset = offset;
    arc.style.stroke = color;

    const valEl = document.getElementById('is-value');
    valEl.textContent = `${Math.round(is)}%`;
    valEl.style.color = color;

    // Stress
    animVal('stress-val', stress, 0);
    document.getElementById('stress-fill').style.width = `${stress}%`;
    document.getElementById('stress-fill').style.background = stress > 60 ? '#ef4444' : stress > 30 ? '#f59e0b' : '#22c55e';
    document.getElementById('stress-detail').textContent = `RMSSD: ${rmssd.toFixed(1)} ms (base: ${u.baseline_rmssd})`;

    // Behavior
    const screen = d.screen_min_allday || 0;
    const steps = d.steps_allday || 0;
    const inertia = screen / Math.max(screen + steps / 100, 1) * 100;
    animVal('behavior-val', behavior, 0);
    document.getElementById('behavior-fill').style.width = `${behavior}%`;
    document.getElementById('behavior-fill').style.background = behavior > 60 ? '#ef4444' : behavior > 30 ? '#eab308' : '#3b82f6';
    document.getElementById('behavior-detail').textContent = `Inercia: ${Math.round(inertia)}% | Pantalla/Pasos`;

    // Formula
    document.getElementById('f-stress').textContent = Math.round(stress);
    document.getElementById('f-behavior').textContent = Math.round(behavior);
    document.getElementById('f-total').textContent = Math.round(is);

    // ─── Session Classification ──────────────────────────
    const cls = d.session_class || {};
    let prodCount = 0, entCount = 0;
    ['morning', 'afternoon', 'evening', 'night'].forEach(seg => {
        const badge = document.getElementById(`class-${seg}`);
        const c = cls[seg] || 'none';
        badge.textContent = c === 'productive' ? '🟢 Productivo' : c === 'entertainment' ? '🔴 Entretenim.' : '—';
        badge.className = `seg-badge ${c}`;
        if (c === 'productive') prodCount++;
        if (c === 'entertainment') entCount++;
    });
    const total = Math.max(prodCount + entCount, 1);
    const prodPct = Math.round(prodCount / total * 100);
    const entPct = Math.round(entCount / total * 100);
    document.getElementById('prod-fill').style.width = `${prodPct}%`;
    document.getElementById('prod-pct').textContent = `${prodPct}%`;
    document.getElementById('ent-fill').style.width = `${entPct}%`;
    document.getElementById('ent-pct').textContent = `${entPct}%`;

    // ─── Alert ───────────────────────────────────────────
    const alert = document.getElementById('is-alert');
    const SUGGESTIONS = ['💧 Bebe agua y estira', '🚶 Pasea 15 min', '🎸 Toca la guitarra', '📖 Lee un capítulo',
        '🧘 Medita 5 min', '🎨 Dibuja algo', '🏃 Sal a correr', '☕ Prepárate un té'];
    if (is >= 70 && entCount > 0) {
        alert.classList.remove('hidden');
        document.getElementById('is-alert-action').textContent = SUGGESTIONS[dayIdx % SUGGESTIONS.length];
    } else {
        alert.classList.add('hidden');
    }

    // ─── KPIs ────────────────────────────────────────────
    const sed = d.real_sedentary || 0; // Corrected: 960 - active_min (waking hrs only)
    animVal('k-screen', screen, 0);
    animVal('k-steps', steps, 0);
    animVal('k-sed', sed, 0);
    animVal('k-rmssd', rmssd, 1);

    setBar('kf-screen', screen / 600, screen > 400 ? '#ef4444' : screen > 200 ? '#eab308' : '#22c55e');
    setBar('kf-steps', steps / 15000, steps > 8000 ? '#22c55e' : steps > 4000 ? '#eab308' : '#ef4444');
    setBar('kf-sed', sed / 900, sed > 800 ? '#ef4444' : sed > 600 ? '#eab308' : '#22c55e');
    setBar('kf-rmssd', rmssd / 35, rmssd > 25 ? '#22c55e' : rmssd > 15 ? '#eab308' : '#ef4444');

    // Update intraday charts
    updateIntradayCharts(d);
    updateTimelineHighlight(dayIdx);
}

// ─── Helpers ────────────────────────────────────────────────────
function animVal(id, target, dec) {
    const el = document.getElementById(id);
    if (!el) return;
    const cur = parseFloat(el.textContent.replace(/[^\d.-]/g, '')) || 0;
    const dur = 400, s = performance.now();
    (function tick(now) {
        const p = Math.min((now - s) / dur, 1);
        const v = cur + (target - cur) * (1 - Math.pow(1 - p, 3));
        el.textContent = dec > 0 ? v.toFixed(dec) : Math.round(v).toLocaleString('es-ES');
        if (p < 1) requestAnimationFrame(tick);
    })(performance.now());
}

function setBar(id, pct, color) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.width = `${Math.min(Math.max(pct, 0), 1) * 100}%`;
    el.style.background = color;
}

// ═══════════════════════════════════════════════════════════════
// ─── CHARTS ────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════

function initCharts() {
    // Dual timeline: RMSSD (left) vs Screen (right)
    charts.dual = new Chart(document.getElementById('chart-dual-timeline').getContext('2d'), {
        type: 'line',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                title: { display: true, text: 'IS · RMSSD · Pantalla — Serie Temporal', font: { size: 14 } },
                tooltip: { backgroundColor: 'rgba(10,10,15,0.95)', cornerRadius: 12 }
            },
            scales: {
                y: { title: { display: true, text: 'IS (%) / RMSSD (ms)', color: '#3b82f6' }, ticks: { color: '#3b82f6' }, grid: { color: 'rgba(59,130,246,0.05)' } },
                y1: { title: { display: true, text: 'Pantalla (min) / Pasos', color: '#22c55e' }, ticks: { color: '#22c55e' }, position: 'right', grid: { drawOnChartArea: false } },
                x: { grid: { display: false } }
            }
        }
    });

    // Intraday screen bars
    charts.intradayScreen = new Chart(document.getElementById('chart-intraday-screen').getContext('2d'), {
        type: 'bar',
        data: { labels: ['🌅 Mañana', '☀️ Tarde', '🌆 Noche', '🌙 Madrug.'], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false, indexAxis: 'y',
            plugins: { title: { display: true, text: '📱 Pantalla por Segmento (min)', font: { size: 13 } }, legend: { display: false } },
            scales: { x: { grid: { color: 'rgba(255,255,255,0.03)' } }, y: { grid: { display: false } } }
        }
    });

    // IS per segment
    charts.intradayIS = new Chart(document.getElementById('chart-intraday-is').getContext('2d'), {
        type: 'bar',
        data: { labels: ['🌅 Mañana', '☀️ Tarde', '🌆 Noche', '🌙 Madrug.'], datasets: [] },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                title: { display: true, text: '🧠 Riesgo IS por Segmento', font: { size: 13 } },
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => `Score: ${ctx.raw.toFixed(1)}` } }
            },
            scales: { y: { grid: { color: 'rgba(255,255,255,0.03)' }, title: { display: true, text: 'Score' }, min: 0 }, x: { grid: { display: false } } }
        }
    });
}

function updateDualTimeline() {
    const u = DATA.globem_users[state.userIdx];
    const ch = charts.dual;
    const days = u.daily;
    ch.data.labels = days.map(d => d.date.slice(5));
    ch.data.datasets = [
        {
            label: 'IS (%)', data: days.map(d => d.IS || 0),
            borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.06)', fill: true,
            tension: 0.4, pointRadius: 5, pointHoverRadius: 8, yAxisID: 'y'
        },
        {
            label: 'RMSSD (ms)', data: days.map(d => d.daily_rmssd || 0),
            borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.04)',
            tension: 0.4, pointRadius: 3, borderDash: [5, 5], yAxisID: 'y'
        },
        {
            label: 'Pantalla (min)', data: days.map(d => d.screen_min_allday || 0),
            borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.04)', fill: true,
            tension: 0.4, pointRadius: 3, yAxisID: 'y1'
        },
        {
            label: 'Pasos', data: days.map(d => d.steps_allday || 0),
            borderColor: '#eab308', backgroundColor: 'rgba(234,179,8,0.03)',
            tension: 0.4, pointRadius: 2, borderDash: [3, 3], yAxisID: 'y1'
        }
    ];
    highlightDay(state.dayIdx);
    ch.update('none');
}

function updateTimelineHighlight(idx) {
    const ch = charts.dual;
    if (!ch.data.datasets[0]) return;
    const u = DATA.globem_users[state.userIdx];
    ch.data.datasets[0].pointBackgroundColor = u.daily.map((_, i) => i === idx ? '#fff' : '#3b82f6');
    ch.data.datasets[0].pointBorderColor = u.daily.map((_, i) => i === idx ? '#3b82f6' : 'transparent');
    ch.data.datasets[0].pointBorderWidth = u.daily.map((_, i) => i === idx ? 3 : 0);
    ch.data.datasets[0].pointRadius = u.daily.map((_, i) => i === idx ? 9 : 5);
    ch.update('none');
}

function highlightDay(idx) {
    const ch = charts.dual;
    const u = DATA.globem_users[state.userIdx];
    if (ch.data.datasets[0]) {
        ch.data.datasets[0].pointBackgroundColor = u.daily.map((_, i) => i === idx ? '#fff' : '#3b82f6');
        ch.data.datasets[0].pointBorderColor = u.daily.map((_, i) => i === idx ? '#3b82f6' : 'transparent');
        ch.data.datasets[0].pointBorderWidth = u.daily.map((_, i) => i === idx ? 3 : 0);
        ch.data.datasets[0].pointRadius = u.daily.map((_, i) => i === idx ? 9 : 5);
    }
}

function updateIntradayCharts(d) {
    const segs = ['morning', 'afternoon', 'evening', 'night'];

    // Screen bars with color coding (red = entertainment, green = productive)
    const scrData = segs.map(s => d[`screen_min_${s}`] || 0);
    const cls = d.session_class || {};
    const scrColors = segs.map(s => cls[s] === 'entertainment' ? 'rgba(239,68,68,0.7)' : cls[s] === 'productive' ? 'rgba(34,197,94,0.7)' : 'rgba(100,100,120,0.5)');
    charts.intradayScreen.data.datasets = [{
        data: scrData, backgroundColor: scrColors,
        borderColor: scrColors.map(c => c.replace('0.7', '1').replace('0.5', '0.7')),
        borderWidth: 1, borderRadius: 6
    }];
    charts.intradayScreen.update('none');

    // IS risk per segment
    const isScores = segs.map(seg => {
        const scr = d[`screen_min_${seg}`] || 0;
        const stp = d[`steps_${seg}`] || 1;
        const avg = d[`avg_session_${seg}`] || 0;
        const sed = d[`sedentary_min_${seg}`] || 0;
        let score = 0;
        score += (scr / Math.max(stp, 1) * 1000 > 100 ? 3 : scr / Math.max(stp, 1) * 1000 > 50 ? 1.5 : 0);
        score += (avg > 10 ? 2 : avg > 5 ? 1 : 0);
        score += (sed > 340 ? 2 : sed > 300 ? 1 : 0);
        if (seg === 'night' && scr > 60) score += 2;
        if (seg === 'evening' && scr > 120) score += 1;
        return Math.round(score * 10) / 10;
    });
    const isColors = isScores.map(s => s >= 6 ? 'rgba(239,68,68,0.8)' : s >= 3 ? 'rgba(245,158,11,0.8)' : 'rgba(34,197,94,0.8)');
    charts.intradayIS.data.datasets = [{
        data: isScores, backgroundColor: isColors,
        borderColor: isColors.map(c => c.replace('0.8', '1')),
        borderWidth: 2, borderRadius: 8
    }];
    charts.intradayIS.update('none');
}

// ═══════════════════════════════════════════════════════════════
// ─── TIMELINE CONTROLS ─────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════

function initTimeline() {
    document.getElementById('play-btn').addEventListener('click', togglePlay);
    document.getElementById('timeline-slider').addEventListener('input', e => updateDay(parseInt(e.target.value)));

    document.querySelectorAll('.speed-dot').forEach(dot => {
        dot.addEventListener('click', () => {
            document.querySelectorAll('.speed-dot').forEach(d => d.classList.remove('active'));
            dot.classList.add('active');
            state.speed = parseInt(dot.dataset.ms);
            if (state.playing) { clearInterval(state.interval); startInterval(); }
        });
    });
}

function togglePlay() {
    state.playing = !state.playing;
    const btn = document.getElementById('play-btn');
    if (state.playing) {
        btn.textContent = '⏸ Pausar';
        btn.classList.add('playing');
        startInterval();
    } else {
        btn.textContent = '▶ Reproducir';
        btn.classList.remove('playing');
        clearInterval(state.interval);
    }
}

function startInterval() {
    state.interval = setInterval(() => {
        const u = DATA.globem_users[state.userIdx];
        const next = state.dayIdx + 1;
        if (next >= u.daily.length) { togglePlay(); return; }
        updateDay(next);
    }, state.speed);
}

// ═══════════════════════════════════════════════════════════════
// ─── NUDGE SIMULATOR ───────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════

function initNudge() {
    const btn = document.getElementById('sim-nudge-btn');
    const idle = document.getElementById('w-idle');
    const notif = document.getElementById('w-notif');
    const ok = document.getElementById('w-ok');
    const feedback = document.getElementById('wn-feedback');
    const frame = document.querySelector('.watch-frame');
    let nudgeState = 'idle';

    const NUDGES = [
        { sug: 'Llevas <strong>5h 23min</strong> de pantalla. Sal a <strong>caminar 15 min</strong> — tu HRV mejorará un 20%.', s: '5h 23min', p: '2,200', h: '45%' },
        { sug: 'Tu sistema nervioso necesita un <strong>descanso</strong>. Prueba <strong>10 min de respiración</strong> guiada.', s: '6h 10min', p: '1,800', h: '52%' },
        { sug: 'Llevas <strong>4h 45min</strong> sedentario. Hidrátate y <strong>estira 5 minutos</strong>.', s: '4h 45min', p: '3,100', h: '38%' },
        { sug: 'Tu RMSSD ha caído un <strong>30%</strong>. Deja el móvil y <strong>sal a pasear</strong>.', s: '3h 50min', p: '2,500', h: '30%' },
        { sug: 'Uso de pantalla prolongado con <strong>0 pasos</strong>. Prepárate un <strong>té y dibuja algo</strong>.', s: '7h 15min', p: '900', h: '60%' },
    ];

    btn.addEventListener('click', () => {
        if (nudgeState !== 'idle') {
            idle.classList.remove('hidden'); notif.classList.add('hidden'); ok.classList.add('hidden'); feedback.classList.add('hidden');
            nudgeState = 'idle'; btn.textContent = 'Simular Alerta IS > 75%'; return;
        }
        const n = NUDGES[Math.floor(Math.random() * NUDGES.length)];
        document.getElementById('wn-body').innerHTML = `<p>💓 HRV <strong>${n.h} bajo</strong></p><p>📱 <strong>${n.s}</strong> pantalla · <strong>${n.p}</strong> pasos</p>`;
        document.getElementById('wn-suggestion').innerHTML = n.sug;

        idle.classList.add('hidden'); notif.classList.remove('hidden');
        notif.style.animation = 'none'; void notif.offsetHeight; notif.style.animation = 'slideUp 0.5s cubic-bezier(0.34,1.56,0.64,1)';
        frame.classList.add('watch-vibrate'); setTimeout(() => frame.classList.remove('watch-vibrate'), 1200);
        nudgeState = 'notif'; btn.textContent = '↺ Reiniciar';
    });

    document.getElementById('wn-accept').addEventListener('click', () => feedback.classList.remove('hidden'));
    document.getElementById('wn-later').addEventListener('click', () => { notif.classList.add('hidden'); idle.classList.remove('hidden'); nudgeState = 'idle'; btn.textContent = 'Simular Alerta IS > 70% (Ocio)'; });
    document.getElementById('fb-y').addEventListener('click', showOK);
    document.getElementById('fb-n').addEventListener('click', showOK);

    function showOK() {
        notif.classList.add('hidden'); ok.classList.remove('hidden');
        nudgeState = 'ok';
        setTimeout(() => { ok.classList.add('hidden'); idle.classList.remove('hidden'); nudgeState = 'idle'; btn.textContent = 'Simular Alerta IS > 70% (Ocio)'; }, 3000);
    }
}

// ─── Pipeline Animation ─────────────────────────────────────────
function initPipeline() {
    const stages = document.querySelectorAll('.pipe-stage');
    const obs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                stages.forEach((s, i) => setTimeout(() => s.classList.add('visible'), i * 200));
                obs.unobserve(e.target);
            }
        });
    }, { threshold: 0.2 });
    const pipe = document.getElementById('pipeline');
    if (pipe) obs.observe(pipe);
}

// ─── Nav Highlight ──────────────────────────────────────────────
function initNav() {
    const sections = document.querySelectorAll('section[id]');
    const links = document.querySelectorAll('.nav-link');
    const obs = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                links.forEach(l => { l.classList.remove('active'); if (l.getAttribute('href') === `#${e.target.id}`) l.classList.add('active'); });
            }
        });
    }, { rootMargin: '-40% 0px -60% 0px' });
    sections.forEach(s => obs.observe(s));
}
