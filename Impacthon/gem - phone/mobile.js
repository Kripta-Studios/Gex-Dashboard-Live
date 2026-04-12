/* ═══════════════════════════════════════════════════════════════
   Teyka Mobile — App Logic
   Trade Republic chart + Swipe + iOS Notifications
   Rest periods: vertical red bands instead of dots
   ═══════════════════════════════════════════════════════════════ */

// ─── Deterministic RNG para Demos ───────────────────────────────
// Sobrescribimos Math.random con una semilla fija para que al recargar (F5) los picos sean idénticos
let _seed = 1337;
Math.random = function() {
    var x = Math.sin(_seed++) * 10000;
    return x - Math.floor(x);
};

// ─── State ──────────────────────────────────────────────────
let DATA = null;
let state = { userIdx: 0, dayIdx: 0, screenIdx: 0, range: 'day', notifShown: false };
let mainChart = null, histChart = null;

// ─── IS Levels ──────────────────────────────────────────────
const LEVELS = [
    { max: 25, name: 'Estado óptimo', cls: 'level-optimal', color: '#C7C7CC' },
    { max: 50, name: 'Monitoreo activo', cls: 'level-attention', color: '#EF9A9A' },
    { max: 70, name: 'Considera un descanso', cls: 'level-alert', color: '#EF5350' },
    { max: 100, name: 'Necesitas desconectar', cls: 'level-critical', color: '#C62828' },
];

function getLevel(is) {
    return LEVELS.find(l => is <= l.max) || LEVELS[3];
}

function isColor(val) {
    if (val <= 25) return '#C7C7CC';
    if (val <= 50) return '#EF9A9A';
    if (val <= 70) return '#EF5350';
    return '#C62828';
}

