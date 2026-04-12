/* ═══════════════════════════════════════════════════════════════
   Teyka Admin — Research Panel Logic
   Uses globem_users from gem_data.json (daily IS aggregates)
   ═══════════════════════════════════════════════════════════════ */

let DATA = null;
let charts = {};

// ─── Chart.js Defaults ──────────────────────────────────────
Chart.defaults.color = '#8b8d99';
Chart.defaults.borderColor = 'rgba(255,255,255,0.04)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 8;

// ─── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('gem_data.json');
        DATA = await res.json();
    } catch (e) {
        console.error('Failed to load gem_data.json:', e);
        document.querySelector('.main').innerHTML = '<p style="padding:40px;color:#ef4444;">Error: gem_data.json not found</p>';
        return;
    }

    document.getElementById('sidebar-date').textContent = new Date().toLocaleDateString('es-ES');
    const engine = DATA.engine || 'Legacy';
    document.getElementById('sidebar-version').textContent = engine;
    initNav();
    initExport();
    renderOverview();
});

// ─── Navigation ─────────────────────────────────────────────
function initNav() {
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('nav-active'));
            btn.classList.add('nav-active');
            document.querySelectorAll('.view').forEach(v => v.classList.remove('view-active'));
            document.getElementById(`view-${view}`).classList.add('view-active');
            document.getElementById('topbar-title').textContent = btn.textContent.trim();

            // Lazy render
            if (view === 'users') renderUsers();
            if (view === 'correlations') renderCorrelations();
            if (view === 'logs') renderLogs();
            if (view === 'sandbox') renderSandbox();
        });
    });
}

// ─── Helpers ────────────────────────────────────────────────
function isBadge(val) {
    if (val >= 70) return `<span class="is-badge is-critical">${val.toFixed(1)}%</span>`;
    if (val >= 50) return `<span class="is-badge is-alert">${val.toFixed(1)}%</span>`;
    if (val >= 25) return `<span class="is-badge is-attention">${val.toFixed(1)}%</span>`;
    return `<span class="is-badge is-optimal">${val.toFixed(1)}%</span>`;
}

function levelBadge(val) {
    if (val >= 70) return '<span class="level-badge is-critical">CRITICO</span>';
    if (val >= 50) return '<span class="level-badge is-alert">ALERTA</span>';
    if (val >= 25) return '<span class="level-badge is-attention">ATENCION</span>';
    return '<span class="level-badge is-optimal">OPTIMO</span>';
}

function isColor(val) {
    if (val >= 70) return '#E53935';
    if (val >= 50) return '#EF5350';
    if (val >= 25) return '#EAB308';
    return '#22C55E';
}

function allDays() {
    const days = [];
    DATA.globem_users.forEach(u => {
        u.daily.forEach(d => { days.push({ ...d, pid: u.pid }); });
    });
    return days;
}

