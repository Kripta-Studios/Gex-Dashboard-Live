/**
 * Trade Annotator — Main Application
 *
 * Interactive chart with:
 *  - OHLC candlestick chart (TradingView Lightweight Charts)
 *  - Time-varying greek level lines (max/min gamma, vanna, dgex, etc.)
 *  - Static IB and Fibonacci horizontal lines
 *  - Trade markers with add/delete annotation
 */

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let chart = null;
let candleSeries = null;
let levelSeries = {};       // name -> LineSeries
let priceLinesIB = [];      // IB horizontal price lines
let priceLinesFib = [];     // Fibonacci horizontal price lines
let tradeMarkers = [];      // Trade markers on the candlestick series

let availableDates = [];
let currentDateIndex = -1;
let currentTicker = 'SPX';
let currentDayData = null;
let currentTrades = [];

// Annotation state
let annotationMode = false;
let annotationEntry = null;  // {time, price}
let annotationExit = null;
let pendingDirection = 1;    // 1=LONG, -1=SHORT

// Guard flag to prevent recursive date change events
let _settingDateProgrammatically = false;

// Level visibility
const levelVisibility = {
    ib: true, fib: true, gamma: true,
    vanna: false, dgex: false, zerogamma: false,
    vega: false, vomma: false,
};

// Level -> color mapping
const LEVEL_COLORS = {
    max_gamma_strike:  '#ef4444',
    min_gamma_strike:  '#f87171',
    max_vanna_strike:  '#8b5cf6',
    min_vanna_strike:  '#a78bfa',
    max_dgex_strike:   '#06b6d4',
    min_dgex_strike:   '#67e8f9',
    zero_gamma:        '#f97316',
    max_vega_strike:   '#ec4899',
    min_vega_strike:   '#f9a8d4',
    max_vomma_strike:  '#14b8a6',
    min_vomma_strike:  '#5eead4',
};

const LEVEL_GROUPS = {
    gamma:     ['max_gamma_strike', 'min_gamma_strike'],
    vanna:     ['max_vanna_strike', 'min_vanna_strike'],
    dgex:      ['max_dgex_strike', 'min_dgex_strike'],
    zerogamma: ['zero_gamma'],
    vega:      ['max_vega_strike', 'min_vega_strike'],
    vomma:     ['max_vomma_strike', 'min_vomma_strike'],
};

// ═══════════════════════════════════════════════════════════════
// TIME HELPERS
// ═══════════════════════════════════════════════════════════════

/**
 * Convert "HH:MM" time string to a Unix timestamp using a reference date.
 * Lightweight Charts needs Unix timestamps.
 */
function timeToUnix(timeStr, dateStr) {
    // dateStr = "YYYYMMDD", timeStr = "HH:MM"
    const y = parseInt(dateStr.slice(0, 4));
    const m = parseInt(dateStr.slice(4, 6)) - 1;
    const d = parseInt(dateStr.slice(6, 8));
    const [hh, mm] = timeStr.split(':').map(Number);
    return Math.floor(new Date(y, m, d, hh, mm, 0).getTime() / 1000);
}

function unixToTime(unix) {
    const dt = new Date(unix * 1000);
    return dt.toTimeString().slice(0, 5); // "HH:MM"
}

function dateStrToISO(dateStr) {
    // "YYYYMMDD" -> "YYYY-MM-DD"
    return `${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}`;
}

function isoToDateStr(iso) {
    // "YYYY-MM-DD" -> "YYYYMMDD"
    return iso.replace(/-/g, '');
}

/**
 * Set the date input value WITHOUT triggering the change listener.
 */
function setDateInputSilent(dateStr) {
    _settingDateProgrammatically = true;
    document.getElementById('dateInput').value = dateStrToISO(dateStr);
    _settingDateProgrammatically = false;
}

// ═══════════════════════════════════════════════════════════════
// CHART INITIALIZATION
// ═══════════════════════════════════════════════════════════════

