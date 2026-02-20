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

    // Check if analysis data exists
    if (!data || !data.analysis) {
        const header = document.createElement("div");
        header.className = "chart-header";
        header.innerHTML = `
        <div class="chart-title-row">
          <div>
            <span class="chart-title" style="color:#FFD700;">${inputTicker} IB & LEVELS</span>
            <span class="chart-subtitle">${dateStr}</span>
          </div>
          <div>
            <button class="btn-close" onclick="removeChart(${index})">×</button>
          </div>
        </div>
        <div class="chart-stats" style="border-left: 3px solid #FF4500; display:flex; gap:10px;">
          <span style="font-size:10px; color:#FF4500;">WAIT a few seconds. Error: No analysis data available for this ticker/date</span>
        </div>
      `;
        panel.appendChild(header);
        return panel;
    }

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
 * Render IB chart using Chart.js with candlesticks
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Object} jsonData - IB data object
 */
function renderIBChart(canvas, jsonData) {
    // 1. Obtener la hora actual en Nueva York
    const now = new Date();
    const nyTime = now.toLocaleTimeString('en-US', {
        timeZone: 'America/New_York',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit'
    });

    // 2. Definir la hora de inicio dinámicamente
    // Si en NY son las 09:30 o más tarde, cortamos desde las 09:30.
    // Si es más temprano (pre-market), mostramos desde las 03:00.
    const startTime = (nyTime >= "09:30") ? "09:30" : "03:00";
    // Filter to market hours
    const rawSeries = jsonData.series || [];
    const series = rawSeries.filter(d => d.time >= startTime && d.time <= "17:00");

    if (series.length === 0) return;

    const labels = series.map(d => d.time);

    // Extract OHLC data for candlesticks
    const ohlcData = series.map(d => ({
        o: d.open || d.price,
        h: d.high || d.price,
        l: d.low || d.price,
        c: d.price
    }));

    const ibHigh = jsonData.analysis.ib_high;
    const ibLow = jsonData.analysis.ib_low;
    const currentPrice = jsonData.analysis.current_price;

    const ibRange = jsonData.analysis.ib_range;
    const upperLimit = currentPrice * 1.015;
    const lowerLimit = currentPrice * 0.985;

    const datasets = [];

    // Invisible price line for tooltip reference
    datasets.push({
        label: 'Price',
        data: series.map(d => d.price),
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        borderWidth: 0,
        pointRadius: 0,
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
        [1.272, 1.618, 2.0, 2.272, 2.618, 3, 3.272, 3.618, 4].forEach((ext, i) => {
            const val = ibLow + (ibRange * ext);
            if (val >= lowerLimit && val <= upperLimit) {
                datasets.push(makeHLine(val, fibColors[i % fibColors.length], `Fib ${ext}`, [2, 2]));
            }
        });
    } else {
        [-0.272, -0.618, -1.0, -1.272, -1.618, -2, -2.272, -2.618, -3].forEach((ext, i) => {
            const val = ibLow + (ibRange * ext);
            if (val >= lowerLimit && val <= upperLimit) {
                datasets.push(makeHLine(val, fibColors[i % fibColors.length], `Fib ${ext}`, [2, 2]));
            }
        });
    }

    // Greek levels
    const greekColors = {
        'max_gamma': '#00FF00', 'min_gamma': '#FF0000',
        'max_dgex': '#00FFFF', 'min_dgex': '#FFA500',
        'min_vanna': '#9400D3',
        'max_vega': '#FF1493',
        'max_vomma': '#FFFFFF',
        'call_wall': '#00FF00', 
        'put_wall': '#FF0000'
    };

    if (jsonData.levels) {
        Object.keys(jsonData.levels).forEach(k => {
            const levelPrice = jsonData.levels[k];
            if (greekColors[k] && levelPrice >= lowerLimit && levelPrice <= upperLimit) {
                const label = k.replace('_', ' ').toUpperCase();
                datasets.push(makeHLine(levelPrice, greekColors[k], label, [10, 5]));
            }
        });
    }

    // Custom candlestick drawing plugin
    const candlestickPlugin = {
        id: 'candlestick',
        beforeDatasetsDraw(chart) {
            const { ctx, chartArea: { left, right, top, bottom }, scales: { x, y } } = chart;

            const barWidth = (right - left) / labels.length * 0.6;

            ohlcData.forEach((candle, i) => {
                const xPixel = x.getPixelForValue(i);
                const oPixel = y.getPixelForValue(candle.o);
                const hPixel = y.getPixelForValue(candle.h);
                const lPixel = y.getPixelForValue(candle.l);
                const cPixel = y.getPixelForValue(candle.c);

                const isBullish = candle.c >= candle.o;
                const color = isBullish ? '#00d26a' : '#ff4757';

                ctx.save();

                // Draw wick
                ctx.strokeStyle = color;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(xPixel, hPixel);
                ctx.lineTo(xPixel, lPixel);
                ctx.stroke();

                // Draw body
                const bodyTop = Math.min(oPixel, cPixel);
                const bodyHeight = Math.abs(cPixel - oPixel) || 1;

                ctx.fillStyle = color;
                ctx.fillRect(xPixel - barWidth / 2, bodyTop, barWidth, bodyHeight);

                ctx.restore();
            });
        }
    };

    // Floating labels plugin
    const floatingLabelsPlugin = {
        id: 'floatingLabels',
        afterDatasetsDraw(chart) {
            const { ctx, chartArea: { left, right, top, bottom }, scales: { x, y } } = chart;

            chart.data.datasets.forEach((dataset, i) => {
                if (dataset.label === 'Price' || !dataset.label || !dataset.data.length) return;

                const value = dataset.data[0];
                const yPixel = y.getPixelForValue(value);

                if (yPixel < top || yPixel > bottom) return;

                ctx.save();
                ctx.fillStyle = dataset.borderColor;
                ctx.font = 'bold 10px sans-serif';
                ctx.textAlign = 'left';
                ctx.textBaseline = 'bottom';
                ctx.fillText(dataset.label, left + 5, yPixel - 4);
                ctx.restore();
            });
        }
    };

    // Render chart
    new Chart(canvas, {
        type: 'line',
        data: { labels, datasets },
        plugins: [candlestickPlugin, floatingLabelsPlugin],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false,
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    displayColors: false,
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        title: function (context) {
                            const idx = context[0].dataIndex;
                            return `${labels[idx]}`;
                        },
                        label: function (context) {
                            const idx = context.dataIndex;
                            const c = ohlcData[idx];
                            if (context.dataset.label === 'Price') {
                                return [
                                    `Open: ${c.o.toFixed(2)}`,
                                    `High: ${c.h.toFixed(2)}`,
                                    `Low: ${c.l.toFixed(2)}`,
                                    `Close: ${c.c.toFixed(2)}`
                                ];
                            }
                            return null;
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

    // Use retry mechanism to wait for server to finish generating file
    const data = await fetchIBDataWithRetry(ticker, dateStr);

    btn.innerText = originalText;

    if (data) {
        addIBChartToCurrent(data, ticker, dateStr);
        renderAllCharts();
    } else {
        // Show actual file being searched (without slashes)
        const cleanTicker = ticker.replace(/\//g, '');
        alert(`No IB Levels data found for ${ticker}.\nSearched: ib_data_${cleanTicker}_${dateStr}.json`);
    }
}