// ─── SVG Icons ──────────────────────────────────────────────
const SVG = {
    alertCircle: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    checkCircle: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
    chart: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 4-6"/></svg>`,
    alertTriangle: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    bell: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
    calendar: `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
};

// ─── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    updateClock();
    setInterval(updateClock, 30000);

    try {
        const res = await fetch('gem_data.json');
        DATA = await res.json();
    } catch (e) {
        console.error('Failed to load data:', e);
        return;
    }

    initUserModal();
    initRangeSelector();
    initBottomNav();
    initNotification();
    initOnboarding();
    selectUser(0);
    showDailySummary();
});

function updateClock() {
    const now = new Date();
    const h = now.getHours().toString().padStart(2, '0');
    const m = now.getMinutes().toString().padStart(2, '0');
    document.getElementById('status-time').textContent = `${h}:${m}`;
}

function updateGreeting(userName) {
    const hour = new Date().getHours();
    let greeting;
    if (hour < 12) greeting = 'Buenos días';
    else if (hour < 20) greeting = 'Buenas tardes';
    else greeting = 'Buenas noches';

    // Extract a name: "Usuario 1" → "Álvaro" (use fixed name for demo)
    const names = ['Álvaro', 'María', 'Carlos', 'Lucía', 'Diego', 'Ana', 'Pablo', 'Sofía'];
    const idx = state.userIdx % names.length;
    const name = names[idx];
    
    document.getElementById('greeting-name').textContent = `Hola, ${name}`;
    document.getElementById('greeting-sub').textContent = `${greeting} · Tu resumen de hoy`;
}

// ─── User Selection ─────────────────────────────────────────
function initUserModal() {
    const trigger = document.getElementById('user-trigger');
    const modal = document.getElementById('user-modal');

    trigger.addEventListener('click', () => {
        buildUserList();
        modal.classList.add('modal-visible');
    });
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('modal-visible');
    });
}

function buildUserList() {
    const list = document.getElementById('user-list');
    list.innerHTML = '';
    DATA.users.forEach((u, i) => {
        const level = getLevel(u.summary.avg_is);
        const avatarColors = ['#E53935','#F4511E','#7B1FA2','#1976D2','#00897B','#43A047','#FF8F00','#5E35B1'];
        const names = ['Álvaro', 'María', 'Carlos', 'Lucía', 'Diego', 'Ana', 'Pablo', 'Sofía'];
        const item = document.createElement('div');
        item.className = `user-item ${i === state.userIdx ? 'user-selected' : ''}`;
        item.innerHTML = `
            <div class="user-avatar" style="background:${avatarColors[i % 8]}">${names[i][0]}</div>
            <div class="user-info">
                <div class="user-name">${names[i]}</div>
                <div class="user-detail">${u.summary.avg_screen}min pantalla · ${u.summary.avg_steps} pasos</div>
            </div>
            <div class="user-is" style="background:${level.color}20;color:${level.color}">${u.summary.avg_is}%</div>
        `;
        item.addEventListener('click', () => {
            selectUser(i);
            document.getElementById('user-modal').classList.remove('modal-visible');
        });
        list.appendChild(item);
    });
}

function selectUser(idx) {
    state.userIdx = idx;
    const user = DATA.users[idx];
    state.dayIdx = user.days.length - 1;
    state.notifShown = false;
    updateGreeting(user.id);
    renderDay();
    renderHistory();
    if (localStorage.getItem('gem_onboarded')) {
        showDailySummary();
    }
}

// ─── Render Day View ────────────────────────────────────────
function renderDay() {
    const user = DATA.users[state.userIdx];
    const day = user.days[state.dayIdx];

    // IS gauge
    const avgIS = day.daily_is;
    const level = getLevel(avgIS);
    document.getElementById('is-number').textContent = Math.round(avgIS);
    document.getElementById('is-level').textContent = level.name;

    // Animate SVG arc
    const arc = document.getElementById('is-arc');
    const circumference = 327;
    const offset = circumference - (circumference * Math.min(avgIS, 100) / 100);
    arc.style.strokeDashoffset = offset;
    arc.style.stroke = level.color;

    // Date display
    document.getElementById('is-date').textContent = day.date;

    const hero = document.querySelector('.is-hero');
    hero.className = 'is-hero ' + level.cls;

    // Health cards
    setText('h-rmssd', Math.round(day.rmssd_avg));
    setText('h-steps', day.steps_total.toLocaleString('es-ES'));
    setText('h-screen', Math.round(day.screen_total));
    setText('h-active', Math.round(day.active_min));

    setBar('hf-rmssd', day.rmssd_avg / 35, day.rmssd_avg > 25 ? '#34C759' : day.rmssd_avg > 15 ? '#FF9F0A' : '#E53935');
    setBar('hf-steps', Math.min(day.steps_total / 12000, 1), day.steps_total > 8000 ? '#34C759' : day.steps_total > 4000 ? '#FF9F0A' : '#E53935');
    setBar('hf-screen', Math.min(day.screen_total / 600, 1), day.screen_total > 400 ? '#E53935' : day.screen_total > 200 ? '#FF9F0A' : '#34C759');
    setBar('hf-active', Math.min(day.active_min / 300, 1), day.active_min > 120 ? '#34C759' : day.active_min > 60 ? '#FF9F0A' : '#E53935');

    // Decomposition
    const hourNow = new Date().getHours();
    const hourData = day.hourly[Math.min(hourNow, 23)] || day.hourly[12];
    setText('d-stress', Math.round(hourData.stress));
    setText('d-behavior', Math.round(hourData.behavior));
    setBar('df-stress', hourData.stress / 100, '#E53935');
    setBar('df-behavior', hourData.behavior / 100, '#FF9F0A');

    // Inyectar contexto demo dinámico una sola vez por día
    if (!day._demoInjected) {
        day._demoInjected = true;
        
        // Generar un patrón estocástico pero coherente
        day.hourly.forEach((h) => {
            if (h.hour < 8) h.app_type = 'inactive';
            else if (h.hour < 14) h.app_type = Math.random() > 0.2 ? 'productive' : 'non-productive'; 
            else if (h.hour < 16) h.app_type = Math.random() > 0.4 ? 'non-productive' : 'productive'; 
            else if (h.hour < 20) h.app_type = Math.random() > 0.3 ? 'productive' : 'non-productive'; 
            else h.app_type = Math.random() > 0.6 ? 'productive' : 'non-productive'; 
            
            // Alterar algo de IS original (+/- 10%) para ruido natural
            h.is = Math.max(0, Math.min(100, (h.is || 0) + (Math.random() * 20 - 10)));
        });

        // Asegurar puntos clave variados
        if (day.hourly.length > 20) {
            // Pico productivo por estrés de trabajo válido
            const prodIdx = 9 + Math.floor(Math.random() * 4); // 9-12
            if (day.hourly[prodIdx]) {
                day.hourly[prodIdx].app_type = 'productive';
                day.hourly[prodIdx].is = 76 + Math.random() * 10;
            }

            // Ocio de mediodía (Riesgo frecuente de segunda banda roja)
            const chillIdx = 13 + Math.floor(Math.random() * 3); // 13-15
            if (day.hourly[chillIdx]) {
                day.hourly[chillIdx].app_type = 'non-productive';
                // 50% de probabilidad de que el descanso de mediodía cruce el umbral y genere otra alerta visual
                day.hourly[chillIdx].is = Math.random() > 0.5 ? (72 + Math.random() * 15) : (40 + Math.random() * 20);
            }

            // Ocio de media mañana (30% chance de banda roja extra por la mañana)
            const mornChill = 10 + Math.floor(Math.random() * 2); // 10-11
            if (Math.random() > 0.7 && day.hourly[mornChill]) {
                day.hourly[mornChill].app_type = 'non-productive';
                day.hourly[mornChill].is = 73 + Math.random() * 10;
            }

            // Pico de ocio desencadenante primario (Asegurado SIEMPRE en la demo principal, tarde/noche)
            const triggerIdx = 18 + Math.floor(Math.random() * 4); // 18-21
            if (day.hourly[triggerIdx]) {
                day.hourly[triggerIdx].app_type = 'non-productive';
                day.hourly[triggerIdx].is = 76 + Math.random() * 12;
            }
        }
    }

    day.rest_points = [];
    let maxContextIS = 0;
    day.hourly.forEach(h => {
        if (h.is > 70 && h.app_type === 'non-productive') {
            day.rest_points.push(h.hour);
            if (h.is > maxContextIS) maxContextIS = h.is;
        }
    });

    // Rest points
    renderRestPoints(day);

    // Chart
    if (state.range === 'day') {
        renderDayChart(day);
    } else if (state.range === 'week') {
        renderWeekChart(user);
    } else {
        renderMonthChart(user);
    }

    // Maybe trigger notification
    if (window.pendingNotifTimeout) clearTimeout(window.pendingNotifTimeout);
    if (maxContextIS > 70 && !state.notifShown) {
        window.pendingNotifTimeout = setTimeout(() => showNotification(day), 2500);
    }
}

function renderRestPoints(day) {
    const container = document.getElementById('rest-points');
    container.innerHTML = '';
    if (!day.rest_points || day.rest_points.length === 0) {
        container.innerHTML = `<div class="rest-point rest-low">${SVG.checkCircle} Sin alertas hoy</div>`;
        return;
    }
    day.rest_points.forEach(h => {
        const isVal = day.hourly[h]?.is || 0;
        const cls = isVal > 70 ? 'rest-high' : isVal > 50 ? 'rest-mid' : 'rest-low';
        const pip = document.createElement('div');
        pip.className = `rest-point ${cls}`;
        pip.innerHTML = `${SVG.alertCircle} ${h}:00`;
        container.appendChild(pip);
    });
}

// ─── Trade Republic Chart — RED BANDS for rest zones ────────
function renderDayChart(day) {
    const ctx = document.getElementById('main-chart').getContext('2d');
    if (mainChart) mainChart.destroy();

    const labels = day.hourly.map(h => `${h.hour}:00`);
    const values = day.hourly.map(h => h.is);
    const restSet = new Set(day.rest_points || []);

    const maxVal = Math.max(...values);
    
    const thresholdLinePlugin = {
        id: 'thresholdLine',
        beforeDraw(chart) {
            const { ctx, chartArea, scales: { y } } = chart;
            if (!chartArea || !y) return;
            const targetY = y.getPixelForValue(70);
            if (targetY >= chartArea.top && targetY <= chartArea.bottom) {
                ctx.save();
                ctx.beginPath();
                ctx.strokeStyle = 'rgba(239, 68, 68, 0.5)';
                ctx.lineWidth = 1;
                ctx.setLineDash([4, 4]);
                ctx.moveTo(chartArea.left, targetY);
                ctx.lineTo(chartArea.right, targetY);
                ctx.stroke();
                ctx.restore();
            }
        }
    };

    const gradient = ctx.createLinearGradient(0, 0, 0, 220);
    if (maxVal > 70) {
        gradient.addColorStop(0, 'rgba(79, 70, 229, 0.35)');
        gradient.addColorStop(0.5, 'rgba(79, 70, 229, 0.08)');
        gradient.addColorStop(1, 'rgba(79, 70, 229, 0)');
    } else {
        gradient.addColorStop(0, 'rgba(199, 199, 204, 0.15)');
        gradient.addColorStop(1, 'rgba(199, 199, 204, 0)');
    }

    const restBandsPlugin = {
        id: 'restBands',
        beforeDatasetsDraw(chart) {
            const { ctx, chartArea, scales: { x, y } } = chart;
            if (!chartArea || !x || !y) return;
            
            const meta = chart.getDatasetMeta(0);
            if (!meta || !meta.data || !meta.data.length || restSet.size === 0) return;
            
            ctx.save();
            const points = meta.data;

            const periods = [];
            const sorted = Array.from(restSet).sort((a,b)=>a-b);
            sorted.forEach(hour => {
                const i = day.hourly.findIndex(h => h.hour === hour);
                if (i === -1) return;
                periods.push({ start: Math.max(0, i - 1), end: Math.min(points.length - 1, i + 1) });
            });

            const merged = [];
            periods.forEach(p => {
                if (!merged.length) merged.push({...p});
                else {
                    const last = merged[merged.length - 1];
                    if (p.start <= last.end) last.end = Math.max(last.end, p.end);
                    else merged.push({...p});
                }
            });

            merged.forEach(p => {
                ctx.beginPath();
                ctx.moveTo(points[p.start].x, chartArea.bottom);
                ctx.lineTo(points[p.start].x, points[p.start].y);

                for (let i = p.start + 1; i <= p.end; i++) {
                    const pt = points[i];
                    if (pt && pt.cp1x !== undefined && pt.cp1y !== undefined && pt.cp2x !== undefined && pt.cp2y !== undefined) {
                        ctx.bezierCurveTo(pt.cp1x, pt.cp1y, pt.cp2x, pt.cp2y, pt.x, pt.y);
                    } else if (pt) {
                        ctx.lineTo(pt.x, pt.y);
                    }
                }
                
                ctx.lineTo(points[p.end].x, chartArea.bottom);
                ctx.closePath();

                ctx.fillStyle = 'rgba(229, 57, 53, 0.25)'; // Relleno semitransparente sin contorno perimetral
                ctx.fill();

                // Sello de colisión superior: Difumina el anti-aliasing contra la curva maestra 
                // para que abrace perfectamente la línea roja de Chart.js
                ctx.beginPath();
                ctx.moveTo(points[p.start].x, points[p.start].y);
                for (let i = p.start + 1; i <= p.end; i++) {
                    const pt = points[i];
                    if (pt && pt.cp1x !== undefined && pt.cp1y !== undefined) {
                        ctx.bezierCurveTo(pt.cp1x, pt.cp1y, pt.cp2x, pt.cp2y, pt.x, pt.y);
                    } else if (pt) {
                        ctx.lineTo(pt.x, pt.y);
                    }
                }
                ctx.strokeStyle = 'rgba(229, 57, 53, 0.25)'; // Mismo color rojo translúcido
                ctx.lineWidth = 2.5; // Grosor exacto de sellado
                ctx.lineJoin = 'round';
                ctx.stroke();
            });

            const yPos = y.getPixelForValue(70);
            if (yPos >= chartArea.top && yPos <= chartArea.bottom) {
                ctx.strokeStyle = 'rgba(229, 57, 53, 0.35)';
                ctx.setLineDash([5, 5]);
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(chartArea.left, yPos);
                ctx.lineTo(chartArea.right, yPos);
                ctx.stroke();
            }

            ctx.restore();
        }
    };

    mainChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                data: values,
                borderColor: isColor(maxVal),
                borderWidth: 2.5,
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHoverBackgroundColor: isColor(maxVal),
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        font: { size: 10, family: 'Inter' },
                        maxTicksLimit: 8,
                        callback: (v, i) => i % 3 === 0 ? labels[i] : '',
                        color: '#AEAEB2',
                    },
                    border: { display: false },
                },
                y: {
                    min: 0, max: 100,
                    grid: { color: 'rgba(0,0,0,0.04)', drawBorder: false },
                    ticks: { display: false },
                    border: { display: false },
                }
            },
            onHover: (e, elements) => {
                const tooltip = document.getElementById('chart-tooltip');
                if (elements.length) {
                    const idx = elements[0].index;
                    const h = day.hourly[idx];
                    tooltip.querySelector('#tooltip-hour').textContent = `${h.hour}:00`;
                    
                    const appLabel = h.app_type === 'productive' ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;color:#4F46E5"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path></svg>Productivo' :
                                     h.app_type === 'non-productive' ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;color:#EF4444"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect><line x1="12" y1="18" x2="12.01" y2="18"></line></svg>Ocio' : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;color:#AEAEB2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>Inactivo';
                    
                    tooltip.querySelector('#tooltip-is').innerHTML = `<span style="font-size:12px;color:#AEAEB2;font-weight:400">${appLabel}</span><br><strong style="font-size:16px">${Math.round(h.is)}% IS</strong>`;
                    tooltip.classList.add('visible');
                    const x = elements[0].element.x;
                    const y = elements[0].element.y;
                    tooltip.style.left = `${x - 40}px`;
                    tooltip.style.top = `${y - 65}px`;
                } else {
                    tooltip.classList.remove('visible');
                }
            }
        },
        plugins: [restBandsPlugin, thresholdLinePlugin]
    });
}

function renderWeekChart(user) {
    const ctx = document.getElementById('main-chart').getContext('2d');
    if (mainChart) mainChart.destroy();

    const startIdx = Math.max(0, state.dayIdx - 6);
    const weekDays = user.days.slice(startIdx, state.dayIdx + 1);
    const labels = weekDays.map(d => {
        const dt = new Date(d.date);
        return ['Dom','Lun','Mar','Mie','Jue','Vie','Sáb'][dt.getDay()];
    });
    const values = weekDays.map(d => d.daily_is);

    const gradient = ctx.createLinearGradient(0, 0, 0, 220);
    gradient.addColorStop(0, 'rgba(229, 57, 53, 0.20)');
    gradient.addColorStop(1, 'rgba(229, 57, 53, 0)');

    mainChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                data: values,
                borderColor: '#EF5350',
                borderWidth: 2.5,
                backgroundColor: gradient,
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: values.map(v => isColor(v)),
                pointBorderColor: '#FFF',
                pointBorderWidth: 2,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: true } },
            scales: {
                x: { grid: { display: false }, border: { display: false }, ticks: { font: { family: 'Inter' } } },
                y: { min: 0, max: 100, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { display: false }, border: { display: false } }
            }
        }
    });
}

function renderMonthChart(user) {
    const ctx = document.getElementById('main-chart').getContext('2d');
    if (mainChart) mainChart.destroy();

    const labels = user.days.map(d => {
        const dt = new Date(d.date);
        return `${dt.getDate()}/${dt.getMonth() + 1}`;
    });
    const values = user.days.map(d => d.daily_is);

    const gradient = ctx.createLinearGradient(0, 0, 0, 220);
    gradient.addColorStop(0, 'rgba(229, 57, 53, 0.15)');
    gradient.addColorStop(1, 'rgba(229, 57, 53, 0)');

    mainChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                data: values,
                borderColor: '#EF9A9A',
                borderWidth: 2,
                backgroundColor: gradient,
                fill: true,
                tension: 0.3,
                pointRadius: 0,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false }, ticks: { maxTicksLimit: 8, font: { size: 10, family: 'Inter' } }, border: { display: false } },
                y: { min: 0, max: 100, grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { display: false }, border: { display: false } }
            }
        }
    });
}

// ─── Range Selector ─────────────────────────────────────────
function initRangeSelector() {
    document.querySelectorAll('.range-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('range-active'));
            btn.classList.add('range-active');
            state.range = btn.dataset.range;
            renderDay();
        });
    });
}

// ─── Bottom Nav ─────────────────────────────────────────────
function initBottomNav() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const idx = parseInt(btn.dataset.screen);
            navigateToScreen(idx);
        });
    });

    document.querySelector('.chart-container').addEventListener('dblclick', () => {
        showDaySelector();
    });
}

function navigateToScreen(idx) {
    state.screenIdx = idx;
    document.getElementById('screens').style.transform = `translateX(-${idx * 100}%)`;
    document.querySelectorAll('.nav-btn').forEach((b, i) => {
        b.classList.toggle('nav-active', i === idx);
    });
}

function showDaySelector() {
    const modal = document.getElementById('day-modal');
    const slider = document.getElementById('day-slider');
    const label = document.getElementById('day-slider-label');
    const user = DATA.users[state.userIdx];

    slider.max = user.days.length - 1;
    slider.value = state.dayIdx;
    label.textContent = user.days[state.dayIdx].date;

    slider.oninput = () => {
        state.dayIdx = parseInt(slider.value);
        label.textContent = user.days[state.dayIdx].date;
    };

    document.getElementById('day-done').onclick = () => {
        modal.classList.remove('modal-visible');
        renderDay();
        renderHistory();
    };

    modal.classList.add('modal-visible');
    modal.addEventListener('click', (e) => {
        if (e.target === modal) { modal.classList.remove('modal-visible'); renderDay(); }
    });
}

// ─── History Calendar ───────────────────────────────────────
function renderHistory() {
    const user = DATA.users[state.userIdx];
    const grid = document.getElementById('calendar-grid');
    grid.innerHTML = '';

    ['L','M','X','J','V','S','D'].forEach(d => {
        const h = document.createElement('div');
        h.className = 'cal-header';
        h.textContent = d;
        grid.appendChild(h);
    });

    if (user.days.length > 0) {
        const dt = new Date(user.days[state.dayIdx].date);
        const months = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
        document.getElementById('history-month').textContent = `${months[dt.getMonth()]} ${dt.getFullYear()}`;
    }

    const firstDate = new Date(user.days[0].date);
    const startDow = (firstDate.getDay() + 6) % 7;

    for (let i = 0; i < startDow; i++) {
        const empty = document.createElement('div');
        empty.className = 'cal-day';
        grid.appendChild(empty);
    }

    user.days.forEach((day, i) => {
        const dt = new Date(day.date);
        const cell = document.createElement('div');
        cell.className = `cal-day ${i === state.dayIdx ? 'cal-selected' : ''}`;

        const is = day.daily_is;
        let bg;
        if (is <= 25) bg = '#F5F5F5';
        else if (is <= 40) bg = '#FFEBEE';
        else if (is <= 60) bg = '#FFCDD2';
        else bg = '#EF9A9A';
        cell.style.background = bg;
        cell.textContent = dt.getDate();

        cell.addEventListener('click', () => {
            state.dayIdx = i;
            renderDay();
            renderHistory();
        });

        grid.appendChild(cell);
    });

    renderHistoryChart(user);
    renderHistoryStats(user);
}

function renderHistoryChart(user) {
    const ctx = document.getElementById('history-chart');
    if (!ctx) return;
    if (histChart) histChart.destroy();

    const values = user.days.map(d => d.daily_is);
    const labels = user.days.map(d => {
        const dt = new Date(d.date);
        return `${dt.getDate()}/${dt.getMonth() + 1}`;
    });
    const pointColors = user.days.map((d, i) =>
        i === state.dayIdx ? '#E53935' : 'transparent'
    );

    const gradient = ctx.getContext('2d').createLinearGradient(0, 0, 0, 180);
    gradient.addColorStop(0, 'rgba(229,57,53,0.12)');
    gradient.addColorStop(1, 'rgba(229,57,53,0)');

    histChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                data: values,
                borderColor: '#EF9A9A',
                borderWidth: 1.5,
                backgroundColor: gradient,
                fill: true,
                tension: 0.3,
                pointRadius: user.days.map((_, i) => i === state.dayIdx ? 6 : 0),
                pointBackgroundColor: pointColors,
                pointBorderColor: '#FFF',
                pointBorderWidth: 2,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: { min: 0, max: 100, display: false }
            }
        }
    });
}

function renderHistoryStats(user) {
    const container = document.getElementById('history-stats');
    const values = user.days.map(d => d.daily_is);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const maxIS = Math.max(...values);
    const alerts = user.days.reduce((sum, d) => sum + d.alerts, 0);

    let trendCls = 'trend-stable', trendLabel = '→ Estable';
    if (values.length >= 14) {
        const first7 = values.slice(0, 7).reduce((a, b) => a + b, 0) / 7;
        const last7 = values.slice(-7).reduce((a, b) => a + b, 0) / 7;
        if (last7 > first7 + 3) { trendCls = 'trend-up'; trendLabel = '↑ Subiendo'; }
        else if (last7 < first7 - 3) { trendCls = 'trend-down'; trendLabel = '↓ Bajando'; }
    }

    container.innerHTML = `
        <div class="history-stat-card">
            <div class="hstat-icon">${SVG.chart}</div>
            <div><div class="hstat-label">IS Medio</div><div class="hstat-value">${avg.toFixed(1)}%</div></div>
            <div class="hstat-trend ${trendCls}">${trendLabel}</div>
        </div>
        <div class="history-stat-card">
            <div class="hstat-icon">${SVG.alertTriangle}</div>
            <div><div class="hstat-label">IS Máximo</div><div class="hstat-value">${maxIS.toFixed(1)}%</div></div>
        </div>
        <div class="history-stat-card">
            <div class="hstat-icon">${SVG.bell}</div>
            <div><div class="hstat-label">Alertas totales</div><div class="hstat-value">${alerts}</div></div>
        </div>
        <div class="history-stat-card">
            <div class="hstat-icon">${SVG.calendar}</div>
            <div><div class="hstat-label">Días registrados</div><div class="hstat-value">${user.days.length}</div></div>
        </div>
    `;
}

// ─── Navigation ──────────────────────────────────────────────
function initBottomNav() {
    const btns = document.querySelectorAll('.nav-btn');
    const container = document.querySelector('.screens-container');

    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('nav-active'));
            btn.classList.add('nav-active');

            const screen = parseInt(btn.dataset.screen);
            state.screenIdx = screen;
            container.style.transform = `translateX(-${screen * 100}%)`;

            if (screen === 1) renderHistory();
            else renderDay();
        });
    });
}

// ─── Notification ───────────────────────────────────────────
function initNotification() {
    document.getElementById('notif-now').addEventListener('click', dismissNotif);
    document.getElementById('notif-later').addEventListener('click', dismissNotif);
    document.getElementById('notif-overlay').addEventListener('click', (e) => {
        if (e.target.id === 'notif-overlay') dismissNotif();
    });
}

function showNotification(day) {
    if (state.notifShown) return;
    if (!localStorage.getItem('gem_onboarded')) return; // Block notifications from interrupting the onboarding tour
    state.notifShown = true;

    const notifPoint = day.hourly.filter(h => h.is > 70 && h.app_type === 'non-productive').reduce((a, b) => a.is > b.is ? a : b, {is: 0, hour: 0});
    if (!notifPoint.hour) return;

    const screenTotal = Math.round(day.screen_total);
    const titleEl = document.getElementById('notif-title');
    const bodyEl = document.getElementById('notif-body');
    const card = document.getElementById('notif-card');
    
    titleEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:6px;"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg>Gemini calculando nudge...';
    bodyEl.innerHTML = `<span style="opacity:0.7">Saturación crítica (IS ${Math.round(notifPoint.is)}%) detectada en zona horaria no productiva. Generando sugerencia contextual...</span>`;
    card.classList.add('notif-visible');
    document.getElementById('notif-overlay').classList.add('notif-visible');

    setTimeout(async () => {
        const suggestion = await getHobbySuggestion(state.userIdx === 0);
        titleEl.textContent = 'Tu mente necesita un descanso';
        bodyEl.innerHTML = `Llevas <strong>${screenTotal} min</strong> de pantalla hoy y alcanzaste un <strong>${Math.round(notifPoint.is)}% IS</strong> a las ${notifPoint.hour}:00 durante uso no productivo.<br><br>Teyka sugiere que podrías <strong>${suggestion}</strong> para reducir el estrés.`;
        if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
    }, 1500);
}

function dismissNotif() {
    document.getElementById('notif-card').classList.remove('notif-visible');
    document.getElementById('notif-overlay').classList.remove('notif-visible');
}

// ─── Helpers ────────────────────────────────────────────────
function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setBar(id, pct, color) {
    const el = document.getElementById(id);
    if (el) {
        el.style.width = `${Math.min(pct, 1) * 100}%`;
        el.style.background = color;
    }
}

// ═══════════════════════════════════════════════════════════════
// DAILY SUMMARY (Yesterday Recap)
// ═══════════════════════════════════════════════════════════════

function showDailySummary() {
    if (!localStorage.getItem('gem_onboarded')) return; // Block daily summary from covering up the UI during onboarding
    const card = document.getElementById('daily-summary');
    if (!card || !DATA) return;

    const user = DATA.users[state.userIdx];
    if (!user || user.days.length < 2) return;

    // "Yesterday" = day index 1 (day 0 is today)
    const yesterday = user.days[1];
    if (!yesterday || !yesterday.hourly) return;

    // Inject stochastic context to yesterday if not done
    if (!yesterday._demoInjected) {
        yesterday._demoInjected = true;
        let sum = 0;
        let alertCount = 0;
        yesterday.hourly.forEach(h => {
            if (h.hour < 8) h.app_type = 'inactive';
            else if (h.hour < 14) h.app_type = Math.random() > 0.25 ? 'productive' : 'non-productive';
            else if (h.hour < 16) h.app_type = Math.random() > 0.45 ? 'non-productive' : 'productive';
            else if (h.hour < 20) h.app_type = Math.random() > 0.35 ? 'productive' : 'non-productive';
            else h.app_type = Math.random() > 0.5 ? 'productive' : 'non-productive';
            h.is = Math.max(0, Math.min(100, (h.is || 0) + (Math.random() * 16 - 8)));
        });
        // Force a high ocio peak
        const peakH = 14 + Math.floor(Math.random() * 6);
        if (yesterday.hourly[peakH]) {
            yesterday.hourly[peakH].app_type = 'non-productive';
            yesterday.hourly[peakH].is = 75 + Math.random() * 15;
        }

        // Re-calculate daily_is and alerts for history synchronization
        yesterday.hourly.forEach(h => {
            sum += h.is;
            if (h.is >= 70 && h.app_type === 'non-productive') alertCount++;
        });
        yesterday.daily_is = sum / yesterday.hourly.length;
        yesterday.alerts = alertCount;
    }

    // Find peak IS hour
    let peakHour = yesterday.hourly[0];
    yesterday.hourly.forEach(h => { if (h.is > peakHour.is) peakHour = h; });

    const peakIS = Math.round(peakHour.is);
    if (peakIS < 40) return; // nothing interesting to report

    // Find recovery: lowest IS after the peak hour
    const afterPeak = yesterday.hourly.filter(h => h.hour > peakHour.hour);
    const recoveryHour = afterPeak.length
        ? afterPeak.reduce((a, b) => a.is < b.is ? a : b)
        : null;

    const drop = recoveryHour ? Math.round(peakHour.is - recoveryHour.is) : 0;
    const peakType = peakHour.app_type === 'non-productive' ? 'ocio' : peakHour.app_type === 'productive' ? 'trabajo' : 'inactividad';

    // Populate card
    document.getElementById('ds-peak-val').textContent = peakIS + '%';
    document.getElementById('ds-detail').innerHTML = 
        `Ayer a las <strong>${peakHour.hour}:00</strong> alcanzaste un pico de <strong>${peakIS}% IS</strong> durante un periodo de <strong>${peakType}</strong>. ` +
        `Llevabas <strong>${Math.round(yesterday.screen_total)} min</strong> de pantalla.`;

    const resultEl = document.getElementById('ds-result');
    if (drop >= 15) {
        resultEl.className = 'ds-result ds-result-good';
        resultEl.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34C759" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg><span>Tras la recomendación, tu IS bajó <strong>${drop} puntos porcentuales</strong> hasta las ${recoveryHour.hour}:00.</span>`;
    } else if (drop > 0) {
        resultEl.className = 'ds-result ds-result-neutral';
        resultEl.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" stroke-width="2" stroke-linecap="round"><path d="M5 12h14"/></svg><span>Tu IS se redujo ${drop} puntos porcentuales. Intenta desconectar más hoy.</span>`;
    } else {
        resultEl.className = 'ds-result ds-result-neutral';
        resultEl.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--red-400)" stroke-width="2" stroke-linecap="round"><path d="M12 5v14"/><path d="M19 12l-7 7-7-7"/></svg><span>Tu IS no bajó tras el pico. Intenta tomarte un descanso antes hoy.</span>`;
    }

    card.style.display = 'block';

    // Close button
    document.getElementById('ds-close').onclick = () => {
        card.style.display = 'none';
    };
}

