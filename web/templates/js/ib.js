/**
 * IB Panel Module
 * Creates Initial Balance chart panels using Chart.js
 */

/**
 * Create an IB (Initial Balance) panel
 * @param {Object} chartObj - Chart configuration object
 * @param {number} index - Chart index
 * @returns {HTMLElement} Panel element
 */
function createIBPanel(chartObj, index) {
    const { data, inputTicker, dateStr } = chartObj;

    const panel = document.createElement("div");
    panel.className = "chart-panel";
    panel.draggable = true;
    panel.dataset.index = index;
    panel.addEventListener("dragstart", handleDragStart);
    panel.addEventListener("dragend", handleDragEnd);

    // Header
    const header = document.createElement("div");
    header.className = "chart-header";
    header.innerHTML = `
    <div class="chart-title-row">
      <div>
        <span class="chart-title" style="color:#FFD700;">${inputTicker} IB & LEVELS</span>
        <span class="chart-subtitle">${dateStr}</span>
      </div>
      <div>
        <button class="btn-popout" onclick="openDetachedWindow(${index})" title="Pop out">⇱</button>
        <button class="btn-close" onclick="removeChart(${index})">×</button>
      </div>
    </div>
    <div class="chart-stats" style="border-left: 3px solid #FFD700; display:flex; gap:10px;">
      <span style="font-size:10px;">Range: <strong style="color:white">${data.analysis.ib_range.toFixed(2)}</strong></span>
      <span style="font-size:10px;">High: ${data.analysis.ib_high.toFixed(2)}</span>
      <span style="font-size:10px;">Low: ${data.analysis.ib_low.toFixed(2)}</span>
    </div>
  `;
    panel.appendChild(header);

    const canvasContainer = document.createElement("div");
    canvasContainer.style.flex = "1";
    canvasContainer.style.position = "relative";
    canvasContainer.style.minHeight = "0";
    canvasContainer.style.padding = "10px";

    const canvas = document.createElement("canvas");
    canvasContainer.appendChild(canvas);
    panel.appendChild(canvasContainer);

    setTimeout(() => renderIBChart(canvas, data), 0);

    return panel;
}

/**
 * Render IB chart using Chart.js
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Object} jsonData - IB data object
 */
function renderIBChart(canvas, jsonData) {
    // Filter to market hours
    const rawSeries = jsonData.series || [];
    const series = rawSeries.filter(d => d.time >= "09:20" && d.time <= "16:15");

    if (series.length === 0) return;

    const labels = series.map(d => d.time);
    const priceData = series.map(d => d.price);

    const ibHigh = jsonData.analysis.ib_high;
    const ibLow = jsonData.analysis.ib_low;
    const currentPrice = jsonData.analysis.current_price;
    const ibRange = jsonData.analysis.ib_range;

    const datasets = [];

    // Price line
    datasets.push({
        label: 'Price',
        data: priceData,
        borderColor: '#00F0FF',
        backgroundColor: '#00F0FF',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2,
        order: 1
    });

    // Helper for horizontal lines
    const makeHLine = (val, color, label, borderDash = [5, 5]) => ({
        label: label,
        data: labels.map(() => val),
        borderColor: color,
        borderWidth: 1,
        borderDash: borderDash,
        pointRadius: 0,
        fill: false,
        order: 10,
        pointHitRadius: 1,
        pointHoverRadius: 1
    });

    // IB lines
    datasets.push(makeHLine(ibHigh, 'rgba(255,255,255,0.7)', 'IB High'));
    datasets.push(makeHLine(ibLow, 'rgba(255,255,255,0.7)', 'IB Low'));

    // Fibonacci extensions
    const fibColors = ['#FFD700', '#FF8C00', '#FF4500'];
    const ibMid = (ibHigh + ibLow) / 2;

    if (currentPrice >= ibMid) {
        [1.272, 1.618, 2.0].forEach((ext, i) => {
            const val = ibLow + (ibRange * ext);
            datasets.push(makeHLine(val, fibColors[i], `Fib ${ext}`, [2, 2]));
        });
    } else {
        [-0.272, -0.618, -1.0].forEach((ext, i) => {
            const val = ibLow + (ibRange * ext);
            datasets.push(makeHLine(val, fibColors[i], `Fib ${ext}`, [2, 2]));
        });
    }

    // Greek levels
    const greekColors = {
        'max_gamma': '#00FF00', 'min_gamma': '#FF0000',
        'max_dgex': '#00FFFF', 'min_dgex': '#FFA500',
        'min_vanna': '#9400D3'
    };

    if (jsonData.levels) {
        const upperLimit = currentPrice * 1.015;
        const lowerLimit = currentPrice * 0.985;

        Object.keys(jsonData.levels).forEach(k => {
            const levelPrice = jsonData.levels[k];
            if (greekColors[k] && levelPrice >= lowerLimit && levelPrice <= upperLimit) {
                const label = k.replace('_', ' ').toUpperCase();
                datasets.push(makeHLine(levelPrice, greekColors[k], label, [10, 5]));
            }
        });
    }

    // Render chart with floating labels plugin
    new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        plugins: [{
            id: 'floatingLabels',
            afterDatasetsDraw(chart, args, options) {
                const { ctx, chartArea: { left, right, top, bottom }, scales: { x, y } } = chart;

                chart.data.datasets.forEach((dataset, i) => {
                    if (dataset.label === 'Price' || !dataset.label || !dataset.data.length) return;

                    const value = dataset.data[0];
                    const yPixel = y.getPixelForValue(value);

                    if (yPixel < top || yPixel > bottom) return;

                    ctx.save();
                    ctx.fillStyle = dataset.borderColor;
                    ctx.font = 'bold 10px sans-serif';
                    ctx.textAlign = 'right';
                    ctx.textBaseline = 'bottom';
                    ctx.fillText(dataset.label, right - 5, yPixel - 4);
                    ctx.restore();
                });
            }
        }],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'nearest',
                axis: 'y',
                intersect: false,
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    displayColors: true,
                    mode: 'nearest',
                    intersect: false,
                    filter: function (tooltipItem, index, tooltipItems) {
                        return index === 0;
                    },
                    callbacks: {
                        title: function (context) {
                            return context[0].dataset.label;
                        },
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            if (context.parsed.y !== null) label += context.parsed.y.toFixed(2);
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#666', maxTicksLimit: 10 },
                    grid: { color: '#222' }
                },
                y: {
                    position: 'right',
                    ticks: { color: '#888' },
                    grid: { color: '#222' }
                }
            }
        }
    });
}

/**
 * Add IB chart to current tab
 */
function addIBChartToCurrent(data, ticker, dateStr) {
    const tab = tabs.find((t) => t.id === currentTabId);
    if (tab) {
        tab.charts.push({
            type: 'ib',
            data: data,
            inputTicker: ticker,
            inputExp: 'ib',
            dateStr: dateStr
        });
    }
}

/**
 * Handle Load IB button click
 */
async function handleLoadIB() {
    const ticker = document.getElementById("ticker").value.toUpperCase();
    const dateVal = document.getElementById("fourier-date").value;
    const dateStr = dateVal.replace(/-/g, "");

    const btn = document.getElementById("btn-ib");
    const originalText = btn.innerText;
    btn.innerText = "⏳";

    const data = await fetchIBData(ticker, dateStr);

    btn.innerText = originalText;

    if (data) {
        addIBChartToCurrent(data, ticker, dateStr);
        renderAllCharts();
    } else {
        alert(`No IB Levels data found for ${ticker}.`);
    }
}