function initChart() {
    const container = document.getElementById('chart');
    chart = LightweightCharts.createChart(container, {
        layout: {
            background: { type: 'solid', color: '#0a0e17' },
            textColor: '#94a3b8',
            fontFamily: 'Inter, sans-serif',
            fontSize: 12,
        },
        grid: {
            vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
            horzLines: { color: 'rgba(30, 41, 59, 0.5)' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: { color: 'rgba(59, 130, 246, 0.3)', width: 1, style: 2 },
            horzLine: { color: 'rgba(59, 130, 246, 0.3)', width: 1, style: 2 },
        },
        rightPriceScale: {
            borderColor: '#1e293b',
            scaleMargins: { top: 0.05, bottom: 0.05 },
        },
        timeScale: {
            borderColor: '#1e293b',
            timeVisible: true,
            secondsVisible: false,
            rightOffset: 5,
            barSpacing: 4,
        },
        handleScroll: true,
        handleScale: true,
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderUpColor: '#22c55e',
        borderDownColor: '#ef4444',
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
    });

    // Handle chart clicks for annotation
    chart.subscribeClick((param) => {
        if (!annotationMode) return;
        if (!param.time) return;

        const price = candleSeries.coordinateToPrice(param.point.y);
        const timeStr = unixToTime(param.time);

        if (!annotationEntry) {
            // Set entry
            annotationEntry = { time: param.time, timeStr, price: Math.round(price * 100) / 100 };
            document.getElementById('annotationStep').textContent = 'exit';
        } else {
            // Set exit
            annotationExit = { time: param.time, timeStr, price: Math.round(price * 100) / 100 };
            // Auto-detect direction
            pendingDirection = annotationExit.price > annotationEntry.price ? 1 : -1;
            showTradeModal();
        }
    });

    // Handle resize
    const ro = new ResizeObserver(() => {
        chart.applyOptions({
            width: container.clientWidth,
            height: container.clientHeight,
        });
    });
    ro.observe(container);
}

// ═══════════════════════════════════════════════════════════════
// DATA LOADING & RENDERING
// ═══════════════════════════════════════════════════════════════

async function loadDates() {
    try {
        const resp = await fetch(`/api/dates/${currentTicker}`);
        const data = await resp.json();
        availableDates = data.dates || [];
        setStatus(`${availableDates.length} trading days available for ${currentTicker}`);
    } catch (e) {
        showToast('Failed to load dates', 'error');
    }
}

async function loadDay(dateStr) {
    if (!dateStr) return;

    showLoading(true);
    setStatus(`Loading ${currentTicker} ${dateStr}...`);

    try {
        // Load day data and trades in parallel
        const [dayResp, tradesResp] = await Promise.all([
            fetch(`/api/day/${currentTicker}/${dateStr}`),
            fetch(`/api/trades/${currentTicker}/${dateStr}`),
        ]);

        if (!dayResp.ok) {
            const err = await dayResp.json();
            showToast(err.detail || 'Failed to load day data', 'error');
            showLoading(false);
            return;
        }

        currentDayData = await dayResp.json();
        const tradesData = await tradesResp.json();
        currentTrades = tradesData.trades || [];

        renderChart();
        renderTrades();

        // Update the date input to confirm the loaded date
        currentDateIndex = availableDates.indexOf(dateStr);
        setDateInputSilent(dateStr);
        setStatus(`${currentTicker} ${dateStr} — ${currentDayData.candles.length} candles, ${currentTrades.length} trades`);
        showLoading(false);

    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
        showLoading(false);
    }
}

function renderChart() {
    if (!currentDayData || !chart) return;

    const dateStr = currentDayData.date;

    // Clear existing overlays
    clearOverlays();

    // 1. Render candles
    const candleData = currentDayData.candles
        .filter(c => c.open > 0 && c.high > 0 && c.low > 0 && c.close > 0)
        .map(c => ({
            time: timeToUnix(c.time, dateStr),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }));

    candleSeries.setData(candleData);

    // 2. Render IB horizontal lines
    renderIBLines();

    // 3. Render Fibonacci lines
    renderFibLines();

    // 4. Render greek level lines
    renderGreekLevels();

    // 5. Render trade markers
    renderTradeMarkers();

    // Fit content
    chart.timeScale().fitContent();
}

function clearOverlays() {
    // Remove all line series
    for (const name in levelSeries) {
        try { chart.removeSeries(levelSeries[name]); } catch(e) {}
    }
    levelSeries = {};

    // Remove IB price lines
    priceLinesIB.forEach(pl => { try { candleSeries.removePriceLine(pl); } catch(e) {} });
    priceLinesIB = [];

    // Remove Fib price lines
    priceLinesFib.forEach(pl => { try { candleSeries.removePriceLine(pl); } catch(e) {} });
    priceLinesFib = [];
}

function renderIBLines() {
    if (!levelVisibility.ib || !currentDayData) return;

    const ibHigh = currentDayData.ib_high;
    const ibLow = currentDayData.ib_low;

    if (ibHigh > 0) {
        const pl = candleSeries.createPriceLine({
            price: ibHigh,
            color: '#3b82f6',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            axisLabelVisible: true,
            title: 'IB High',
        });
        priceLinesIB.push(pl);
    }

    if (ibLow > 0) {
        const pl = candleSeries.createPriceLine({
            price: ibLow,
            color: '#3b82f6',
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            axisLabelVisible: true,
            title: 'IB Low',
        });
        priceLinesIB.push(pl);
    }
}

function renderFibLines() {
    if (!levelVisibility.fib || !currentDayData || !currentDayData.fibonacci) return;

    const fib = currentDayData.fibonacci;
    const fibColors = {
        fib_127_up: '#f59e0b', fib_161_up: '#f59e0b', fib_200_up: '#f59e0b',
        fib_127_dn: '#f59e0b', fib_161_dn: '#f59e0b', fib_200_dn: '#f59e0b',
    };
    const fibLabels = {
        fib_127_up: '127.2% ↑', fib_161_up: '161.8% ↑', fib_200_up: '200% ↑',
        fib_127_dn: '127.2% ↓', fib_161_dn: '161.8% ↓', fib_200_dn: '200% ↓',
    };

    for (const [key, price] of Object.entries(fib)) {
        if (price <= 0) continue;
        const pl = candleSeries.createPriceLine({
            price: price,
            color: fibColors[key] || '#f59e0b',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: false,
            title: fibLabels[key] || key,
        });
        priceLinesFib.push(pl);
    }
}

function renderGreekLevels() {
    if (!currentDayData || !currentDayData.levels) return;

    const dateStr = currentDayData.date;
    const levels = currentDayData.levels;

    for (const [name, points] of Object.entries(levels)) {
        // Check visibility
        const group = Object.entries(LEVEL_GROUPS).find(([g, names]) => names.includes(name));
        if (group && !levelVisibility[group[0]]) continue;
        if (!points || points.length === 0) continue;

        const color = LEVEL_COLORS[name] || '#6b7280';
        const isMax = name.startsWith('max_') || name === 'zero_gamma';

        // IMPORTANT: priceScaleId='right' attaches the series to the
        // SAME price axis as the candlestick series so the strike
        // price lines overlay at the correct Y-position on the chart.
        const series = chart.addLineSeries({
            color: color,
            lineWidth: 1,
            lineStyle: isMax ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dotted,
            crosshairMarkerVisible: false,
            lastValueVisible: false,
            priceLineVisible: false,
            priceScaleId: 'right',
            title: name.replace(/_/g, ' ').replace('strike', '').trim(),
        });

        const data = points.map(p => ({
            time: timeToUnix(p.time, dateStr),
            value: p.value,
        }));

        series.setData(data);
        levelSeries[name] = series;
    }
}

function renderTradeMarkers() {
    if (!currentDayData) return;

    const dateStr = currentDayData.date;
    const markers = [];

    for (const trade of currentTrades) {
        const timeStr = trade.time || trade.entry_time;
        if (!timeStr) continue;

        const unix = timeToUnix(timeStr, dateStr);
        const isLong = trade.target === 1 || trade.direction === 'LONG';
        const isManual = trade.source === 'manual';

        markers.push({
            time: unix,
            position: isLong ? 'belowBar' : 'aboveBar',
            color: isLong ? '#22c55e' : '#ef4444',
            shape: isLong ? 'arrowUp' : 'arrowDown',
            text: `${isLong ? 'L' : 'S'}${isManual ? '*' : ''} ${trade.spot_price || ''}`,
        });

        // If manual trade has exit, show that too
        if (isManual && trade.exit_time) {
            const exitUnix = timeToUnix(trade.exit_time, dateStr);
            markers.push({
                time: exitUnix,
                position: 'inBar',
                color: '#94a3b8',
                shape: 'circle',
                text: `Exit`,
            });
        }
    }

    // Sort markers by time (required by Lightweight Charts)
    markers.sort((a, b) => a.time - b.time);
    candleSeries.setMarkers(markers);
}

// ═══════════════════════════════════════════════════════════════
// TRADES PANEL
// ═══════════════════════════════════════════════════════════════

function renderTrades() {
    const panel = document.getElementById('tradesPanel');
    const countEl = document.getElementById('tradeCount');

    countEl.textContent = currentTrades.length;

    if (currentTrades.length === 0) {
        panel.innerHTML = '<div class="no-trades">No trades for this day</div>';
        return;
    }

    let html = '';
    for (const trade of currentTrades) {
        const isLong = trade.target === 1 || trade.direction === 'LONG';
        const dir = isLong ? 'long' : 'short';
        const dirLabel = isLong ? 'LONG' : 'SHORT';
        const timeStr = trade.time || trade.entry_time || '—';
        const price = trade.spot_price || trade.entry_price || 0;
        const isManual = trade.source === 'manual';

        html += `
        <div class="trade-item" data-trade-id="${trade.id}">
            <span class="trade-badge ${dir}">${dirLabel}</span>
            ${isManual ? '<span class="trade-badge manual">Manual</span>' : ''}
            <div class="trade-info">
                <div class="time">${timeStr}</div>
                <div class="price">$${price.toFixed(2)}${trade.time_to_target ? ` • ${trade.time_to_target}min to TP` : ''}</div>
            </div>
            <button class="trade-delete" onclick="deleteTrade('${trade.id}')" title="Delete">✕</button>
        </div>`;
    }
    panel.innerHTML = html;
}

async function deleteTrade(tradeId) {
    try {
        const resp = await fetch(`/api/trades/${tradeId}`, { method: 'DELETE' });
        if (resp.ok) {
            showToast('Trade deleted', 'success');
            // Reload trades
            const dateStr = currentDayData?.date;
            if (dateStr) {
                const tradesResp = await fetch(`/api/trades/${currentTicker}/${dateStr}`);
                const data = await tradesResp.json();
                currentTrades = data.trades || [];
                renderTrades();
                renderTradeMarkers();
            }
        } else {
            showToast('Failed to delete trade', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// ANNOTATION MODE
// ═══════════════════════════════════════════════════════════════

function toggleAnnotation() {
    annotationMode = !annotationMode;
    annotationEntry = null;
    annotationExit = null;

    const btn = document.getElementById('annotateBtn');
    const banner = document.getElementById('annotationBanner');

    if (annotationMode) {
        btn.classList.add('active');
        banner.classList.add('active');
        document.getElementById('annotationStep').textContent = 'entry';
    } else {
        btn.classList.remove('active');
        banner.classList.remove('active');
    }
}

function showTradeModal() {
    const modal = document.getElementById('tradeModal');
    modal.classList.add('active');

    document.getElementById('modalEntry').textContent =
        `${annotationEntry.timeStr} @ $${annotationEntry.price.toFixed(2)}`;
    document.getElementById('modalExit').textContent =
        `${annotationExit.timeStr} @ $${annotationExit.price.toFixed(2)}`;

    // Auto-select direction
    selectDirection(pendingDirection);
}

function selectDirection(dir) {
    pendingDirection = dir;
    document.getElementById('dirLong').classList.toggle('selected', dir === 1);
    document.getElementById('dirShort').classList.toggle('selected', dir === -1);
}

function cancelAnnotation() {
    document.getElementById('tradeModal').classList.remove('active');
    annotationEntry = null;
    annotationExit = null;
    document.getElementById('annotationStep').textContent = 'entry';
}

async function confirmAnnotation() {
    if (!annotationEntry || !annotationExit || !currentDayData) return;

    const trade = {
        ticker: currentTicker,
        date: currentDayData.date,
        entry_time: annotationEntry.timeStr,
        exit_time: annotationExit.timeStr,
        entry_price: annotationEntry.price,
        exit_price: annotationExit.price,
        target: pendingDirection,
        direction: pendingDirection === 1 ? 'LONG' : 'SHORT',
        time_to_target: Math.abs(annotationExit.time - annotationEntry.time) / 60,
        time_to_stop: 0,
        max_move: Math.abs(annotationExit.price - annotationEntry.price) / annotationEntry.price,
    };

    try {
        const resp = await fetch('/api/trades', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(trade),
        });

        if (resp.ok) {
            showToast(`Trade added: ${trade.direction} @ ${trade.entry_time}`, 'success');
            // Reload
            const tradesResp = await fetch(`/api/trades/${currentTicker}/${currentDayData.date}`);
            const data = await tradesResp.json();
            currentTrades = data.trades || [];
            renderTrades();
            renderTradeMarkers();
        } else {
            showToast('Failed to add trade', 'error');
        }
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }

    document.getElementById('tradeModal').classList.remove('active');
    annotationEntry = null;
    annotationExit = null;
    document.getElementById('annotationStep').textContent = 'entry';
}

// ═══════════════════════════════════════════════════════════════
// LEVEL TOGGLES
// ═══════════════════════════════════════════════════════════════

function setupLevelToggles() {
    const checkboxes = document.querySelectorAll('.level-toggle input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.addEventListener('change', () => {
            const lvl = cb.dataset.level;
            levelVisibility[lvl] = cb.checked;
            // Re-render overlays
            if (currentDayData) {
                clearOverlays();
                renderIBLines();
                renderFibLines();
                renderGreekLevels();
                renderTradeMarkers();
            }
        });
    });
}

// ═══════════════════════════════════════════════════════════════
// SAVE
// ═══════════════════════════════════════════════════════════════

async function saveData() {
    try {
        const resp = await fetch('/api/save', { method: 'POST' });
        const data = await resp.json();
        showToast(data.message || 'Saved', 'success');
        loadSummary();
    } catch (e) {
        showToast(`Save failed: ${e.message}`, 'error');
    }
}

async function loadSummary() {
    try {
        const resp = await fetch('/api/summary');
        const data = await resp.json();
        const info = document.getElementById('summaryInfo');
        info.innerHTML = `<strong>${data.total || 0}</strong> samples | <strong>${data.dates || 0}</strong> days | ${data.manual || 0} manual | ${data.deleted || 0} deleted`;
    } catch(e) {}
}

// ═══════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════

function navigateDay(offset) {
    if (availableDates.length === 0) return;
    let newIdx = currentDateIndex + offset;
    if (newIdx < 0) newIdx = 0;
    if (newIdx >= availableDates.length) newIdx = availableDates.length - 1;
    if (newIdx === currentDateIndex) return;

    currentDateIndex = newIdx;
    const dateStr = availableDates[currentDateIndex];
    // loadDay will set the input via setDateInputSilent
    loadDay(dateStr);
}

// ═══════════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════════

function showLoading(show) {
    document.getElementById('chartLoading').style.display = show ? 'flex' : 'none';
}

function setStatus(text) {
    document.getElementById('statusText').textContent = text;
}

function showToast(msg, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

// ═══════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    initChart();
    setupLevelToggles();

    // Events
    document.getElementById('tickerSelect').addEventListener('change', async (e) => {
        currentTicker = e.target.value;
        await loadDates();
        // Try to load current date for new ticker
        const dateInput = document.getElementById('dateInput').value;
        if (dateInput) {
            const dateStr = isoToDateStr(dateInput);
            if (availableDates.includes(dateStr)) {
                loadDay(dateStr);
            }
        }
    });

    document.getElementById('dateInput').addEventListener('change', (e) => {
        // Guard: skip if this was set programmatically
        if (_settingDateProgrammatically) return;

        const dateStr = isoToDateStr(e.target.value);
        if (!dateStr || dateStr.length !== 8) return;

        if (availableDates.includes(dateStr)) {
            loadDay(dateStr);
        } else {
            showToast(`No data available for ${dateStr} in the dataset.`, 'error');
            // Revert visually to the currently loaded date's value without reloading
            if (currentDayData && currentDayData.date) {
                setDateInputSilent(currentDayData.date);
            }
        }
    });

    document.getElementById('prevDay').addEventListener('click', () => navigateDay(-1));
    document.getElementById('nextDay').addEventListener('click', () => navigateDay(1));
    document.getElementById('annotateBtn').addEventListener('click', toggleAnnotation);
    document.getElementById('saveBtn').addEventListener('click', saveData);

    // ESC to cancel annotation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (annotationMode) toggleAnnotation();
            document.getElementById('tradeModal').classList.remove('active');
        }
    });

    // Arrow key navigation
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
        if (e.key === 'ArrowLeft') navigateDay(-1);
        if (e.key === 'ArrowRight') navigateDay(1);
    });

    // Load initial data
    await loadDates();
    await loadSummary();

    // Default to most recent date
    if (availableDates.length > 0) {
        const lastDate = availableDates[availableDates.length - 1];
        loadDay(lastDate);
    }
});