// ═══════════════════════════════════════════════════════════════
// ONBOARDING FLOW
// ═══════════════════════════════════════════════════════════════

const OB_STEPS = ['ob-welcome', 'ob-gauge', 'ob-chart', 'ob-notif', 'ob-hobbies'];
let obStep = 0;
let userHobbies = [];

function initOnboarding() {
    const overlay = document.getElementById('onboarding-overlay');
    if (!overlay) return;

    // Already completed → skip
    if (localStorage.getItem('gem_onboarded')) {
        overlay.classList.add('ob-hidden');
        setTimeout(() => overlay.remove(), 600);
        return;
    }



    // Next button
    document.getElementById('ob-next-btn').addEventListener('click', advanceOnboarding);

    // Personalization buttons
    const btnYes = document.getElementById('ob-personalize-yes');
    if (btnYes) btnYes.addEventListener('click', advanceOnboarding);
    
    const btnNo = document.getElementById('ob-personalize-no');
    if (btnNo) btnNo.addEventListener('click', finishOnboarding);

    // Hobby tags toggle
    document.getElementById('ob-tags').addEventListener('click', (e) => {
        const tag = e.target.closest('.ob-tag');
        if (!tag) return;
        tag.classList.toggle('ob-tag-active');
        const hobby = tag.dataset.hobby;
        if (tag.classList.contains('ob-tag-active')) {
            if (!userHobbies.includes(hobby)) userHobbies.push(hobby);
        } else {
            userHobbies = userHobbies.filter(h => h !== hobby);
        }
    });

    // Custom hobby input
    const customInput = document.getElementById('ob-custom-input');
    const customAdd = document.getElementById('ob-custom-add');
    
    function addCustomHobby() {
        const val = customInput.value.trim();
        if (!val) return;
        
        // Create new tag
        const btn = document.createElement('button');
        btn.className = 'ob-tag ob-tag-active';
        btn.dataset.hobby = val.toLowerCase();
        btn.textContent = val;
        document.getElementById('ob-tags').appendChild(btn);
        userHobbies.push(val.toLowerCase());
        customInput.value = '';
    }
    
    customAdd.addEventListener('click', addCustomHobby);
    customInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); addCustomHobby(); }
    });

    // Done button (finish onboarding)
    document.getElementById('ob-done-btn').addEventListener('click', finishOnboarding);
}