// ═══════════════════════════════════════════════════════════════
// OVERVIEW
// ═══════════════════════════════════════════════════════════════
function renderOverview() {
    const users = DATA.globem_users;
    const days = allDays();
    const totalDays = days.length;
    const avgIS = days.reduce((s, d) => s + d.IS, 0) / totalDays;
    const criticalDays = days.filter(d => d.IS >= 70).length;
    const avgScreen = days.reduce((s, d) => s + (d.screen_min_allday || 0), 0) / totalDays;
    const avgSteps = days.reduce((s, d) => s + (d.steps_allday || 0), 0) / totalDays;

    document.getElementById('kpi-users').textContent = users.length;
    document.getElementById('kpi-avg-is').textContent = avgIS.toFixed(1) + '%';
    document.getElementById('kpi-critical').textContent = criticalDays;
    document.getElementById('kpi-days').textContent = totalDays;
    document.getElementById('kpi-screen').textContent = Math.round(avgScreen) + ' min';
    document.getElementById('kpi-steps').textContent = Math.round(avgSteps).toLocaleString('es-ES');

    document.getElementById('topbar-users').textContent = `${users.length} usuarios`;
    document.getElementById('topbar-days').textContent = `${totalDays} días`;
    document.getElementById('topbar-alerts').textContent = `${criticalDays} críticos`;

    // IS Distribution Histogram
    const bins = Array(20).fill(0);
    days.forEach(d => { const b = Math.min(Math.floor(d.IS / 5), 19); bins[b]++; });
    const binLabels = bins.map((_, i) => `${i * 5}-${i * 5 + 5}`);
    const binColors = bins.map((_, i) => {
        const mid = i * 5 + 2.5;
        if (mid >= 70) return '#E53935';
        if (mid >= 50) return '#EF5350';
        if (mid >= 25) return '#EAB308';
        return '#22C55E';
    });

    destroyChart('chart-dist');
    charts['chart-dist'] = new Chart(document.getElementById('chart-dist'), {
        type: 'bar',
        data: {
            labels: binLabels,
            datasets: [{
                data: bins,
                backgroundColor: binColors.map(c => c + '80'),
                borderColor: binColors,
                borderWidth: 1,
                borderRadius: 3,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: 'rgba(255,255,255,0.03)' } }
            }
        }
    });

    // User comparison bars
    const uLabels = users.map(u => u.pid.replace('INS-W_', 'U'));
    const uValues = users.map(u => u.avg_IS);
    const uColors = uValues.map(v => isColor(v) + '90');

    destroyChart('chart-user-compare');
    charts['chart-user-compare'] = new Chart(document.getElementById('chart-user-compare'), {
        type: 'bar',
        data: {
            labels: uLabels,
            datasets: [{
                label: 'IS Medio',
                data: uValues,
                backgroundColor: uColors,
                borderColor: uValues.map(v => isColor(v)),
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: {
                x: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.03)' } },
                y: { grid: { display: false } }
            }
        }
    });

    // Segments: entertainment vs productive donut
    let totalEnt = 0, totalProd = 0, totalNone = 0;
    days.forEach(d => {
        if (d.session_class) {
            Object.values(d.session_class).forEach(v => {
                if (v === 'entertainment') totalEnt++;
                else if (v === 'productive') totalProd++;
                else totalNone++;
            });
        }
    });

    destroyChart('chart-segments');
    charts['chart-segments'] = new Chart(document.getElementById('chart-segments'), {
        type: 'doughnut',
        data: {
            labels: ['Entretenimiento', 'Productivo', 'Sin datos'],
            datasets: [{
                data: [totalEnt, totalProd, totalNone],
                backgroundColor: ['#E5393580', '#22C55E80', '#53555f40'],
                borderColor: ['#E53935', '#22C55E', '#53555f'],
                borderWidth: 1,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: { position: 'bottom', labels: { padding: 12 } }
            }
        }
    });

    // RMSSD by user
    const rmssdLabels = users.map(u => u.pid.replace('INS-W_', 'U'));
    const rmssdBaseline = users.map(u => u.baseline_rmssd);
    const rmssdAvg = users.map(u => {
        const vals = u.daily.map(d => d.daily_rmssd).filter(v => v != null);
        return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
    });

    destroyChart('chart-rmssd');
    charts['chart-rmssd'] = new Chart(document.getElementById('chart-rmssd'), {
        type: 'bar',
        data: {
            labels: rmssdLabels,
            datasets: [
                { label: 'Baseline', data: rmssdBaseline, backgroundColor: '#3B82F640', borderColor: '#3B82F6', borderWidth: 1, borderRadius: 3 },
                { label: 'Media diaria', data: rmssdAvg, backgroundColor: '#EF535040', borderColor: '#EF5350', borderWidth: 1, borderRadius: 3 },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: 'rgba(255,255,255,0.03)' }, title: { display: true, text: 'ms' } }
            }
        }
    });

    // Fitbit bar
    const fitbitUsers = DATA.fitbit_users || [];
    destroyChart('chart-fitbit');
    charts['chart-fitbit'] = new Chart(document.getElementById('chart-fitbit'), {
        type: 'bar',
        data: {
            labels: fitbitUsers.map((_, i) => `F${i + 1}`),
            datasets: [{
                label: 'RMSSD (ms)',
                data: fitbitUsers.map(u => u.rmssd),
                backgroundColor: fitbitUsers.map(u => {
                    if (u.risk === 'Alto') return '#E5393560';
                    if (u.risk === 'Medio') return '#EAB30860';
                    return '#22C55E60';
                }),
                borderColor: fitbitUsers.map(u => {
                    if (u.risk === 'Alto') return '#E53935';
                    if (u.risk === 'Medio') return '#EAB308';
                    return '#22C55E';
                }),
                borderWidth: 1,
                borderRadius: 3,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { grid: { color: 'rgba(255,255,255,0.03)' }, title: { display: true, text: 'ms' } }
            }
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// USERS VIEW
// ═══════════════════════════════════════════════════════════════
function renderUsers() {
    const users = DATA.globem_users;
    const tbody = document.getElementById('user-tbody');
    const sort = document.getElementById('user-sort').value;
    const search = document.getElementById('user-search').value.toLowerCase();

    let sorted = [...users];
    if (sort === 'is-desc') sorted.sort((a, b) => b.avg_IS - a.avg_IS);
    else if (sort === 'is-asc') sorted.sort((a, b) => a.avg_IS - b.avg_IS);
    else if (sort === 'screen-desc') sorted.sort((a, b) => b.avg_screen - a.avg_screen);
    else if (sort === 'steps-desc') sorted.sort((a, b) => b.avg_steps - a.avg_steps);
    else if (sort === 'sed-desc') sorted.sort((a, b) => b.avg_sedentary - a.avg_sedentary);

    if (search) sorted = sorted.filter(u => u.pid.toLowerCase().includes(search));

    tbody.innerHTML = '';
    sorted.forEach(u => {
        const critical = u.daily.filter(d => d.IS >= 70).length;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-weight:600;color:var(--text)">${u.pid}</td>
            <td>${isBadge(u.avg_IS)}</td>
            <td>${Math.round(u.avg_screen)}</td>
            <td>${u.avg_steps.toLocaleString('es-ES')}</td>
            <td>${Math.round(u.avg_sedentary)}</td>
            <td>${u.baseline_rmssd.toFixed(1)}</td>
            <td style="color:${critical > 0 ? '#E53935' : '#22C55E'}">${critical}/${u.days}</td>
            <td>${u.days}</td>
        `;
        tr.addEventListener('click', () => showUserDetail(u));
        tbody.appendChild(tr);
    });

    // Event listeners for sort/search
    document.getElementById('user-sort').onchange = renderUsers;
    document.getElementById('user-search').oninput = renderUsers;
}

function showUserDetail(user) {
    const panel = document.getElementById('user-detail');
    panel.style.display = 'block';
    document.getElementById('detail-title').textContent = `${user.pid} — Detalle`;

    // KPIs
    const kpis = document.getElementById('detail-kpis');
    const critical = user.daily.filter(d => d.IS >= 70).length;
    const entSegments = user.daily.reduce((s, d) =>
        s + (d.session_class ? Object.values(d.session_class).filter(v => v === 'entertainment').length : 0), 0);
    
    kpis.innerHTML = `
        <div class="dk-item"><div class="dk-label">IS Medio</div><div class="dk-value" style="color:${isColor(user.avg_IS)}">${user.avg_IS}%</div></div>
        <div class="dk-item"><div class="dk-label">Pantalla</div><div class="dk-value">${Math.round(user.avg_screen)}m</div></div>
        <div class="dk-item"><div class="dk-label">Pasos</div><div class="dk-value">${user.avg_steps.toLocaleString('es-ES')}</div></div>
        <div class="dk-item"><div class="dk-label">Sedentario</div><div class="dk-value">${Math.round(user.avg_sedentary)}m</div></div>
        <div class="dk-item"><div class="dk-label">Días Críticos</div><div class="dk-value" style="color:#E53935">${critical}</div></div>
    `;

    // IS daily chart
    const dailyLabels = user.daily.map(d => d.date.slice(5));
    const dailyIS = user.daily.map(d => d.IS);

    destroyChart('chart-detail-daily');
    const ctx1 = document.getElementById('chart-detail-daily').getContext('2d');
    const grad = ctx1.createLinearGradient(0, 0, 0, 260);
    grad.addColorStop(0, 'rgba(229,57,53,0.15)');
    grad.addColorStop(1, 'rgba(229,57,53,0)');

    charts['chart-detail-daily'] = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: dailyLabels,
            datasets: [{
                label: 'IS %',
                data: dailyIS,
                borderColor: '#EF5350',
                borderWidth: 2,
                backgroundColor: grad,
                fill: true,
                tension: 0.3,
                pointRadius: 2,
                pointBackgroundColor: dailyIS.map(v => isColor(v)),
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
                y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.03)' } }
            }
        }
    });

    // Stress vs Behavior lines
    destroyChart('chart-detail-decomp');
    charts['chart-detail-decomp'] = new Chart(document.getElementById('chart-detail-decomp'), {
        type: 'line',
        data: {
            labels: dailyLabels,
            datasets: [
                { label: 'StressScore', data: user.daily.map(d => d.stress_score), borderColor: '#E53935', borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
                { label: 'BehaviorScore', data: user.daily.map(d => d.behavior_score), borderColor: '#EAB308', borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
                y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.03)' } }
            }
        }
    });

    // Segments timeline (stacked)
    const segData = { morning: [], afternoon: [], evening: [], night: [] };
    user.daily.forEach(d => {
        ['morning', 'afternoon', 'evening', 'night'].forEach(seg => {
            const cls = d.session_class?.[seg] || 'none';
            segData[seg].push(cls === 'entertainment' ? 1 : cls === 'productive' ? 0 : 0.5);
        });
    });

    destroyChart('chart-detail-segments');
    charts['chart-detail-segments'] = new Chart(document.getElementById('chart-detail-segments'), {
        type: 'bar',
        data: {
            labels: dailyLabels,
            datasets: [
                { label: 'Morning', data: segData.morning.map(v => v === 1 ? 1 : 0), backgroundColor: '#E5393560', stack: 's' },
                { label: 'Afternoon', data: segData.afternoon.map(v => v === 1 ? 1 : 0), backgroundColor: '#EF535060', stack: 's' },
                { label: 'Evening', data: segData.evening.map(v => v === 1 ? 1 : 0), backgroundColor: '#C6282860', stack: 's' },
                { label: 'Night', data: segData.night.map(v => v === 1 ? 1 : 0), backgroundColor: '#88000060', stack: 's' },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { grid: { display: false }, ticks: { maxTicksLimit: 15 }, stacked: true },
                y: { stacked: true, max: 4, grid: { color: 'rgba(255,255,255,0.03)' }, title: { display: true, text: 'Ent. segments' } }
            }
        }
    });

    // Close button
    document.getElementById('detail-close').onclick = () => panel.style.display = 'none';

    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ═══════════════════════════════════════════════════════════════
// CORRELATIONS
// ═══════════════════════════════════════════════════════════════
function renderCorrelations() {
    const days = allDays();
    const colors = DATA.globem_users.map(u => isColor(u.avg_IS));
    const userColorMap = {};
    DATA.globem_users.forEach((u, i) => { userColorMap[u.pid] = colors[i]; });

    function makeScatter(canvasId, xKey, yKey, xLabel, yLabel) {
        const pts = days.filter(d => d[xKey] != null && d[yKey] != null).map(d => ({
            x: d[xKey], y: d[yKey], pid: d.pid
        }));

        destroyChart(canvasId);
        charts[canvasId] = new Chart(document.getElementById(canvasId), {
            type: 'scatter',
            data: {
                datasets: [{
                    data: pts,
                    backgroundColor: pts.map(p => (userColorMap[p.pid] || '#8b8d99') + '60'),
                    borderWidth: 0,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.raw.pid}: (${ctx.raw.x.toFixed(0)}, ${ctx.raw.y.toFixed(1)})`
                        }
                    }
                },
                scales: {
                    x: { title: { display: true, text: xLabel }, grid: { color: 'rgba(255,255,255,0.03)' } },
                    y: { title: { display: true, text: yLabel }, grid: { color: 'rgba(255,255,255,0.03)' } }
                }
            }
        });
    }

    makeScatter('scatter-screen-is', 'screen_min_allday', 'IS', 'Pantalla (min)', 'IS (%)');
    makeScatter('scatter-steps-stress', 'steps_allday', 'stress_score', 'Pasos', 'StressScore');
    makeScatter('scatter-rmssd-is', 'daily_rmssd', 'IS', 'RMSSD (ms)', 'IS (%)');
    makeScatter('scatter-sed-behavior', 'real_sedentary', 'behavior_score', 'Sedentarismo (min)', 'BehaviorScore');

    // Correlation matrix
    const fields = ['screen_min_allday', 'steps_allday', 'real_sedentary', 'stress_score', 'behavior_score'];
    const names = ['Pantalla', 'Pasos', 'Sedent.', 'Stress', 'Behavior'];
    const grid = document.getElementById('corr-grid');
    grid.innerHTML = '';

    for (let i = 0; i < fields.length; i++) {
        for (let j = 0; j < fields.length; j++) {
            const cell = document.createElement('div');
            cell.className = 'corr-cell';

            const xs = days.map(d => d[fields[i]]).filter(v => v != null);
            const ys = days.map(d => d[fields[j]]).filter(v => v != null);
            const n = Math.min(xs.length, ys.length);
            let corr = 0;
            if (n > 5 && i !== j) {
                const mx = xs.reduce((a, b) => a + b, 0) / n;
                const my = ys.reduce((a, b) => a + b, 0) / n;
                let num = 0, dx = 0, dy = 0;
                for (let k = 0; k < n; k++) {
                    num += (xs[k] - mx) * (ys[k] - my);
                    dx += (xs[k] - mx) ** 2;
                    dy += (ys[k] - my) ** 2;
                }
                corr = dx && dy ? num / Math.sqrt(dx * dy) : 0;
            } else if (i === j) {
                corr = 1;
            }

            const abs = Math.abs(corr);
            let bg;
            if (corr > 0) bg = `rgba(229,57,53,${abs * 0.6})`;
            else bg = `rgba(59,130,246,${abs * 0.6})`;
            if (i === j) bg = 'rgba(255,255,255,0.05)';

            cell.style.background = bg;
            cell.innerHTML = `<div class="corr-label">${names[i]} × ${names[j]}</div>${corr.toFixed(2)}`;
            grid.appendChild(cell);
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// LOGS
// ═══════════════════════════════════════════════════════════════
function renderLogs() {
    const filter = document.getElementById('log-filter').value;
    const days = allDays();
    let filtered = days;
    if (filter === 'critical') filtered = days.filter(d => d.IS >= 70);
    else if (filter === 'alert') filtered = days.filter(d => d.IS >= 50);

    filtered.sort((a, b) => b.IS - a.IS);

    const tbody = document.getElementById('logs-tbody');
    tbody.innerHTML = '';

    filtered.forEach(d => {
        const entCount = d.session_class
            ? Object.values(d.session_class).filter(v => v === 'entertainment').length
            : 0;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${d.date}</td>
            <td style="font-weight:600">${d.pid}</td>
            <td>${isBadge(d.IS)}</td>
            <td>${d.stress_score?.toFixed(1) || '—'}</td>
            <td>${d.behavior_score?.toFixed(1) || '—'}</td>
            <td>${Math.round(d.screen_min_allday || 0)}</td>
            <td>${Math.round(d.steps_allday || 0).toLocaleString('es-ES')}</td>
            <td>${Math.round(d.real_sedentary || 0)}</td>
            <td>${entCount}/4</td>
            <td>${levelBadge(d.IS)}</td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('log-count').textContent = `${filtered.length} registros`;
    document.getElementById('log-filter').onchange = renderLogs;
}

// ═══════════════════════════════════════════════════════════════
// SANDBOX
// ═══════════════════════════════════════════════════════════════
function renderSandbox() {
    const wStress = document.getElementById('w-stress');
    const wBehavior = document.getElementById('w-behavior');
    const wThreshold = document.getElementById('w-threshold');

    function update() {
        const w1 = parseInt(wStress.value) / 100;
        const w2 = 1 - w1;
        const threshold = parseInt(wThreshold.value);

        wBehavior.value = Math.round(w2 * 100);
        document.getElementById('w-stress-val').textContent = w1.toFixed(2);
        document.getElementById('w-behavior-val').textContent = w2.toFixed(2);
        document.getElementById('w-threshold-val').textContent = threshold;

        const days = allDays();
        const simValues = days.map(d => {
            let sim = w1 * (d.stress_score || 0) + w2 * (d.behavior_score || 0);
            // Apply consistency guarantees
            const entCount = d.session_class
                ? Object.values(d.session_class).filter(v => v === 'entertainment').length
                : 0;
            if (entCount >= 2) sim = Math.max(sim, 50);
            if (entCount >= 3) sim = Math.max(sim, 65);
            if (entCount >= 4) sim = Math.max(sim, 78);
            return Math.min(sim, 100);
        });

        const origValues = days.map(d => d.IS);
        const simAvg = simValues.reduce((a, b) => a + b, 0) / simValues.length;
        const origAvg = origValues.reduce((a, b) => a + b, 0) / origValues.length;
        const simCritical = simValues.filter(v => v >= threshold).length;
        const simMin = Math.min(...simValues);
        const simMax = Math.max(...simValues);
        const delta = simAvg - origAvg;

        document.getElementById('sr-avg').textContent = simAvg.toFixed(1) + '%';
        document.getElementById('sr-critical').textContent = simCritical;
        document.getElementById('sr-min').textContent = simMin.toFixed(1) + '%';
        document.getElementById('sr-max').textContent = simMax.toFixed(1) + '%';
        document.getElementById('sr-delta').textContent = `Δ vs original: ${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`;
        document.getElementById('sr-delta').style.color = Math.abs(delta) < 1 ? '#8b8d99' : delta > 0 ? '#E53935' : '#22C55E';

        // Chart: histogram comparison
        const origBins = Array(20).fill(0);
        const simBins = Array(20).fill(0);
        origValues.forEach(v => { origBins[Math.min(Math.floor(v / 5), 19)]++; });
        simValues.forEach(v => { simBins[Math.min(Math.floor(v / 5), 19)]++; });
        const binLabels = origBins.map((_, i) => `${i * 5}`);

        destroyChart('chart-sandbox');
        charts['chart-sandbox'] = new Chart(document.getElementById('chart-sandbox'), {
            type: 'bar',
            data: {
                labels: binLabels,
                datasets: [
                    { label: 'Original', data: origBins, backgroundColor: '#3B82F640', borderColor: '#3B82F6', borderWidth: 1, borderRadius: 2 },
                    { label: 'Simulado', data: simBins, backgroundColor: '#E5393540', borderColor: '#E53935', borderWidth: 1, borderRadius: 2 },
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'top' } },
                scales: {
                    x: { grid: { display: false }, title: { display: true, text: 'IS %' } },
                    y: { grid: { color: 'rgba(255,255,255,0.03)' }, title: { display: true, text: 'Días' } }
                }
            }
        });
    }

    wStress.oninput = update;
    wThreshold.oninput = update;
    update();
}

// ─── Export ─────────────────────────────────────────────────
function initExport() {
    document.getElementById('export-json').addEventListener('click', () => {
        const blob = new Blob([JSON.stringify(DATA, null, 2)], { type: 'application/json' });
        downloadBlob(blob, 'gem_data_export.json');
    });

    document.getElementById('export-csv').addEventListener('click', () => {
        const days = allDays();
        const headers = ['pid', 'date', 'IS', 'stress_score', 'behavior_score', 'daily_rmssd',
            'screen_min_allday', 'steps_allday', 'real_sedentary', 'active_min_allday'];
        const rows = days.map(d =>
            headers.map(h => d[h] != null ? d[h] : '').join(',')
        );
        const csv = [headers.join(','), ...rows].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        downloadBlob(blob, 'gem_data_export.csv');
    });
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

function destroyChart(id) {
    if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}