function advanceOnboarding() {
    if (obStep >= OB_STEPS.length - 1) return;

    const current = document.getElementById(OB_STEPS[obStep]);
    current.classList.remove('ob-step-active');

    obStep++;
    const next = document.getElementById(OB_STEPS[obStep]);
    if (next) {
        next.classList.add('ob-step-active');
        
        const scrollContainer = document.querySelector('.screen-scroll');
        if (scrollContainer) {
            if (OB_STEPS[obStep] === 'ob-gauge' || Math.abs(obStep) === 1 || OB_STEPS[obStep] === 'ob-chart') {
                scrollContainer.scrollTo({top: 0, behavior: 'smooth'});
            }
        }
    }

    // Update dots
    document.querySelectorAll('.ob-dot').forEach((d, i) => {
        d.classList.toggle('ob-dot-active', i === obStep);
    });

    // Toggle overlay transparency for tour steps (1-3) so app is visible behind
    const overlay = document.getElementById('onboarding-overlay');
    if (obStep >= 1 && obStep <= 3) {
        overlay.classList.add('ob-tour-mode');
    } else {
        overlay.classList.remove('ob-tour-mode');
    }

    // Hide nav on specific custom steps
    const nav = document.getElementById('ob-nav');
    if (OB_STEPS[obStep] === 'ob-notif' || OB_STEPS[obStep] === 'ob-hobbies') {
        nav.classList.add('ob-nav-hidden');
    } else {
        nav.classList.remove('ob-nav-hidden');
    }
}

function finishOnboarding() {
    // Si el usuario escribió un hobby a mano y no le dio al símbolo '+' (entró directo a Empezar)
    const customInput = document.getElementById('ob-custom-input');
    if (customInput) {
        const val = customInput.value.trim();
        if (val && !userHobbies.includes(val)) {
            userHobbies.push(val);
        }
    }

    // Save hobbies and flag
    localStorage.setItem('gem_hobbies', JSON.stringify(userHobbies));
    localStorage.setItem('gem_onboarded', '1');

    const overlay = document.getElementById('onboarding-overlay');
    overlay.classList.add('ob-hidden');
    setTimeout(() => overlay.remove(), 600);

    // Volver al bloque principal al entrar a la app real
    const scrollContainer = document.querySelector('.screen-scroll');
    if (scrollContainer) {
        scrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// ─── Hobby-aware notification suggestions (Gemini AI + Fallback) ──
async function getHobbySuggestion(useGemini = true) {
    const stored = localStorage.getItem('gem_hobbies');
    const hobbies = stored ? JSON.parse(stored) : [];
    
    // Configuración API: Leemos dinámicamente el .env
    let API_KEY = "";
    try {
        const envRes = await fetch('../.env');
        if (!envRes.ok) throw new Error(`HTTP ${envRes.status}`);
        const envText = await envRes.text();
        const match = envText.match(/key=([^\r\n]+)/i);
        if (match) API_KEY = match[1].trim();
        console.log("✅ API KEY cargada desde ../.env");
    } catch (e) {
        console.warn("⚠️ Falló ../.env, intentando .env local. Error:", e.message);
        try {
            const envResChild = await fetch('.env');
            if (!envResChild.ok) throw new Error(`HTTP ${envResChild.status}`);
            const envTextChild = await envResChild.text();
            const matchChild = envTextChild.match(/key=([^\r\n]+)/i);
            if (matchChild) {
                API_KEY = matchChild[1].trim();
                console.log("✅ API KEY cargada desde .env local");
            } else {
                console.error("❌ Archivo .env descargado, pero no se encontró 'key=...'! Contenido:", envTextChild);
            }
        } catch (err) {
            console.error("❌ Fallo CRÍTICO leyendo el archivo .env vía Fetch. Mensaje HTTP:", err.message);
            console.warn("⚠️ Pasando a Offline Fallback por falta de .env. Verifica que el servidor de Python exponga el .env y no haya permisos de sistema bloqueándolo.");
        }
    }

    if (!API_KEY) {
        console.warn("API_KEY está completamente vacía, abortando petición a Gemini.");
        return getFallback();
    }

    const API_URL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${API_KEY}`;
    
    // Función de fallback genérica
    const getFallback = (forceDefault = false) => {
        if (forceDefault || !hobbies.length) {
            const defaults = [
                'salir a dar un paseo corto', 
                'hacer una serie de estiramientos', 
                'prepararte un té o café', 
                'respirar profundamente 5 minutos',
                'apagar la pantalla un instante',
                'tomar un vaso de agua fresca',
                'cerrar los ojos durante un par de minutos'
            ];
            return defaults[Math.floor(Math.random() * defaults.length)];
        }
        const templates = {
            'caminar': 'dar un paseo corto de 15 minutos',
            'correr': 'hacer una serie rápida de estiramientos o trote',
            'musica': 'poner tu playlist favorita y cerrar los ojos',
            'leer': 'desconectar leyendo unas páginas de tu libro',
            'meditar': 'meditar 10 min respirando profundo',
            'cocinar': 'prepararte algo rico o un snack saludable',
            'guitarra': 'tocar un rato para desconectar la mente',
            'dibujar': 'coger papel y dibujar libremente unos minutos',
            'yoga': 'hacer una pausa corta de yoga o mindfulness',
            'naturaleza': 'tomar aire fresco al lado de la ventana o calle',
            'amigos': 'mandar un audio o llamar a quien tú sabes',
            'gimnasio': 'levantarte y hacer movilidad articular',
        };
        const pick = hobbies[Math.floor(Math.random() * hobbies.length)];
        return templates[pick] || `dedicar un momento a la afición seleccionada (${pick})`;
    };

    if (!useGemini) return getFallback(true);
    if (!hobbies.length) return getFallback();

    try {
        const prompt = `El usuario tiene un alto nivel de estrés. Sus hobbies guardados son: ${hobbies.join(', ')}. Escribe una única frase corta (máximo 8 o 10 palabras), directa y amable, sugiriendo una actividad concreta y realista basada en estos hobbies para que se relaje ahora mismo. No des explicaciones ni uses comillas ni signos de puntuación finales, solo el predicado. Ejemplo: "escuchar un álbum completo de tu artista favorito" o "salir a andar por el parque".`;

        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`❌ HTTP Error ${response.status}: ${errorText}`);
            throw new Error(`API request failed with status ${response.status}`);
        }
        
        const data = await response.json();
        let aiText = data.candidates[0].content.parts[0].text.trim().toLowerCase();
        
        // Limpiamos formato si la IA añade punto o comillas por error
        aiText = aiText.replace(/^[.¡!¿?"']+|[.¡!¿?"']+$/g, '');
        return aiText;
        
    } catch (error) {
        console.warn("⚠️ Gemini API falló (posible límite de cuota o key agotada). Usando fallback offline:", error);
        return getFallback();
    }
}

// ─── Development & Demo Shortcuts ──────────────────────────
// Press Shift + O to reset onboarding and reload the app
document.addEventListener('keydown', (e) => {
    if (e.shiftKey && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        localStorage.removeItem('gem_onboarded');
        localStorage.removeItem('gem_hobbies');
        location.reload();
    }
});

